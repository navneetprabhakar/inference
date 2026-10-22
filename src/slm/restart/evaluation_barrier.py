"""Durable evaluation sequencing; evidence authenticity belongs to the evaluator.

The scoped evaluator supplies a verifier that raises on invalid raw evidence.
This barrier binds accepted evidence bytes to run, schedule, target and checkpoint;
it never computes scores or grants candidate initialization authority.
"""
import hashlib
import json
import sqlite3
from pathlib import Path
from .numerical_monitor_comparison import exact


class EvaluationPending(RuntimeError):
    pass


class EvaluationBarrier:
    def __init__(self, path, *, identity, schedule):
        if not isinstance(identity, str) or not identity or not schedule.updates:
            raise ValueError('Missing evaluation contract')
        self.schedule = schedule
        self.identity = identity
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS barrier (
                id INTEGER PRIMARY KEY CHECK(id=1), contract TEXT NOT NULL,
                step INTEGER NOT NULL, terminal TEXT);
            CREATE TABLE IF NOT EXISTS evidence (
                step INTEGER NOT NULL, event TEXT NOT NULL, raw BLOB NOT NULL,
                sha256 TEXT NOT NULL, PRIMARY KEY(step,event));
        ''')
        contract = json.dumps({'identity':identity,'schedule_sha256':schedule.sha256}, sort_keys=True)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT contract FROM barrier WHERE id=1').fetchone()
            if row and row[0] != contract:
                raise ValueError('Changed evaluation contract')
            self.db.execute('INSERT OR IGNORE INTO barrier VALUES (1,?,0,NULL)', (contract,))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); self.db.close(); raise

    def position(self):
        step, terminal = self.db.execute('SELECT step,terminal FROM barrier WHERE id=1').fetchone()
        if terminal:
            raise EvaluationPending('Terminal evaluation barrier: '+terminal)
        return step

    def required(self, step):
        if step == 0:
            return ('dev_loss_checkpoint',)
        # Pilot decisions remain separately durable in PilotBarrier.
        events = [e for e in self.schedule.updates[step-1].events
                  if e not in ('pilot_continuation_gate','normal_budget_end')]
        if step == len(self.schedule.updates) and 'copying_probes' not in events:
            events.append('copying_probes')
        return tuple(events)

    def pending(self):
        step = self.position()
        rows = self.db.execute('SELECT event,raw,sha256 FROM evidence WHERE step=?', (step,)).fetchall()
        for event, raw, pin in rows:
            if hashlib.sha256(raw).hexdigest() != pin:
                raise ValueError('Corrupt evaluation evidence')
        done = {row[0] for row in rows}
        return tuple(e for e in self.required(step) if e not in done)

    def require_update(self, update):
        step = self.position()
        if step >= len(self.schedule.updates) or update != self.schedule.updates[step]:
            raise EvaluationPending('Update differs from durable schedule position')
        if self.pending():
            raise EvaluationPending('Required evaluation pending: '+', '.join(self.pending()))

    def completed_update(self, update):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.require_update(update)
            self.db.execute('UPDATE barrier SET step=? WHERE id=1', (update.step,))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK'); raise

    def accept(self, event, path, *, checkpoint_sha256, verify):
        """verify(raw, context) MUST inspect raw metrics/artifacts and raise on failure.

        There is deliberately no default verifier. Publication by a worker alone
        is not evidence of acceptance. Failed verification makes the barrier terminal.
        """
        self.db.execute('BEGIN IMMEDIATE')
        try:
            step = self.position()
            if event not in self.pending():
                raise EvaluationPending('Unexpected or already accepted evaluation')
            if (not isinstance(checkpoint_sha256,str) or len(checkpoint_sha256)!=64
                    or any(c not in '0123456789abcdef' for c in checkpoint_sha256)):
                raise ValueError('Invalid checkpoint hash')
            raw = Path(path).read_bytes()
            context = {'identity':self.identity,'schedule_sha256':self.schedule.sha256,
                       'step':step,'targets':0 if step==0 else self.schedule.updates[step-1].cumulative_targets,
                       'event':event,'checkpoint_sha256':checkpoint_sha256}
            prior = self.db.execute('SELECT raw FROM evidence WHERE step=?',(step,)).fetchall()
            if any(json.loads(row[0])['context']['checkpoint_sha256'] != checkpoint_sha256 for row in prior):
                raise ValueError('Evaluations at one boundary must use the same checkpoint')
            payload = json.loads(raw)
            if not isinstance(payload,dict) or not exact(payload.get('context'),context):
                raise ValueError('Unbound evaluation evidence')
            if verify(raw, context) is not True:
                raise ValueError('Evaluator did not verify evidence')
            self.db.execute('INSERT INTO evidence VALUES (?,?,?,?)',
                            (step,event,raw,hashlib.sha256(raw).hexdigest()))
            self.db.execute('COMMIT')
        except BaseException as error:
            self.db.execute('ROLLBACK')
            self.db.execute('UPDATE barrier SET terminal=coalesce(terminal,?) WHERE id=1',
                            (type(error).__name__+': '+str(error),))
            raise

    def close(self):
        self.db.close()
