"""Parent prerequisite checks and immutable candidate code/input binding.

No model allocation or launcher. Freeze only after lifecycle implementation and
fresh controls finish; worker verification needs no final-test file access.
"""
import hashlib,json,os
from pathlib import Path
from . import numerical_snapshot,numerical_prerequisites,candidate_custody
from .evaluation_snapshot import _file
from .schedule import Schedule
from .token_store import TrainingTokens

NUMERICAL_RESULT='c71501918884c88a07d8dd8b5092887bb1b864130ff5749b95f013013855eb1f'
NUMERICAL_SNAPSHOT='c421a72e71f2e650b52e499657106d8c465c5304585b364d19d51ea25ae3996a'
SCHEDULE='9e11be8bf9b4dee66ec7b0d36099597a789554721c1a346b925a0d5128ed1c83'
CORE=('src/slm/common/config.py','src/slm/backends/mlx_backend.py','src/slm/backends/torch_backend.py',
      'src/slm/restart/accumulation.py','src/slm/restart/segments.py','src/slm/restart/monitor.py')


def inventory(project):
    project=Path(project).resolve(strict=True)
    files=list((project/'src/slm').rglob('*.py'))+list((project/'tests').glob('test_restart_*.py'))
    files+=candidate_custody.readable_files(project)
    return sorted({str(p.relative_to(project)) for p in files})


def preflight(project,*,now):
    project=Path(project).resolve(strict=True);base=project/'restart/execution-v1'
    deadline=numerical_snapshot.authority(project,now)
    prerequisites=numerical_prerequisites.verify(project)
    from .known_leakage import verify as verify_known_leakage
    leakage=verify_known_leakage(project)
    run=base/'numerical-run-v2'
    if numerical_snapshot.digest(_file(run,'result.json'))!=NUMERICAL_RESULT:
        raise ValueError('Changed numerical result')
    if numerical_snapshot.digest(_file(run,'snapshot.json'))!=NUMERICAL_SNAPSHOT:
        raise ValueError('Changed historical numerical snapshot')
    result=json.loads((run/'result.json').read_bytes());snapshot=json.loads((run/'snapshot.json').read_bytes())
    if result['passed_cases']!=40 or result['reported_cases']!=40 or result['failed'] or result['missing']:
        raise ValueError('Numerical gate incomplete')
    names={'progress':'progress.json','inputs':'integrity-inputs.json','supervisor':'supervisor.json','trajectory':'trajectory-evidence.json'}
    for key,name in names.items():
        if numerical_snapshot.digest(_file(run,name))!=result['evidence_sha256'][key]:raise ValueError('Changed numerical evidence')
    # Historical orchestration differs as lifecycle implementation advances. Core
    # numerical code must still be exactly the version exercised by the toy pass.
    for relative in CORE:
        if numerical_snapshot.digest(_file(project,relative))!=snapshot['files'][relative]:
            raise ValueError('Numerically tested core changed: '+relative)
    for relative,pin in snapshot['files'].items():
        if numerical_snapshot.digest(_file(base/'numerical-v2-source-archive',relative))!=pin:
            raise ValueError('Historical numerical archive changed')
    store=TrainingTokens(base/'data-train',manifest_sha256=numerical_prerequisites.PINS['data-train/manifest.json'])
    raw=_file(base,'batch-schedule-draft-v3/updates.jsonl').read_bytes()
    schedule=Schedule(raw,expected_sha256=SCHEDULE,document_targets={k:v['targets'] for k,v in store._index.items()})
    if schedule.target_cap!=43409847 or len(schedule.updates)!=5383:raise ValueError('Changed candidate schedule bounds')
    return {'status':'PARENT_PREREQUISITES_VERIFIED','original_deadline':deadline,
            'numerical_result_sha256':NUMERICAL_RESULT,'numerical_snapshot_sha256':NUMERICAL_SNAPSHOT,
            'schedule_sha256':SCHEDULE,'target_cap':schedule.target_cap,'scheduled_updates':len(schedule.updates),
            'environment':numerical_snapshot.environment(),'prerequisites':prerequisites,'known_leakage':leakage,
            'model_initialized':False}


def freeze(project,destination,*,now):
    project=Path(project).resolve(strict=True);receipt=preflight(project,now=now)
    payload={'schema':1,'purpose':'candidate-code-input-binding','preflight':receipt,
             'files':{p:numerical_snapshot.digest(_file(project,p)) for p in inventory(project)}}
    raw=(json.dumps(payload,sort_keys=True,indent=2)+'\n').encode()
    with Path(destination).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return hashlib.sha256(raw).hexdigest()


def verify(project,path,*,expected_sha256,now):
    project=Path(project).resolve(strict=True)
    deadline=numerical_snapshot.authority(project,now)
    raw=Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256:raise ValueError('Changed candidate manifest')
    payload=json.loads(raw);p=payload['preflight']
    if (payload.get('schema')!=1 or payload.get('purpose')!='candidate-code-input-binding'
            or p.get('original_deadline')!=deadline or p.get('environment')!=numerical_snapshot.environment()
            or p.get('numerical_result_sha256')!=NUMERICAL_RESULT or p.get('schedule_sha256')!=SCHEDULE):
        raise ValueError('Changed candidate execution contract')
    if set(payload['files'])!=set(inventory(project)):raise ValueError('Changed candidate inventory')
    for relative,pin in payload['files'].items():
        if numerical_snapshot.digest(_file(project,relative))!=pin:raise ValueError('Changed candidate code/input: '+relative)
    return p
