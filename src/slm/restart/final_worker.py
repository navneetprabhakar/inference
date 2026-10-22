"""Single-use, parent-bound final worker; no optimizer or random initialization."""
import hashlib,json,os,sys,time
from pathlib import Path
from . import candidate_snapshot,final_state,final_custody
from .supervisor import atomic_json


def preflight(path,pin,*,now=None):
    now=time.time() if now is None else now;path=Path(path).absolute();raw=path.read_bytes()
    if path.resolve(strict=True)!=path or hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Changed final ticket')
    t=json.loads(raw)
    keys={'schema','project','candidate','output','identity','snapshot_sha256','state_sha256','completion_sha256',
          'training_phase','selection','deadline','parent_pid','profile_sha256'}
    if set(t)!=keys or type(t['schema']) is not int or t['schema']!=1 or type(t['parent_pid']) is not int or t['parent_pid']!=os.getppid():
        raise ValueError('Unowned final ticket')
    project=Path(t['project']).resolve(strict=True);candidate=Path(t['candidate']).absolute();output=Path(t['output']).absolute()
    if (candidate!=project/'restart/execution-v1/candidate-run-v1' or candidate.resolve(strict=True)!=candidate
            or output!=candidate/'final-run-v1' or output.resolve(strict=True)!=output or path!=candidate/'final-ticket.json'):
        raise ValueError('Unowned final directories')
    bound=candidate_snapshot.verify(project,candidate/'snapshot.json',expected_sha256=t['snapshot_sha256'],now=now)
    if t['identity']!='candidate-v1:'+t['snapshot_sha256'] or t['deadline']!=bound['original_deadline'] or not now<t['deadline']:
        raise ValueError('Changed final identity/deadline')
    phase=t['training_phase']
    if phase not in ('continuation','continuation-recovery'):raise ValueError('Final requires completed continuation')
    if any((candidate/name).exists() for name in ('parent-stop.json','worker-stop.json','final-stop.json')):
        raise ValueError('Failed candidate cannot evaluate final')
    completion_path=candidate/(phase+'-completion.json')
    if final_state.digest(completion_path)!=t['completion_sha256']:raise ValueError('Changed training completion')
    completion=json.loads(completion_path.read_bytes());supervisor=json.loads((candidate/(phase+'-supervisor.json')).read_bytes())
    if supervisor['status']!='PASS' or completion['status'] not in ('NORMAL_BUDGET_END','PLATEAU_END','WORK_BUDGET_END'):
        raise ValueError('Training did not finish cleanly')
    if completion['best']!=t['selection']:raise ValueError('Changed final checkpoint selection')
    profile=candidate/'final-worker.sb'
    if final_state.digest(profile)!=t['profile_sha256'] or profile.read_text()!=final_custody.profile(project,candidate,output):
        raise ValueError('Changed final custody profile')
    if final_state.digest(candidate/'final-state-v1/manifest.json')!=t['state_sha256']:raise ValueError('Changed final state snapshot')
    clock=final_state.open_clock(candidate/'time.sqlite',identity=t['identity'],deadline=t['deadline'])
    try:
        if clock.terminal() is not None or not 0<clock.charged()<clock.cap:raise ValueError('Final time not reserved or exhausted')
    finally:clock.db.close()
    with (output/'worker-started.json').open('x') as f:
        json.dump({'pid':os.getpid(),'parent_pid':os.getppid(),'ticket_sha256':pin},f);f.flush();os.fsync(f.fileno())
    return t,completion


def execute(path,pin):
    t,completion=preflight(path,pin);project=Path(t['project']);candidate=Path(t['candidate']);output=Path(t['output'])
    handles={};clock=None
    try:
        from slm.common.config import Config
        from .token_store import TrainingTokens
        from .schedule import Schedule
        from .numerical_prerequisites import PINS
        from . import candidate_evaluation,development_loss,full_diagnostics,final_evaluation
        base=project/'restart/execution-v1'
        config=Config(**json.loads((project/'restart/approval-v1/policy.json').read_bytes())['architecture'])
        store=TrainingTokens(base/'data-train',manifest_sha256=PINS['data-train/manifest.json'])
        schedule=Schedule((base/'batch-schedule-draft-v3/updates.jsonl').read_bytes(),expected_sha256=candidate_snapshot.SCHEDULE,
                          document_targets={k:v['targets'] for k,v in store._index.items()})
        expected={'code_hash':t['snapshot_sha256'],'tokenizer_hash':PINS['tokenizer-8192/manifest.json'],
                  'config_hash':hashlib.sha256(json.dumps(config.to_dict(),sort_keys=True).encode()).hexdigest()}
        handles=final_state.open_state(candidate/'final-state-v1',manifest_sha256=t['state_sha256'],identity=t['identity'],
            schedule=schedule,expected=expected,checkpoint_root=candidate/'checkpoints',deadline=t['deadline'])
        clock=final_state.open_clock(candidate/'time.sqlite',identity=t['identity'],deadline=t['deadline'])
        dev=candidate_evaluation.inputs(project,'dev_loss_checkpoint')
        copy=candidate_evaluation.inputs(project,'copying_probes');copy.pop('config')
        def heartbeat():atomic_json(output/'heartbeat.json',{'pid':os.getpid(),'monotonic':time.monotonic()})
        heartbeat()
        raw,receipt,assessment=final_evaluation.evaluate(project,completion,catalog=handles['catalog'],quality=handles['quality'],
            pilot=handles['pilot'],time_budget=clock,dev_verify=development_loss.quality_verifier(dev['dev_store']),
            copy_verify=full_diagnostics.copying_verifier(**copy),heartbeat=heartbeat,selection=t['selection'])
        for name,data in [('raw.json',raw),('receipt.json',(json.dumps(receipt,sort_keys=True,indent=2)+'\n').encode()),
                          ('assessment.json',(json.dumps(assessment,sort_keys=True,indent=2)+'\n').encode()),
                          ('review-packet.json',(json.dumps(assessment['metrics']['review_packet'],indent=2)+'\n').encode())]:
            with (output/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        atomic_json(output/'completion.json',{'status':'NARRATIVE_REVIEW_REQUIRED','raw_sha256':receipt['result_sha256'],
            'receipt_sha256':final_state.digest(output/'receipt.json'),'assessment_sha256':final_state.digest(output/'assessment.json'),
            'review_packet_sha256':final_state.digest(output/'review-packet.json'),'final_research_pass':False})
        return receipt
    except BaseException as error:
        atomic_json(output/'worker-stop.json',{'status':'STOP','reason':type(error).__name__+': '+str(error),'final_research_pass':False})
        raise
    finally:
        for handle in handles.values():handle.close()
        if clock is not None:clock.db.close()

if __name__=='__main__':
    if len(sys.argv)!=3:raise SystemExit('Parent-bound final ticket path and hash required')
    execute(sys.argv[1],sys.argv[2])
