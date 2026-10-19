"""Durable conservative precharging for sequential finite public-data intake."""
# Creator: Navneet Prabhakar
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from slm.data.schema import digest

DIMENSIONS = ('requests', 'body_bytes', 'rows', 'output_bytes')


class IntakeLedger:
    """Pending/failed charges persist; uncertain operations cannot auto-retry.

    This accounts logical requests and bounded response bodies, not HTTP headers
    or redirect hops. A separate process supervisor must enforce wall timeout.
    File/disk/RSS enforcement is the caller's responsibility, not this ledger's.
    """
    def __init__(self, root, contract, *, clock=time.time):
        self.root = Path(root).resolve()
        fresh = not self.root.exists()
        if set(contract['limits']) != set(DIMENSIONS) or any(
                type(v) is not int or v <= 0 for v in contract['limits'].values()):
            raise ValueError('Positive integer intake limits required')
        if type(contract['wall_seconds']) is not int or contract['wall_seconds'] <= 0:
            raise ValueError('Finite wall limit required')
        self.root.mkdir(parents=True, exist_ok=True)
        if (self.root / 'ledger.sqlite').is_symlink() or (self.root / 'job.lock').is_symlink():
            raise ValueError('Symlink ledger refused')
        if not fresh and not (self.root / 'ledger.sqlite').is_file():
            raise ValueError('Existing ledger directory lost its database; no budget reset')
        self.lock = (self.root / 'job.lock').open('a')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self.lock.close(); raise
        self.clock = clock
        self.db = None
        try:
            self.db = sqlite3.connect(self.root / 'ledger.sqlite', isolation_level=None)
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA journal_mode=DELETE')
            self.db.execute('CREATE TABLE IF NOT EXISTS job (identity TEXT, root TEXT, contract TEXT, deadline REAL)')
            self.db.execute('CREATE TABLE IF NOT EXISTS attempts (key TEXT PRIMARY KEY, charge TEXT, state TEXT, actual_bytes INTEGER, body_sha256 TEXT)')
            row = self.db.execute('SELECT identity,root,contract,deadline FROM job').fetchall()
            identity = digest(contract)
            if not row:
                if not fresh:
                    raise ValueError('Existing database lost its job identity; no budget reset')
                if self.db.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]:
                    raise ValueError('Orphaned ledger charges')
                self.db.execute('INSERT INTO job VALUES (?,?,?,?)',
                    (identity, str(self.root), json.dumps(contract, sort_keys=True), clock() + contract['wall_seconds']))
                row = self.db.execute('SELECT identity,root,contract,deadline FROM job').fetchall()
            if len(row) != 1 or row[0][0] != identity or row[0][1] != str(self.root) or json.loads(row[0][2]) != contract:
                raise ValueError('Exact contract and resume location required')
            self.contract = json.loads(row[0][2])
            self.deadline = row[0][3]
            self.check_time()
        except BaseException:
            self.close(); raise

    def close(self):
        if self.db is not None:
            self.db.close(); self.db = None
        self.lock.close()

    def check_time(self):
        if self.clock() >= self.deadline:
            raise ValueError('Persistent intake wall deadline reached')

    def totals(self):
        total = dict.fromkeys(DIMENSIONS, 0)
        for raw, in self.db.execute('SELECT charge FROM attempts'):
            for k, v in json.loads(raw).items(): total[k] += v
        return total

    def reserve(self, key, **charges):
        """Commit before external work; rejected operations consume no allowance."""
        if not isinstance(key, str) or not key or set(charges) - set(DIMENSIONS) or any(
                type(v) is not int or v < 0 for v in charges.values()):
            raise ValueError('Explicit nonnegative operation charge required')
        charges = {k: charges.get(k, 0) for k in DIMENSIONS}
        if not any(charges.values()): raise ValueError('Nonzero precharge required')
        self.check_time()
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM attempts WHERE key=?', (key,)).fetchone():
                raise ValueError('Operation already reserved; no automatic replay')
            total = self.totals()
            if any(total[k] + charges[k] > self.contract['limits'][k] for k in DIMENSIONS):
                raise ValueError('Persistent global intake budget exhausted')
            self.db.execute('INSERT INTO attempts VALUES (?,?,?,NULL,NULL)',
                            (key, json.dumps(charges, sort_keys=True), 'pending'))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); raise

    def finish(self, key, *, raw=None):
        """Only bytes received in a successful request can be recorded as success."""
        row = self.db.execute('SELECT charge,state FROM attempts WHERE key=?', (key,)).fetchone()
        if row is None or row[1] != 'pending': raise ValueError('Pending reservation required')
        charges = json.loads(row[0])
        if raw is not None and (not isinstance(raw, bytes) or len(raw) > charges['body_bytes']):
            raise ValueError('Successful bytes exceed precharged body allowance')
        self.db.execute('UPDATE attempts SET state=?,actual_bytes=?,body_sha256=? WHERE key=?',
                        ('failed' if raw is None else 'complete', None if raw is None else len(raw),
                         None if raw is None else hashlib.sha256(raw).hexdigest(), key))

    def snapshot(self):
        rows = [dict(key=k, charge=json.loads(c), state=s, actual_body_bytes=n, body_sha256=h)
                for k,c,s,n,h in self.db.execute('SELECT key,charge,state,actual_bytes,body_sha256 FROM attempts ORDER BY rowid')]
        return dict(contract_sha256=digest(self.contract), root=str(self.root),
                    deadline_epoch_seconds=self.deadline, reserved=self.totals(), attempts=rows)
