"""Single-outstanding-request spending reservations and durable response cache."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from slm.data.schema import digest


class Journal:
    def __init__(self,path,cap_nanousd,authorization_id,max_requests=1000):
        if type(cap_nanousd) is not int or not 0<=cap_nanousd<2**60 or not isinstance(authorization_id,str) or not authorization_id.strip():
            raise ValueError('Finite nonnegative integer budget and authorization identity required')
        if type(max_requests) is not int or not 1<=max_requests<=1000000:raise ValueError('Finite positive request cap required')
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.transaction() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] not in (0,1):raise ValueError('Unknown journal schema')
            db.execute('CREATE TABLE IF NOT EXISTS budget (singleton INTEGER PRIMARY KEY CHECK(singleton=1), cap INTEGER NOT NULL, authorization TEXT NOT NULL, halted INTEGER NOT NULL, max_requests INTEGER NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS requests (key TEXT PRIMARY KEY, reserved INTEGER NOT NULL, accounted INTEGER, status TEXT NOT NULL, response TEXT, response_hash TEXT, error_type TEXT)')
            row=db.execute('SELECT cap,authorization,max_requests FROM budget WHERE singleton=1').fetchone()
            if row is None:db.execute('INSERT INTO budget VALUES(1,?,?,0,?)',(cap_nanousd,authorization_id,max_requests))
            elif row!=(cap_nanousd,authorization_id,max_requests):raise ValueError('Existing journal budget/authorization differs; refusing reset')
            db.execute('PRAGMA user_version=1')

    @contextmanager
    def transaction(self):
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None)
        try:
            db.execute('PRAGMA synchronous=FULL');db.execute('BEGIN IMMEDIATE')
            yield db
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:db.execute('ROLLBACK')
            raise
        finally:db.close()

    def cached(self,key):
        with self.transaction() as db:
            row=db.execute('SELECT status,response,response_hash FROM requests WHERE key=?',(key,)).fetchone()
        if row is None:return None
        if row[0]!='complete':raise RuntimeError('Request has no completed cached response; never replay automatically')
        value=json.loads(row[1])
        if digest(value)!=row[2]:raise ValueError('Cached response checksum differs')
        return value

    def reserve(self,key,amount):
        if type(amount) is not int or amount<0:raise ValueError('Nonnegative integer reservation required')
        with self.transaction() as db:
            cap,_,halted,max_requests=db.execute('SELECT cap,authorization,halted,max_requests FROM budget WHERE singleton=1').fetchone()
            if halted:raise RuntimeError('Journal halted; reconcile uncertainty before new requests')
            if db.execute('SELECT 1 FROM requests WHERE status NOT IN (?,?)',('complete','abandoned')).fetchone():
                raise RuntimeError('Outstanding request exists; single-worker journal refuses duplicates/concurrency')
            if db.execute('SELECT COUNT(*) FROM requests').fetchone()[0]>=max_requests:raise ValueError('Teacher request-count cap reached')
            used=db.execute('SELECT COALESCE(SUM(COALESCE(accounted,reserved)),0) FROM requests').fetchone()[0]
            if used+amount>cap:raise ValueError('Teacher reservation exceeds authorized journal budget')
            db.execute('INSERT INTO requests(key,reserved,status) VALUES(?,?,?)',(key,amount,'reserved'))

    def finish(self,key,response,accounted):
        if type(accounted) is not int or accounted<0:raise ValueError('Nonnegative integer accounting required')
        with self.transaction() as db:
            row=db.execute('SELECT reserved,status FROM requests WHERE key=?',(key,)).fetchone()
            if row is None or row[1]!='reserved':raise ValueError('No matching outstanding reservation')
            if accounted>row[0]:
                db.execute('UPDATE budget SET halted=1 WHERE singleton=1')
                db.execute('UPDATE requests SET status=?,accounted=?,error_type=? WHERE key=?',('uncertain',accounted,'UsageExceedsReservation',key))
                overrun=True
            else:
                db.execute('UPDATE requests SET status=?,accounted=?,response=?,response_hash=? WHERE key=?',
                    ('complete',accounted,json.dumps(response,sort_keys=True,allow_nan=False),digest(response),key));overrun=False
        if overrun:raise RuntimeError('Usage exceeded reservation; journal halted, no billing guarantee')

    def uncertain(self,key,error_type):
        with self.transaction() as db:
            db.execute('UPDATE requests SET status=?,error_type=? WHERE key=? AND status=?',('uncertain',error_type,key,'reserved'))
            db.execute('UPDATE budget SET halted=1 WHERE singleton=1')

    def summary(self):
        with self.transaction() as db:
            cap,authorization,halted,max_requests=db.execute('SELECT cap,authorization,halted,max_requests FROM budget WHERE singleton=1').fetchone()
            rows=db.execute('SELECT status,COUNT(*),SUM(COALESCE(accounted,reserved)) FROM requests GROUP BY status').fetchall()
        return {'cap_nanousd':cap,'authorization_id':authorization,'halted':bool(halted),'max_requests':max_requests,
            'states':{status:{'requests':n,'accounted_or_reserved_nanousd':cost} for status,n,cost in rows},
            'settled_cost_usd':None,'scope':'Local conservative accounting; excludes external usage and is not a provider billing cap.'}
