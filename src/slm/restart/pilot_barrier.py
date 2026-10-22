"""Persistent, one-decision pilot barrier; independent of checkpoint rollback.

The scoped evaluator must bind and validate raw evaluation evidence before
calling decide(). This component enforces persistence, not evidence authenticity.
"""
import hashlib,json,sqlite3,math
from pathlib import Path
from .pilot_gate import assess,PilotRejected


class PilotBarrier:
    def __init__(self,path,*,run_identity,schedule_hash,evaluation_hash):
        if any(not isinstance(x,str) or not x for x in (run_identity,schedule_hash,evaluation_hash)):
            raise ValueError('Missing pilot barrier identity')
        self.db=sqlite3.connect(Path(path),isolation_level=None,timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS pilot_contract (id INTEGER PRIMARY KEY CHECK(id=1),value TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS pilot_decision (id INTEGER PRIMARY KEY CHECK(id=1),evidence TEXT NOT NULL,evidence_hash TEXT NOT NULL,checkpoint_hash TEXT NOT NULL,result TEXT NOT NULL)')
        contract=json.dumps(dict(run_identity=run_identity,schedule_hash=schedule_hash,evaluation_hash=evaluation_hash),sort_keys=True)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            found=self.db.execute('SELECT value FROM pilot_contract WHERE id=1').fetchone()
            if found and found[0]!=contract:raise ValueError('Changed pilot barrier contract')
            self.db.execute('INSERT OR IGNORE INTO pilot_contract VALUES (1,?)',(contract,));self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');self.db.close();raise

    def decision(self):
        row=self.db.execute('SELECT evidence,evidence_hash,checkpoint_hash,result FROM pilot_decision WHERE id=1').fetchone()
        if row is None:return None
        if hashlib.sha256(row[0].encode()).hexdigest()!=row[1]:raise ValueError('Corrupt pilot evidence')
        evidence=json.loads(row[0]);stored=json.loads(row[3])
        expected=self._result(evidence)
        if stored!=expected:raise ValueError('Pilot decision inconsistent with evidence')
        return dict(result=stored,evidence_sha256=row[1],checkpoint_sha256=row[2])

    @staticmethod
    def _result(evidence):
        try:return assess(**evidence)
        except (PilotRejected,TypeError,KeyError,ValueError,AttributeError,OverflowError) as error:
            return {'status':'PILOT_REJECTED','reason':str(error),'training_authorized_by_this_check':False}

    def decide(self,evidence,*,checkpoint_sha256):
        if (not isinstance(checkpoint_sha256,str) or len(checkpoint_sha256)!=64
                or any(c not in '0123456789abcdef' for c in checkpoint_sha256)):
            raise ValueError('Pilot checkpoint digest required')
        # Preserve invalid numeric locations as null so failure is durable JSON.
        def sanitize(value):
            if isinstance(value,float) and not math.isfinite(value):return None
            if isinstance(value,list):return [sanitize(x) for x in value]
            if isinstance(value,dict):return {k:sanitize(v) for k,v in value.items()}
            return value
        evidence=sanitize(evidence)
        encoded=json.dumps(evidence,sort_keys=True,separators=(',',':'),allow_nan=False)
        digest=hashlib.sha256(encoded.encode()).hexdigest();result=self._result(evidence)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            if self.db.execute('SELECT 1 FROM pilot_decision WHERE id=1').fetchone():
                raise ValueError('Pilot already decided; no replacement or automatic rescue')
            self.db.execute('INSERT INTO pilot_decision VALUES (1,?,?,?,?)',
                            (encoded,digest,checkpoint_sha256,json.dumps(result,sort_keys=True)))
            self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise
        return self.decision()

    def require_update(self,*,start_targets,end_targets):
        if (type(start_targets) is not int or type(end_targets) is not int
                or not 0<=start_targets<end_targets or start_targets<2000000<end_targets):
            raise ValueError('Invalid update or pilot overshoot')
        decision=self.decision()
        if decision and decision['result']['status']=='PILOT_REJECTED':
            raise PilotRejected('Persistent pilot failure; checkpoint rollback cannot resume')
        if end_targets>2000000 and decision is None:
            raise PilotRejected('Pilot decision required before continuation')
        # Other resource/quality/time/identity gates remain mandatory.

    def close(self):self.db.close()
