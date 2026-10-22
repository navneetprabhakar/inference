"""Parent stage-launch primitives. No automatic run entrypoint yet.

Do not invoke until recovery and final-evaluation lifecycle gates are integrated.
Preparing reserves the sole candidate directory; never reuses a partial attempt.
"""
import hashlib,json,os,re,shutil,sqlite3,subprocess,sys,time
from pathlib import Path
from . import candidate_snapshot,candidate_custody,custody
from .supervisor import TimeBudget,supervise,atomic_json
from .pilot_barrier import PilotBarrier
from .evaluation_snapshot import MANIFEST_SHA256


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prepare(project):
    project=Path(project).resolve(strict=True);output=project/'restart/execution-v1/candidate-run-v1'
    if sys.platform!='darwin' or Path(sys.executable).absolute()!=project/'.venv/bin/python':
        raise ValueError('Project virtual environment on macOS required')
    if output.exists():raise FileExistsError('Sole candidate attempt already reserved')
    prerequisites=candidate_snapshot.preflight(project,now=time.time())
    inventory=candidate_snapshot.inventory(project);before={p:digest(project/p) for p in inventory}
    tests=sorted(str(p.relative_to(project)) for p in (project/'tests').glob('test_restart_*.py'))
    if not tests:raise ValueError('No control tests')
    checked=subprocess.run([sys.executable,'-m','pytest','-q',*tests],cwd=project,
        env=dict(os.environ,PYTHONPATH=str(project/'src'),PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=300)
    if (checked.returncode or not re.search(r'\b\d+ passed\b',checked.stdout)
            or re.search(r'\b(skipped|xfailed|xpassed|failed|error)\b',checked.stdout)):
        raise ValueError('Fresh controls incomplete or failed: '+checked.stdout[-3000:]+checked.stderr[-1000:])
    if inventory!=candidate_snapshot.inventory(project) or before!={p:digest(project/p) for p in inventory}:
        raise ValueError('Code/input changed during controls')
    if shutil.disk_usage(project).free<20*1024**3:raise ValueError('Disk reserve unavailable')
    output.mkdir()
    atomic_json(output/'controls.json',{'stdout':checked.stdout,'stderr':checked.stderr,'exit_code':checked.returncode,'files_sha256':before})
    pin=candidate_snapshot.freeze(project,output/'snapshot.json',now=time.time())
    profile=candidate_custody.profile(project,output);(output/'worker.sb').write_text(profile)
    binding={'project':str(project),'output':str(output),'snapshot_sha256':pin,'identity':'candidate-v1:'+pin,
             'deadline':prerequisites['original_deadline'],'profile_sha256':digest(output/'worker.sb')}
    atomic_json(output/'parent-binding.json',binding)
    return binding


def environment(project,output):
    return dict(PATH='/usr/bin:/bin',PYTHONPATH=str(project/'src'),PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(output),OMP_NUM_THREADS='1',MKL_NUM_THREADS='1')


def probe(binding):
    project=Path(binding['project']);output=Path(binding['output'])
    forbidden=[project/'restart/execution-v1/evaluation-frozen-v1/final'/f'{s}.jsonl' for s in ('grammar','grounded','narrative','copy')]
    forbidden += [project/'restart/execution-v1/data-final/tokens.u16',project/'restart/corpus-audit-v1/audit.sqlite']
    script='''import json,pathlib,socket,sys
from slm.restart.candidate_evaluation import inputs
from slm.restart.candidate_snapshot import verify
project=pathlib.Path(sys.argv[1]);output=pathlib.Path(sys.argv[2])
verify(project,output/'snapshot.json',expected_sha256=sys.argv[3],now=__import__('time').time())
for event in ('dev_loss_checkpoint','full_development_diagnostics','copying_probes'):inputs(project,event)
for path in json.loads(sys.argv[4]):
 try:pathlib.Path(path).read_bytes()
 except PermissionError:pass
 else:raise RuntimeError('Forbidden final/source read allowed')
s=socket.socket()
try:s.bind(('127.0.0.1',0))
except PermissionError:pass
else:raise RuntimeError('Network allowed')
finally:s.close()
'''
    result=subprocess.run(custody.command(output/'worker.sb',[sys.executable,'-c',script,str(project),str(output),binding['snapshot_sha256'],json.dumps(list(map(str,forbidden)))]),
                          cwd=output,env=environment(project,output),capture_output=True,text=True,timeout=60)
    atomic_json(output/'launch-custody-probe.json',{'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,
        'profile_sha256':digest(output/'worker.sb'),'denied_paths':list(map(str,forbidden))})
    if result.returncode:raise ValueError('Candidate custody preflight failed: '+result.stderr)


def recovery_checkpoint(binding,phase):
    """Select the latest catalogued checkpoint; never retry a closed dispatch."""
    from .interruption_recovery import boot_identity
    output=Path(binding['output']);original=phase.removesuffix('-recovery')
    if original not in ('pilot','continuation') or original==phase:raise ValueError('Invalid recovery phase')
    if any((output/name).exists() for name in (original+'-completion.json',original+'-supervisor.json','parent-stop.json','worker-stop.json','recovery-consumed.json')):
        raise ValueError('Closed dispatch or consumed recovery')
    prior_path=output/(original+'-ticket.json');prior=json.loads(prior_path.read_bytes())
    started=json.loads((output/(original+'-worker-started.json')).read_bytes())
    if (started['ticket_sha256']!=digest(prior_path) or prior['phase']!=original
            or any(prior[k]!=binding[k] for k in ('project','output','snapshot_sha256','identity','deadline'))):
        raise ValueError('Recovery original dispatch changed')
    # Read-only boot proof before reserving a recovery ticket or launching a worker.
    quality=sqlite3.connect((output/'quality.sqlite').as_uri()+'?mode=ro',uri=True)
    try:
        step,terminal=quality.execute('SELECT step,terminal FROM barrier WHERE id=1').fetchone()
        original_boot,consumed=quality.execute('SELECT original_boot,recovery FROM interruption WHERE id=1').fetchone()
    finally:quality.close()
    before=json.loads(original_boot);after=boot_identity()
    if (terminal is not None or consumed is not None or before['host']!=after['host']
            or (after['boot_seconds'],after['boot_microseconds'])<=(before['boot_seconds'],before['boot_microseconds'])
            or after['boot_seconds']>time.time()):raise ValueError('No eligible verified reboot')
    catalog=sqlite3.connect((output/'catalog.sqlite').as_uri()+'?mode=ro',uri=True)
    try:row=catalog.execute("SELECT name,pin,step FROM checkpoints WHERE status='retained' ORDER BY seq DESC LIMIT 1").fetchone()
    finally:catalog.close()
    if row is None or row[2]>step:raise ValueError('No complete recovery checkpoint')
    path=output/'checkpoints'/row[0]
    if path.parent!=output/'checkpoints' or path.resolve(strict=True)!=path or digest(path/'manifest.json')!=row[1]:
        raise ValueError('Unowned/changed recovery checkpoint')
    return path,row[1]


def stage(binding,phase):
    if phase not in ('pilot','continuation','pilot-recovery','continuation-recovery'):raise ValueError('Unknown candidate phase')
    project=Path(binding['project']);output=Path(binding['output'])
    bound=candidate_snapshot.verify(project,output/'snapshot.json',expected_sha256=binding['snapshot_sha256'],now=time.time())
    if (output!=project/'restart/execution-v1/candidate-run-v1' or output.resolve(strict=True)!=output
            or binding['identity']!='candidate-v1:'+binding['snapshot_sha256'] or binding['deadline']!=bound['original_deadline']):
        raise ValueError('Changed parent binding')
    if digest(output/'worker.sb')!=binding['profile_sha256'] or (output/'worker.sb').read_text()!=candidate_custody.profile(project,output):
        raise ValueError('Changed custody profile')
    ticket_path=output/(phase+'-ticket.json')
    if ticket_path.exists():raise FileExistsError('Stage already dispatched; no automatic retry')
    checkpoint=checkpoint_pin=None
    if phase=='continuation':
        pilot_phase='pilot-recovery' if (output/'pilot-recovery-ticket.json').exists() else 'pilot'
        prior=json.loads((output/(pilot_phase+'-supervisor.json')).read_bytes());completion=json.loads((output/(pilot_phase+'-completion.json')).read_bytes())
        if prior['status']!='PASS' or completion['status']!='PILOT_PASS' or completion['targets']!=2000000:raise ValueError('Pilot not accepted')
        checkpoint=Path(completion['checkpoint'])
        if checkpoint.parent!=output/'checkpoints' or checkpoint.resolve(strict=True)!=checkpoint:raise ValueError('Unowned pilot checkpoint')
        checkpoint_pin=digest(checkpoint/'manifest.json')
        if not (output/'pilot.sqlite').is_file():raise ValueError('Missing persistent pilot decision')
        pilot=PilotBarrier(output/'pilot.sqlite',run_identity=binding['identity'],schedule_hash=candidate_snapshot.SCHEDULE,evaluation_hash=MANIFEST_SHA256)
        try:decision=pilot.decision()
        finally:pilot.close()
        if decision is None or decision['result']['status']!='PILOT_METRIC_RULES_PASS' or decision['checkpoint_sha256']!=checkpoint_pin:
            raise ValueError('Persisted pilot decision does not authorize continuation')
    if phase.endswith('-recovery'):
        checkpoint,checkpoint_pin=recovery_checkpoint(binding,phase)
    ceiling=7200 if phase.split('-')[0]=='pilot' else 129600
    ticket={k:binding[k] for k in ('project','output','snapshot_sha256','identity','deadline')}
    ticket.update(schema=1,parent_pid=os.getpid(),phase=phase,checkpoint=str(checkpoint) if checkpoint else None,
                  checkpoint_sha256=checkpoint_pin,active_ceiling=ceiling)
    with ticket_path.open('x') as f:json.dump(ticket,f,indent=2);f.flush();os.fsync(f.fileno())
    clock=TimeBudget(output/'time.sqlite',identity=binding['identity'],seconds_cap=129600,deadline_utc=binding['deadline'])
    try:
        probe(binding)
        candidate_snapshot.verify(project,output/'snapshot.json',expected_sha256=binding['snapshot_sha256'],now=time.time())
        result=supervise(custody.command(output/'worker.sb',[sys.executable,'-m','slm.restart.candidate_worker',str(ticket_path),digest(ticket_path)]),
            cwd=output,env=environment(project,output),heartbeat=output/(phase+'-heartbeat.json'),budget=clock,
            receipt=output/(phase+'-supervisor.json'),active_ceiling=ceiling)
        if result['status']!='PASS':raise ValueError('Worker did not complete: '+result['reason'])
        completion=json.loads((output/(phase+'-completion.json')).read_bytes())
        expected='PILOT_PASS' if phase.split('-')[0]=='pilot' else 'NORMAL_BUDGET_END'
        targets=2000000 if phase.split('-')[0]=='pilot' else bound['target_cap']
        status=completion.get('status')
        clean=status in ('PLATEAU_END','WORK_BUDGET_END','PILOT_BUDGET_END')
        if clean:
            count=completion.get('targets');pilot_end=status=='PILOT_BUDGET_END'
            if (type(count) is not int or (pilot_end and (phase.split('-')[0]!='pilot' or not 0<=count<2000000))
                    or (not pilot_end and (phase.split('-')[0]!='continuation' or not 2000000<=count<=bound['target_cap']))):
                raise ValueError('Invalid clean-stop boundary')
            db=sqlite3.connect((output/'quality.sqlite').as_uri()+'?mode=ro',uri=True)
            try:
                terminal=db.execute('SELECT terminal FROM barrier WHERE id=1').fetchone()[0]
                copy=db.execute('SELECT copy_raw,copy_pin,receipt FROM clean_stop WHERE id=1').fetchone()
            finally:db.close()
            reason='development plateau' if status=='PLATEAU_END' else 'work budget exhausted'
            if terminal!=reason or copy is None or copy[0] is None or hashlib.sha256(copy[0]).hexdigest()!=copy[1]:
                raise ValueError('Unverified clean-stop termination copying')
            stop=json.loads(copy[2]);context=json.loads(copy[0])['context']
            checkpoint=Path(completion['checkpoint'])
            if (stop['reason']!=reason or context!=dict(stop['context'],event='copying_probes')
                    or context['identity']!=binding['identity'] or context['schedule_sha256']!=candidate_snapshot.SCHEDULE
                    or context['targets']!=count or context['step']!=completion['step']
                    or checkpoint.parent!=output/'checkpoints' or checkpoint.resolve(strict=True)!=checkpoint
                    or context['checkpoint_sha256']!=digest(checkpoint/'manifest.json')):
                raise ValueError('Clean-stop completion differs from copying evidence')
            if reason=='work budget exhausted':
                from .ledger import Ledger
                ledger=Ledger(output/'exposures.sqlite',binding['identity'],target_cap=bound['target_cap'],
                    update_cap=6000,presentation_cap=3,deadline=binding['deadline'])
                try:ledger.verify_exhaustion(stop['exhaustion'])
                finally:ledger.close()
        if (not clean and (status!=expected or completion.get('targets')!=targets)) or clock.terminal() is not None:
            raise ValueError('Unverified candidate stage completion')
        return completion
    except BaseException as error:
        clock.stop(str(error));atomic_json(output/'parent-stop.json',{'phase':phase,'reason':str(error),'status':'STOP'});raise
    finally:clock.db.close()
