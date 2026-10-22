"""Scoped candidate worker. Requires a parent-bound single-use ticket.

No standalone configuration, legacy checkpoint input or environment bypass.
Parent launcher must own custody, supervision, fresh control checks and phase.
"""
import hashlib,json,math,os,sqlite3,sys,time
from pathlib import Path
from . import candidate_snapshot
from .supervisor import atomic_json


def preflight(path,pin,*,now=None):
    now=time.time() if now is None else now;path=Path(path).absolute();raw=path.read_bytes()
    if path.resolve(strict=True)!=path or hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Changed worker ticket')
    t=json.loads(raw)
    keys={'schema','project','output','snapshot_sha256','identity','parent_pid','phase','checkpoint','checkpoint_sha256','deadline','active_ceiling'}
    if set(t)!=keys or type(t['schema']) is not int or t['schema']!=1:raise ValueError('Invalid worker ticket')
    if type(t['parent_pid']) is not int or t['parent_pid']!=os.getppid():raise ValueError('Unowned worker parent')
    project=Path(t['project']).resolve(strict=True);output=Path(t['output']).absolute()
    if (output.resolve(strict=True)!=output or output!=project/'restart/execution-v1/candidate-run-v1'
            or path.parent!=output):raise ValueError('Unowned candidate output')
    bound=candidate_snapshot.verify(project,output/'snapshot.json',expected_sha256=t['snapshot_sha256'],now=now)
    if t['identity']!='candidate-v1:'+t['snapshot_sha256']:raise ValueError('Unbound candidate identity')
    if t['phase'] not in ('pilot','continuation','pilot-recovery','continuation-recovery'):raise ValueError('Unknown candidate phase')
    ceiling=7200 if t['phase'].split('-')[0]=='pilot' else 129600
    if type(t['active_ceiling']) is not int or t['active_ceiling']!=ceiling:raise ValueError('Changed stage ceiling')
    if t['deadline']!=bound['original_deadline'] or not now<t['deadline']:raise ValueError('Changed/expired original deadline')
    db=sqlite3.connect((output/'time.sqlite').as_uri()+'?mode=ro',uri=True)
    try:row=db.execute('SELECT contract,charged,terminal FROM budget WHERE id=1').fetchone()
    finally:db.close()
    expected={'identity':t['identity'],'seconds_cap':129600,'deadline_utc':t['deadline']}
    if row is None or json.loads(row[0])!=expected or row[2] is not None or not 0<row[1]<=ceiling:
        raise ValueError('Unreserved/terminal/mismatched supervisor clock')
    if t['phase']=='pilot':
        if t['checkpoint'] is not None or t['checkpoint_sha256'] is not None:raise ValueError('Initial candidate must start from scratch')
    else:
        checkpoint=Path(t['checkpoint']).absolute()
        if (checkpoint.resolve(strict=True)!=checkpoint or checkpoint.parent!=output/'checkpoints'
                or hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest()!=t['checkpoint_sha256']):
            raise ValueError('Unowned/changed continuation checkpoint')
        if t['phase'].endswith('-recovery'):
            original=t['phase'].removesuffix('-recovery')
            prior_path=output/(original+'-ticket.json')
            prior=json.loads(prior_path.read_bytes())
            started=json.loads((output/(original+'-worker-started.json')).read_bytes())
            if (started['ticket_sha256']!=hashlib.sha256(prior_path.read_bytes()).hexdigest()
                    or any(prior[k]!=t[k] for k in ('project','output','snapshot_sha256','identity','deadline','active_ceiling'))
                    or prior['phase']!=original):raise ValueError('Recovery does not match original dispatch')
            if any((output/name).exists() for name in (original+'-completion.json',original+'-supervisor.json','parent-stop.json','worker-stop.json')):
                raise ValueError('Completed or stopped dispatch cannot recover')
            if not (output/'initialization-complete.json').is_file():raise ValueError('No completed original initialization')
        else:
            pilot_phase='pilot-recovery' if (output/'pilot-recovery-ticket.json').exists() else 'pilot'
            completion=json.loads((output/(pilot_phase+'-completion.json')).read_bytes())
            if completion.get('status')!='PILOT_PASS' or completion.get('targets')!=2000000 or completion.get('checkpoint')!=str(checkpoint):
                raise ValueError('No successful pilot completion for checkpoint')
    marker=output/(t['phase']+'-worker-started.json')
    with marker.open('x') as f:
        json.dump({'pid':os.getpid(),'parent_pid':os.getppid(),'ticket_sha256':pin},f);f.flush();os.fsync(f.fileno())
    return t


def _fresh(config):
    import numpy as np
    if config.parameter_count!=5114112:raise ValueError('Only the approved candidate can initialize')
    rng=np.random.default_rng(42);weights={}
    for name,shape in config.shapes().items():
        if len(shape)==1:weights[name]=np.ones(shape,dtype=np.float32)
        else:
            std=.02/math.sqrt(2*config.num_layers) if name.endswith(('.o','.down')) else .02
            weights[name]=rng.normal(0,std,shape).astype(np.float32)
    return weights,rng


def restore_progress(t,*,quality,pilot,config,schedule,ledger,expected,clock,**recovery_checks):
    """Validate phase and consume at most one reboot restore before native loading."""
    from . import checkpoint_binding,interruption_recovery
    recovery=t['phase'].endswith('-recovery');phase=t['phase'].split('-')[0]
    decision=pilot.decision()
    if phase=='continuation' and (decision is None or decision['result']['status']!='PILOT_METRIC_RULES_PASS'):
        raise ValueError('Continuation lacks persisted pilot acceptance')
    if not recovery and (phase!='continuation' or decision['checkpoint_sha256']!=t['checkpoint_sha256']):
        raise ValueError('Continuation checkpoint differs from pilot acceptance')
    args=dict(shapes=config.shapes(),schedule=schedule,ledger=ledger,identity=t['identity'],expected=expected)
    if recovery:
        restored,receipt=interruption_recovery.recover(quality,checkpoint=t['checkpoint'],
            checkpoint_root=Path(t['output'])/'checkpoints',manifest_sha256=t['checkpoint_sha256'],
            time_budget=clock,**args,**recovery_checks)
        atomic_json(Path(t['output'])/'recovery-consumed.json',receipt)
    else:
        restored=checkpoint_binding.restore(t['checkpoint'],**args)
        if restored['metadata']['targets']!=2000000 or any(restored['charged_work_after_checkpoint'].values()):
            raise ValueError('Continuation checkpoint has unexpected progress/tail')
    targets=restored['metadata']['targets']
    if (phase=='pilot' and targets>2000000) or (phase=='continuation' and targets<2000000):
        raise ValueError('Recovered progress crosses authorized phase')
    return restored


def execute(path,pin):
    t=preflight(path,pin)
    from slm.common.config import Config
    from slm.backends import mlx_backend as backend
    from .token_store import TrainingTokens
    from .schedule import Schedule
    from .ledger import Ledger
    from .monitor import Monitor
    from .supervisor import TimeBudget
    from .evaluation_quality import EvaluationQualityBarrier
    from .pilot_barrier import PilotBarrier
    from .pilot_evidence import Measurements
    from .checkpoint_catalog import Catalog
    from .interruption_recovery import register
    from . import checkpoint_binding
    from .candidate_loop import Loop
    from .numerical_prerequisites import PINS
    from .evaluation_snapshot import MANIFEST_SHA256
    import mlx.core as mx
    project=Path(t['project']);output=Path(t['output']);base=project/'restart/execution-v1';handles=[]
    clock=TimeBudget(output/'time.sqlite',identity=t['identity'],seconds_cap=129600,deadline_utc=t['deadline'])
    quality=None
    try:
        policy=json.loads((project/'restart/approval-v1/policy.json').read_bytes());config=Config(**policy['architecture'])
        store=TrainingTokens(base/'data-train',manifest_sha256=PINS['data-train/manifest.json'])
        schedule=Schedule((base/'batch-schedule-draft-v3/updates.jsonl').read_bytes(),expected_sha256=candidate_snapshot.SCHEDULE,
                          document_targets={k:v['targets'] for k,v in store._index.items()})
        ledger=Ledger(output/'exposures.sqlite',t['identity'],target_cap=schedule.target_cap,update_cap=6000,presentation_cap=3,deadline=t['deadline']);handles.append(ledger)
        quality=EvaluationQualityBarrier(output/'quality.sqlite',identity=t['identity'],schedule=schedule);handles.append(quality)
        pilot=PilotBarrier(output/'pilot.sqlite',run_identity=t['identity'],schedule_hash=schedule.sha256,evaluation_hash=MANIFEST_SHA256);handles.append(pilot)
        measurements=Measurements(output/'measurements.sqlite',identity=t['identity'],schedule=schedule);handles.append(measurements)
        expected={'code_hash':t['snapshot_sha256'],'tokenizer_hash':PINS['tokenizer-8192/manifest.json'],
                  'config_hash':hashlib.sha256(json.dumps(config.to_dict(),sort_keys=True).encode()).hexdigest()}
        (output/'checkpoints').mkdir(exist_ok=True)
        catalog=Catalog(output/'catalog.sqlite',root=output/'checkpoints',identity=t['identity'],expected=expected,
                        shapes=config.shapes(),schedule=schedule,ledger=ledger);handles.append(catalog)
        def heartbeat():atomic_json(output/(t['phase']+'-heartbeat.json'),{'pid':os.getpid(),'monotonic':time.monotonic()})
        heartbeat()
        if t['phase']=='pilot':
            if ledger.totals()['updates_reserved'] or quality.position()!=0 or pilot.decision() is not None:
                raise ValueError('Initial candidate state is not empty')
            register(quality)
            # Exclusive marker exists before the first random weight is allocated.
            with (output/'initialization-started.json').open('x') as f:
                json.dump({'parameters':5114112,'seed':42,'snapshot_sha256':t['snapshot_sha256']},f);f.flush();os.fsync(f.fileno())
            weights,rng=_fresh(config);params=backend.load(config,weights);moments={};monitor=Monitor();step=targets=0
            mx.eval(params)
            atomic_json(output/'initialization-complete.json',{'parameters':config.parameter_count,'seed':42,
                'parameter_sha256':{k:hashlib.sha256(v.tobytes()).hexdigest() for k,v in weights.items()}})
            del weights
        else:
            restored=restore_progress(t,quality=quality,pilot=pilot,config=config,schedule=schedule,
                ledger=ledger,expected=expected,clock=clock)
            a=restored['arrays'];params=backend.load(config,{k:a['parameter:'+k] for k in config.shapes()})
            moments={} if restored['metadata']['step']==0 else {k:(mx.array(a['first_moment:'+k]),mx.array(a['second_moment:'+k])) for k in config.shapes()}
            monitor=quality.overlay(restored['monitor']);rng=restored['rng'];step=restored['metadata']['step'];targets=restored['metadata']['targets']
        loop=Loop(project=project,output=output,identity=t['identity'],expected=expected,config=config,schedule=schedule,
                  store=store,ledger=ledger,quality=quality,pilot=pilot,catalog=catalog,measurements=measurements,time_budget=clock,
                  backend=backend,params=params,moments=moments,monitor=monitor,rng=rng,step=step,targets=targets,
                  heartbeat=heartbeat,experiment_start=t['deadline']-259200)
        if t['phase']!='pilot':loop.checkpoint_path=Path(t['checkpoint'])
        result=loop.run(stop_after_pilot=t['phase'].split('-')[0]=='pilot')
        atomic_json(output/(t['phase']+'-completion.json'),result)
        return result
    except BaseException as error:
        reason=type(error).__name__+': '+str(error);clock.stop(reason)
        if quality is not None:quality.db.execute('UPDATE barrier SET terminal=coalesce(terminal,?) WHERE id=1',(reason,))
        atomic_json(output/'worker-stop.json',{'status':'STOP','reason':reason,'phase':t['phase']})
        raise
    finally:
        for handle in reversed(handles):handle.close()
        clock.db.close()

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Parent-bound ticket path and hash required')
    execute(sys.argv[1],sys.argv[2])
