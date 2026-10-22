"""Immutable code/input binding for the numerical launcher; no execution permit.

Freeze only after launcher implementation is complete. A launcher must retain
and verify the returned manifest hash, not trust a replacement manifest's claims.
"""
import datetime,hashlib,importlib.metadata,json,math,os,sys
from pathlib import Path
from .evaluation_snapshot import _file

PLAN='f28fe053616946c7b3f10571a05ab564915d790229df239675cabf9098ea8252'
POLICY='a7487bb971d6d33d1113c01c610282d8035b099e5a08da311990187ff34b2a32'
FIXTURES={
 'contract.json':'fa566ff3ae85b69c5f6e6813f64ff40917f541387637fe7f7d000f5bfca19f42',
 'batches.json':'6e2de8251f5a5aa6fbe224892dbdef334d3eeba081291809d9978b5019d8a5c5',
 'long-documents.json':'2361b401651f0f0628578c47f2728f1b20560275632d696959a48ecc32540afb'}
BASE='restart/execution-v1/'
FIXTURE_ROOT=BASE+'numerical-fixtures-v1/'
REVISION_ROOT=BASE+'numerical-revision-proposal-v2/'
REVISION_PINS={'proposal.json':'349316e47bc1698a73f183f475b2c2a7d6cc9f7e94267ec25df07495a313f0f5','authorization.json':'97f02315348914013cd4296c45b49683b549dcbd1023342f8c1f3a0af79233c8'}
PACKAGES=('numpy','mlx','torch','safetensors')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def environment():
    return {'python':sys.version,'executable':str(Path(sys.executable).resolve()),
            'packages':{name:importlib.metadata.version(name) for name in PACKAGES}}


def authority(project,now):
    if type(now) not in (int,float) or not math.isfinite(now):raise ValueError('Invalid wall clock')
    for name,pin in [('PLAN.md',PLAN),('policy.json',POLICY)]:
        if digest(_file(project,'restart/approval-v1/'+name))!=pin:raise ValueError('Changed approved plan/policy')
    approval=json.loads(_file(project,BASE+'authorization.json').read_bytes())
    if (approval.get('owner')!='Navneet Prabhakar' or approval.get('authorization_text')!='ok start with M0-M3'
        or approval.get('scope')!=['M0','M1','M2','M3'] or approval.get('M1_plan_sha256')!=PLAN
        or approval.get('M1_policy_sha256')!=POLICY or approval.get('M1_elapsed_cap_seconds')!=259200
        or approval.get('M1_execution_started_at_utc')!='2026-10-21T04:35:21.314878+00:00'):
        raise ValueError('Missing or mismatched owner authorization')
    start=datetime.datetime.fromisoformat(approval['M1_execution_started_at_utc']).timestamp()
    if not start<=now<start+259200:raise ValueError('Original experiment elapsed budget unavailable')
    for name,pin in FIXTURES.items():
        if digest(_file(project,FIXTURE_ROOT+name))!=pin:raise ValueError('Changed numerical fixture/recipe')
    for name,pin in REVISION_PINS.items():
        if digest(_file(project,REVISION_ROOT+name))!=pin:raise ValueError('Missing or changed bounded revision authorization')
    return start+259200


def inventory(project):
    code=sorted(str(p.relative_to(project)) for p in (project/'src/slm').rglob('*.py'))
    if 'src/slm/restart/numerical_snapshot.py' not in code:raise ValueError('Missing numerical binding code')
    tests=sorted(str(p.relative_to(project)) for p in (project/'tests').glob('test_restart_*.py'))
    return code+tests+['restart/approval-v1/PLAN.md','restart/approval-v1/policy.json',BASE+'authorization.json']+[FIXTURE_ROOT+name for name in sorted(FIXTURES)]+[REVISION_ROOT+name for name in sorted(REVISION_PINS)]


def freeze(project,destination,*,now):
    project=Path(project).resolve(strict=True);destination=Path(destination)
    deadline=authority(project,now)
    content={'schema':1,'purpose':'numerical-only-code-input-snapshot','experiment_deadline':deadline,
             'environment':environment(),'files':{p:digest(_file(project,p)) for p in inventory(project)},
             'training_authorized_by_this_check':False}
    raw=(json.dumps(content,indent=2,sort_keys=True)+'\n').encode()
    # Exclusive creation: do not replace a frozen attempt with newly selected code.
    with destination.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return hashlib.sha256(raw).hexdigest()


def verify(project,manifest,*,expected_sha256,now):
    project=Path(project).resolve(strict=True)
    deadline=authority(project,now)
    raw=Path(manifest).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('Changed numerical code manifest')
    data=json.loads(raw)
    if (data.get('schema')!=1 or data.get('purpose')!='numerical-only-code-input-snapshot'
        or data.get('experiment_deadline')!=deadline or data.get('environment')!=environment()
        or data.get('training_authorized_by_this_check') is not False):raise ValueError('Changed execution contract/environment')
    if set(data.get('files',{}))!=set(inventory(project)):raise ValueError('Changed Python/input inventory')
    for relative,pin in data['files'].items():
        if digest(_file(project,relative))!=pin:raise ValueError('Changed numerical code/input: '+relative)
    return {'experiment_deadline':deadline,'manifest_sha256':expected_sha256,
            'fixture_root':str(project/FIXTURE_ROOT),'training_authorized_by_this_check':False}
