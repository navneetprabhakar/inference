"""Pre-work accounting for the single bounded numerical-suite attempt."""
import json,math,sqlite3
from pathlib import Path

class NumericalBudgetError(RuntimeError):pass

class NumericalBudget:
    def __init__(self,path,*,identity,deadline):
        if not isinstance(identity,str) or not identity or type(deadline) not in (int,float) or not math.isfinite(deadline):raise ValueError('Invalid numerical budget contract')
        self.db=sqlite3.connect(Path(path),isolation_level=None,timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS contract (id INTEGER PRIMARY KEY CHECK(id=1),value TEXT NOT NULL,terminal TEXT);
        CREATE TABLE IF NOT EXISTS work (id TEXT PRIMARY KEY,backend TEXT NOT NULL,kind TEXT NOT NULL,positions INTEGER NOT NULL,optimizer_updates INTEGER NOT NULL,completed INTEGER NOT NULL DEFAULT 0);''')
        contract=json.dumps(dict(identity=identity,deadline=deadline,position_cap=100000,update_cap=18),sort_keys=True)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            old=self.db.execute('SELECT value FROM contract WHERE id=1').fetchone()
            if old and old[0]!=contract:raise NumericalBudgetError('Changed numerical execution contract')
            self.db.execute('INSERT OR IGNORE INTO contract VALUES (1,?,NULL)',(contract,));self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');self.db.close();raise
        self.deadline=deadline

    def reserve(self,event_id,*,backend,kind,positions,now):
        if (not isinstance(event_id,str) or not event_id or backend not in ('mlx','torch')
            or kind not in ('forward','gradient','optimizer','fp64_loss','ce_gradient')
            or type(positions) is not int or positions<1 or type(now) not in (int,float) or not math.isfinite(now)):
            raise ValueError('Invalid numerical work reservation')
        updates=int(kind=='optimizer')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            terminal=self.db.execute('SELECT terminal FROM contract WHERE id=1').fetchone()[0]
            if terminal:raise NumericalBudgetError('Terminal numerical attempt: '+terminal)
            if now>=self.deadline:raise NumericalBudgetError('Numerical deadline exhausted')
            used,count=self.db.execute('SELECT coalesce(sum(positions),0),coalesce(sum(optimizer_updates),0) FROM work').fetchone()
            if used+positions>100000 or count+updates>18:raise NumericalBudgetError('Numerical work cap exhausted')
            if self.db.execute('SELECT 1 FROM work WHERE id=?',(event_id,)).fetchone():raise NumericalBudgetError('Work already charged; duplicate ID forbidden')
            self.db.execute('INSERT INTO work(id,backend,kind,positions,optimizer_updates) VALUES (?,?,?,?,?)',(event_id,backend,kind,positions,updates))
            self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise

    def complete(self,event_id):
        if self.db.execute('UPDATE work SET completed=1 WHERE id=? AND completed=0',(event_id,)).rowcount!=1:
            raise NumericalBudgetError('Missing or already completed work')

    def stop(self,reason):
        if not isinstance(reason,str) or not reason:raise ValueError('Reason required')
        self.db.execute('UPDATE contract SET terminal=coalesce(terminal,?) WHERE id=1',(reason,))

    def events(self,*,require_complete=True):
        rows=self.db.execute('SELECT id,backend,kind,positions,optimizer_updates,completed FROM work ORDER BY rowid').fetchall()
        if require_complete and self.db.execute('SELECT terminal FROM contract WHERE id=1').fetchone()[0]:raise NumericalBudgetError('Terminal numerical attempt')
        if require_complete and any(not r[5] for r in rows):raise NumericalBudgetError('Incomplete charged numerical work')
        return [dict(id=r[0],backend=r[1],kind=r[2],positions=r[3],optimizer_updates=r[4]) for r in rows]

    def close(self):self.db.close()


def perform(budget,event_id,*,backend,kind,positions,now,operation,settle):
    """Charge before operation; settle forces lazy work before marking completion."""
    budget.reserve(event_id,backend=backend,kind=kind,positions=positions,now=now)
    try:
        result=operation()
        settle(result)
        budget.complete(event_id)
        return result
    except BaseException as error:
        budget.stop(type(error).__name__+': '+str(error))
        raise
