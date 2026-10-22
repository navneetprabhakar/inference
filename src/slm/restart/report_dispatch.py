"""Single-use supervised post-holdout assessment; never initializes a model.

The reporting sandbox may read project audit evidence after final scoring. Writes
are confined to its own results; original training/evaluation state is read-only.
"""
import hashlib,json,os,sys,time
from pathlib import Path
from . import candidate_snapshot,custody,final_state,research_report,delivery
from .candidate_launch import environment
from .supervisor import TimeBudget,supervise,atomic_json,verify_resource_history


def profile(project,candidate,output):
    project=Path(project).resolve(strict=True);candidate=Path(candidate).absolute();output=Path(output).absolute()
    if (candidate!=project/'restart/execution-v1/candidate-run-v1' or candidate.resolve(strict=True)!=candidate
            or output!=candidate/'report-run-v1' or output.resolve(strict=True)!=output):
        raise ValueError('Unowned report directories')
    return custody.profile(read_roots=custody.runtime_roots(project)+[project],write_root=output)


def preflight(path,pin):
    path=Path(path).absolute()
    if path.resolve(strict=True)!=path or final_state.digest(path)!=pin:raise ValueError('Changed report ticket')
    t=json.loads(path.read_bytes())
    keys={'schema','project','candidate','output','identity','snapshot_sha256','deadline','parent_pid','reviews_sha256','profile_sha256'}
    if set(t)!=keys or type(t['schema']) is not int or t['schema']!=1 or type(t['parent_pid']) is not int or t['parent_pid']!=os.getppid():
        raise ValueError('Unowned report ticket')
    project=Path(t['project']).resolve(strict=True);candidate=Path(t['candidate']).absolute();output=Path(t['output']).absolute()
    expected=profile(project,candidate,output)
    if path!=candidate/'report-ticket.json':raise ValueError('Unowned report ticket path')
    binding=json.loads((candidate/'parent-binding.json').read_bytes())
    if any(t[k]!=binding[k] for k in ('identity','snapshot_sha256','deadline')):raise ValueError('Changed report binding')
    bound=candidate_snapshot.verify(project,candidate/'snapshot.json',expected_sha256=t['snapshot_sha256'],now=time.time())
    if t['identity']!='candidate-v1:'+t['snapshot_sha256'] or t['deadline']!=bound['original_deadline']:raise ValueError('Changed report authority')
    if ((candidate/'report-worker.sb').read_text()!=expected or final_state.digest(candidate/'report-worker.sb')!=t['profile_sha256']
            or final_state.digest(output/'reviews.json')!=t['reviews_sha256']):raise ValueError('Changed report inputs/custody')
    clock=final_state.open_clock(candidate/'time.sqlite',identity=t['identity'],deadline=t['deadline'])
    try:
        if clock.terminal() is not None or not 0<clock.charged()<clock.cap or time.time()>=clock.deadline:
            raise ValueError('Report clock unavailable')
    finally:clock.db.close()
    with (output/'worker-started.json').open('x') as f:
        json.dump(dict(pid=os.getpid(),parent_pid=os.getppid(),ticket_sha256=pin),f);f.flush();os.fsync(f.fileno())
    return t


def execute(path,pin):
    t=preflight(path,pin);project=Path(t['project']);candidate=Path(t['candidate']);output=Path(t['output'])
    handles={};clock=None
    try:
        from slm.common.config import Config
        from .token_store import TrainingTokens
        from .schedule import Schedule
        from .numerical_prerequisites import PINS
        from . import candidate_evaluation,development_loss,full_diagnostics,delivery
        final_ticket=json.loads((candidate/'final-ticket.json').read_bytes())
        base=project/'restart/execution-v1'
        config=Config(**json.loads((project/'restart/approval-v1/policy.json').read_bytes())['architecture'])
        store=TrainingTokens(base/'data-train',manifest_sha256=PINS['data-train/manifest.json'])
        schedule=Schedule((base/'batch-schedule-draft-v3/updates.jsonl').read_bytes(),expected_sha256=candidate_snapshot.SCHEDULE,
                          document_targets={k:v['targets'] for k,v in store._index.items()})
        expected=dict(code_hash=t['snapshot_sha256'],tokenizer_hash=PINS['tokenizer-8192/manifest.json'],
                      config_hash=hashlib.sha256(json.dumps(config.to_dict(),sort_keys=True).encode()).hexdigest())
        handles=final_state.open_state(candidate/'final-state-v1',manifest_sha256=final_ticket['state_sha256'],identity=t['identity'],
            schedule=schedule,expected=expected,checkpoint_root=candidate/'checkpoints',deadline=t['deadline'])
        clock=final_state.open_clock(candidate/'time.sqlite',identity=t['identity'],deadline=t['deadline'])
        dev=candidate_evaluation.inputs(project,'dev_loss_checkpoint')
        copy=candidate_evaluation.inputs(project,'copying_probes');copy.pop('config')
        def heartbeat():atomic_json(output/'heartbeat.json',dict(pid=os.getpid(),monotonic=time.monotonic()))
        heartbeat()
        verdict=research_report.assess(project,candidate,catalog=handles['catalog'],quality=handles['quality'],pilot=handles['pilot'],
            time_budget=clock,dev_verify=development_loss.quality_verifier(dev['dev_store']),
            copy_verify=full_diagnostics.copying_verifier(**copy),reviews=json.loads((output/'reviews.json').read_bytes()),heartbeat=heartbeat)
        verdict['pilot_feasibility']=handles['pilot'].decision()
        verdict['delivery']=delivery.build(candidate,output,identity=t['identity'],schedule_sha256=schedule.sha256,heartbeat=heartbeat)
        if clock.terminal() is not None or time.time()>=clock.deadline or clock.charged()>=clock.cap:
            raise ValueError('Report delivery budget exhausted')
        path=research_report.publish(output,verdict)
        atomic_json(output/'completion.json',dict(status='REPORT_COMPLETE',report_sha256=final_state.digest(path),ticket_sha256=pin))
        return verdict
    except BaseException as error:
        atomic_json(output/'worker-stop.json',dict(status='STOP',reason=str(error),final_research_pass=False));raise
    finally:
        for handle in handles.values():handle.close()
        if clock is not None:clock.db.close()


def launch(binding,reviews):
    if reviews is None:raise ValueError('Complete narrative reviews required')
    encoded=(json.dumps(reviews,sort_keys=True,allow_nan=False)+'\n').encode()
    project=Path(binding['project']).resolve(strict=True);candidate=Path(binding['output']).absolute()
    if candidate!=project/'restart/execution-v1/candidate-run-v1' or candidate.resolve(strict=True)!=candidate:
        raise ValueError('Unowned report candidate')
    if json.loads((candidate/'parent-binding.json').read_bytes())!=binding:raise ValueError('Changed parent binding')
    output=candidate/'report-run-v1';ticket_path=candidate/'report-ticket.json'
    if any(p.exists() for p in (output,ticket_path,candidate/'research-report-v1.json',candidate/'report-stop.json')):
        raise FileExistsError('Report attempt already reserved; no retry')
    if not (candidate/'time.sqlite').is_file():raise ValueError('Missing original report clock')
    clock=TimeBudget(candidate/'time.sqlite',identity=binding['identity'],seconds_cap=129600,deadline_utc=binding['deadline'])
    try:
        if clock.terminal() is not None or not 0<clock.charged()<clock.cap or time.time()>=clock.deadline:raise ValueError('Report budget unavailable')
        if not (candidate/'final-run-v1/parent-completion.json').is_file():raise ValueError('Final evaluation not complete')
        candidate_snapshot.verify(project,candidate/'snapshot.json',expected_sha256=binding['snapshot_sha256'],now=time.time())
        output.mkdir();(output/'reviews.json').write_bytes(encoded)
        sb=candidate/'report-worker.sb';sb.write_text(profile(project,candidate,output))
        ticket=dict(schema=1,project=str(project),candidate=str(candidate),output=str(output),identity=binding['identity'],
            snapshot_sha256=binding['snapshot_sha256'],deadline=binding['deadline'],parent_pid=os.getpid(),
            reviews_sha256=hashlib.sha256(encoded).hexdigest(),profile_sha256=final_state.digest(sb))
        with ticket_path.open('x') as f:json.dump(ticket,f);f.flush();os.fsync(f.fileno())
        pin=final_state.digest(ticket_path)
        result=supervise(custody.command(sb,[sys.executable,'-m','slm.restart.report_dispatch',str(ticket_path),pin]),
            cwd=output,env=environment(project,output),heartbeat=output/'heartbeat.json',budget=clock,receipt=output/'supervisor.json',active_ceiling=129600)
        if result['status']!='PASS' or clock.terminal() is not None:raise ValueError('Report supervision failed')
        verify_resource_history(output/'supervisor.json')
        done=json.loads((output/'completion.json').read_bytes());started=json.loads((output/'worker-started.json').read_bytes())
        if (done!=dict(status='REPORT_COMPLETE',report_sha256=final_state.digest(output/'research-report-v1.json'),ticket_sha256=pin)
                or started!=dict(pid=result['worker_pid'],parent_pid=os.getpid(),ticket_sha256=pin)):
            raise ValueError('Unverified report execution')
        if final_state.digest(output/'reviews.json')!=ticket['reviews_sha256']:raise ValueError('Reviews changed during assessment')
        candidate_snapshot.verify(project,candidate/'snapshot.json',expected_sha256=binding['snapshot_sha256'],now=time.time())
        verdict=json.loads((output/'research-report-v1.json').read_bytes())
        if verdict['identity']!=binding['identity'] or verdict['code_snapshot_sha256']!=binding['snapshot_sha256']:
            raise ValueError('Report identity changed')
        delivery.verify(output,verdict['delivery'],identity=binding['identity'])
        verdict['report_supervision']=result;verdict['charged_active_seconds']=clock.charged()
        research_report.publish(candidate,verdict)
        return verdict
    except BaseException as error:
        clock.stop('Report failed: '+str(error));atomic_json(candidate/'report-stop.json',dict(status='STOP',reason=str(error),final_research_pass=False));raise
    finally:clock.db.close()


if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Parent-bound report ticket and hash required')
    execute(sys.argv[1],sys.argv[2])
