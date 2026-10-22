"""Crash-persistent pre-work reservations. No neural model dependency."""
import json
import math
import sqlite3
from pathlib import Path

class BudgetError(RuntimeError): pass

class WorkBudgetExhausted(BudgetError):
    """A refused, uncharged update at a verified target/update/exposure limit."""
    def __init__(self,proof):
        super().__init__(proof['reason']);self.proof=proof


class Ledger:
    def __init__(self, path, identity, *, target_cap, update_cap, presentation_cap, deadline):
        caps=(target_cap,update_cap,presentation_cap)
        if any(type(v) is not int or v<1 for v in caps) or not math.isfinite(deadline):
            raise ValueError('Positive integer budgets and finite deadline required')
        if not identity or not isinstance(identity,str):raise ValueError('Run identity required')
        self.db=sqlite3.connect(Path(path),timeout=30,isolation_level=None)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS contract (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, targets INTEGER NOT NULL, completed INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS exposures (reservation TEXT NOT NULL, document TEXT NOT NULL, first INTEGER NOT NULL, last INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS exposure_document ON exposures(document,first,last);
        CREATE INDEX IF NOT EXISTS exposure_reservation ON exposures(reservation);''')
        contract=json.dumps(dict(identity=identity,target_cap=target_cap,update_cap=update_cap,presentation_cap=presentation_cap,deadline=deadline),sort_keys=True)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute("SELECT value FROM contract WHERE key='run'").fetchone()
            if row and row[0]!=contract:raise BudgetError('Changed execution contract')
            self.db.execute("INSERT OR IGNORE INTO contract VALUES ('run',?)",(contract,))
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');self.db.close();raise
        self.target_cap,self.update_cap,self.presentation_cap=caps
        self.deadline=deadline

    def reserve(self, reservation_id, spans, *, now):
        """spans: (document ID, first target offset, exclusive end). Charge before work.

        Reservation IDs cannot be reused, even after a crash. Retry uses a new ID
        and consumes additional exposure; no refunds or reset operation exists.
        """
        if not isinstance(reservation_id,str) or not reservation_id:raise ValueError('Reservation ID required')
        if not math.isfinite(now):raise ValueError('Finite clock required')
        spans=list(spans); total_targets=0; grouped={}
        for doc,start,end in spans:
            if not isinstance(doc,str) or not doc or type(start) is not int or type(end) is not int or start<0 or end<=start:
                raise ValueError('Invalid target span')
            if end-start>self.target_cap:raise BudgetError('Span exceeds total budget')
            total_targets+=end-start
            grouped.setdefault(doc,[]).append((start,end))
        if not spans:raise ValueError('Empty update')
        for ranges in grouped.values():
            ordered=sorted(ranges)
            if any(b[0]<a[1] for a,b in zip(ordered,ordered[1:])):raise ValueError('Repeated targets in update')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if now>=self.deadline:raise BudgetError('Elapsed budget exhausted')
            if self.db.execute('SELECT 1 FROM reservations WHERE id=?',(reservation_id,)).fetchone():raise BudgetError('Reservation already charged; cannot replay silently')
            reason=self._work_exhaustion(spans,total_targets)
            if reason:
                last=self.db.execute('SELECT coalesce(max(rowid),0) FROM reservations').fetchone()[0]
                raise WorkBudgetExhausted(dict(reason=reason,reservation_id=reservation_id,spans=[list(x) for x in spans],
                    proposed_targets=total_targets,ledger_snapshot=self._prefix_snapshot(last)))
            self.db.execute('INSERT INTO reservations(id,targets) VALUES (?,?)',(reservation_id,total_targets))
            self.db.executemany('INSERT INTO exposures VALUES (?,?,?,?)',[(reservation_id,doc,start,end) for doc,start,end in spans])
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK');raise
        return total_targets

    def _work_exhaustion(self,spans,total_targets):
        count,total=self.db.execute('SELECT count(*),coalesce(sum(targets),0) FROM reservations').fetchone()
        if count+1>self.update_cap or total+total_targets>self.target_cap:return 'Target/update budget exhausted'
        for doc,start,end in spans:
            events={start:1,end:-1}
            for first,last in self.db.execute('SELECT first,last FROM exposures WHERE document=? AND first<? AND last>?',(doc,end,start)):
                left,right=max(first,start),min(last,end)
                events[left]=events.get(left,0)+1;events[right]=events.get(right,0)-1
            concurrent=0
            for _,delta in sorted(events.items()):
                concurrent+=delta
                if concurrent>self.presentation_cap:return 'Presentation budget exhausted'
        return None

    def verify_exhaustion(self,proof):
        if set(proof)!={'reason','reservation_id','spans','proposed_targets','ledger_snapshot'}:raise ValueError('Invalid exhaustion proof')
        if proof['ledger_snapshot']!=self.snapshot():raise ValueError('Exhaustion ledger changed')
        spans=proof['spans']
        if (not spans or any(not isinstance(d,str) or not d or type(a) is not int or type(b) is not int or not 0<=a<b for d,a,b in spans)
                or type(proof['proposed_targets']) is not int or sum(b-a for _,a,b in spans)!=proof['proposed_targets']):
            raise ValueError('Invalid exhaustion spans')
        if self.db.execute('SELECT 1 FROM reservations WHERE id=?',(proof['reservation_id'],)).fetchone():
            raise ValueError('Refused work was charged')
        reason=self._work_exhaustion(spans,proof['proposed_targets'])
        if reason is None or reason!=proof['reason']:raise ValueError('Work budget is not exhausted as claimed')
        return True

    def complete(self,reservation_id):
        cur=self.db.execute('UPDATE reservations SET completed=1 WHERE id=? AND completed=0',(reservation_id,))
        if cur.rowcount!=1:raise BudgetError('Missing or already completed reservation')

    def totals(self):
        count,targets,completed=self.db.execute('SELECT count(*),coalesce(sum(targets),0),coalesce(sum(completed),0) FROM reservations').fetchone()
        return dict(updates_reserved=count,targets_reserved=targets,updates_completed=completed)

    def close(self):self.db.close()

    def _prefix_snapshot(self,last_sequence):
        """Logical digest includes WAL-visible rows, not mutable SQLite file bytes."""
        import hashlib
        rows=self.db.execute('SELECT rowid,id,targets,completed FROM reservations WHERE rowid<=? ORDER BY rowid',(last_sequence,)).fetchall()
        if (rows[-1][0] if rows else 0)!=last_sequence:
            raise BudgetError('Checkpoint ledger prefix missing')
        exposures=[]
        for seq,rid,targets,completed in rows:
            spans=self.db.execute('SELECT document,first,last FROM exposures WHERE reservation=? ORDER BY document,first,last',(rid,)).fetchall()
            if completed not in (0,1) or targets<=0 or sum(end-start for _,start,end in spans)!=targets:
                raise BudgetError('Invalid reservation accounting')
            exposures.append([rid,spans])
        contract=self.db.execute("SELECT value FROM contract WHERE key='run'").fetchone()[0]
        payload=json.dumps({'contract':contract,'rows':rows,'exposures':exposures},sort_keys=True,separators=(',',':')).encode()
        return dict(last_sequence=last_sequence,digest=hashlib.sha256(payload).hexdigest(),
                    updates_reserved=len(rows),targets_reserved=sum(r[2] for r in rows),
                    updates_completed=sum(r[3] for r in rows),
                    targets_completed=sum(r[2] for r in rows if r[3]))

    def snapshot(self):
        self.db.execute('BEGIN')
        try:
            last=self.db.execute('SELECT coalesce(max(rowid),0) FROM reservations').fetchone()[0]
            value=self._prefix_snapshot(last)
            self.db.execute('COMMIT');return value
        except BaseException:
            self.db.execute('ROLLBACK');raise

    def verify_snapshot(self,snapshot):
        """Verify old checkpoint prefix while retaining every later budget charge.

        Tail reservations are NOT refunded or silently marked complete. The caller
        must reserve any replay separately and validate its update/data state.
        """
        if not isinstance(snapshot,dict) or type(snapshot.get('last_sequence')) is not int or snapshot['last_sequence']<0:
            raise BudgetError('Invalid checkpoint ledger snapshot')
        self.db.execute('BEGIN')
        try:
            if self._prefix_snapshot(snapshot['last_sequence'])!=snapshot:
                raise BudgetError('Checkpoint ledger prefix changed')
            count,targets=self.db.execute('SELECT count(*),coalesce(sum(targets),0) FROM reservations WHERE rowid>?',(snapshot['last_sequence'],)).fetchone()
            self.db.execute('COMMIT')
            return dict(later_updates_reserved=count,later_targets_reserved=targets,refunds=0)
        except BaseException:
            self.db.execute('ROLLBACK');raise
