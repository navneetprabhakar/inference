"""Immutable SQLite snapshots for a read-only final evaluator.

Backup reads committed WAL contents without modifying original training stores.
All worker handles reject writes, including accidental calls to reserve or resume.
The separate live clock is read-only but observes supervisor charges.
"""
import hashlib,json,os,sqlite3
from pathlib import Path
from .ledger import Ledger
from .evaluation_quality import EvaluationQualityBarrier
from .pilot_barrier import PilotBarrier
from .checkpoint_catalog import Catalog
from .supervisor import TimeBudget
from .evaluation_snapshot import MANIFEST_SHA256

NAMES=('ledger','quality','pilot','catalog')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(root,*,ledger,quality,pilot,catalog):
    root=Path(root).absolute()
    if root.parent.resolve(strict=True)!=root.parent:raise ValueError('Redirected snapshot parent')
    root.mkdir()
    handles=dict(ledger=ledger,quality=quality,pilot=pilot,catalog=catalog)
    before=ledger.snapshot()
    versions={name:(h.db.execute('PRAGMA data_version').fetchone()[0],h.db.total_changes) for name,h in handles.items()}
    files={}
    for name,handle in handles.items():
        path=root/(name+'.sqlite');db=sqlite3.connect(path)
        try:
            handle.db.backup(db)
            if db.execute('PRAGMA quick_check').fetchall()!=[('ok',)]:raise ValueError('Invalid database snapshot')
        finally:db.close()
        with path.open('rb') as f:os.fsync(f.fileno())
        files[path.name]=digest(path)
    if (ledger.snapshot()!=before or versions!={name:(h.db.execute('PRAGMA data_version').fetchone()[0],h.db.total_changes) for name,h in handles.items()}):
        raise ValueError('Training changed during final state freeze')
    raw=(json.dumps({'schema':1,'files':files,'ledger_snapshot':before},sort_keys=True,indent=2)+'\n').encode()
    with (root/'manifest.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    fd=os.open(root,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return hashlib.sha256(raw).hexdigest()


def readonly(path,*,immutable):
    path=Path(path).absolute()
    if path.resolve(strict=True)!=path or not path.is_file():raise ValueError('Redirected readonly state')
    db=sqlite3.connect(path.as_uri()+'?mode=ro'+('&immutable=1' if immutable else ''),uri=True,isolation_level=None)
    db.execute('PRAGMA query_only=ON');return db


def open_state(root,*,manifest_sha256,identity,schedule,expected,checkpoint_root,deadline):
    root=Path(root).absolute()
    if root.resolve(strict=True)!=root or digest(root/'manifest.json')!=manifest_sha256:raise ValueError('Changed final state snapshot')
    manifest=json.loads((root/'manifest.json').read_bytes())
    if manifest['schema']!=1 or set(manifest['files'])!={name+'.sqlite' for name in NAMES}:raise ValueError('Invalid final state inventory')
    handles={}
    try:
        for name,cls in zip(NAMES,(Ledger,EvaluationQualityBarrier,PilotBarrier,Catalog)):
            path=root/(name+'.sqlite')
            if digest(path)!=manifest['files'][path.name]:raise ValueError('Changed final state database')
            handle=cls.__new__(cls);handle.db=readonly(path,immutable=True);handles[name]=handle
        ledger=handles['ledger'];contract=json.loads(ledger.db.execute("SELECT value FROM contract WHERE key='run'").fetchone()[0])
        wanted=dict(identity=identity,target_cap=schedule.target_cap,update_cap=6000,presentation_cap=3,deadline=deadline)
        if contract!=wanted:raise ValueError('Unbound final work ledger')
        ledger.target_cap=schedule.target_cap;ledger.update_cap=6000;ledger.presentation_cap=3;ledger.deadline=deadline
        if ledger.snapshot()!=manifest['ledger_snapshot']:raise ValueError('Final ledger snapshot differs')
        quality=handles['quality'];quality.identity=identity;quality.schedule=schedule
        if json.loads(quality.db.execute('SELECT contract FROM barrier WHERE id=1').fetchone()[0])!=dict(identity=identity,schedule_sha256=schedule.sha256):
            raise ValueError('Unbound final quality state')
        pilot=handles['pilot']
        if json.loads(pilot.db.execute('SELECT value FROM pilot_contract WHERE id=1').fetchone()[0])!=dict(run_identity=identity,schedule_hash=schedule.sha256,evaluation_hash=MANIFEST_SHA256):
            raise ValueError('Unbound final pilot decision')
        catalog=handles['catalog'];catalog.root=Path(checkpoint_root).absolute()
        if catalog.root.resolve(strict=True)!=catalog.root:raise ValueError('Redirected final checkpoint root')
        catalog.args=dict(identity=identity,expected=expected,shapes=None,schedule=schedule,ledger=ledger)
        stored=json.loads(catalog.db.execute('SELECT value FROM contract WHERE id=1').fetchone()[0])
        if {key:stored[key] for key in ('root','identity','expected','schedule')}!=dict(root=str(catalog.root),identity=identity,expected=expected,schedule=schedule.sha256):
            raise ValueError('Unbound final checkpoint catalog')
        catalog.args['shapes']=stored['shapes']
        return handles
    except BaseException:
        for handle in handles.values():handle.db.close()
        raise


def open_clock(path,*,identity,deadline):
    clock=TimeBudget.__new__(TimeBudget);clock.db=readonly(path,immutable=False)
    try:
        contract=json.loads(clock.db.execute('SELECT contract FROM budget WHERE id=1').fetchone()[0])
        if contract!=dict(identity=identity,seconds_cap=129600,deadline_utc=deadline):raise ValueError('Unbound live final clock')
        clock.cap=129600;clock.deadline=deadline;return clock
    except BaseException:clock.db.close();raise
