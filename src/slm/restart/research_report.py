"""Final research verdict from verified execution, raw metrics and explicit reviews.

No model execution or launch authority. Caller must supervise/charge this read-only
assessment under the original budget, then publish once after review is complete.
"""
import hashlib,json,os,time
from pathlib import Path
from . import candidate_snapshot,final_checkpoint,final_custody,final_diagnostics,final_evaluation,known_leakage
from .evaluation_snapshot import _file
from .final_state import digest,readonly
from .ledger import Ledger
from .supervisor import verify_resource_history
from .numerical_monitor_comparison import exact


def execution_bundle(project,candidate):
    project=Path(project).resolve(strict=True);candidate=Path(candidate).absolute()
    if candidate!=project/'restart/execution-v1/candidate-run-v1' or candidate.resolve(strict=True)!=candidate:
        raise ValueError('Unowned research report candidate')
    output=candidate/'final-run-v1'
    for relative in ('parent-stop.json','worker-stop.json','final-stop.json','final-run-v1/worker-stop.json'):
        if (candidate/relative).exists():raise ValueError('Terminal failure cannot become research success')
    def read(relative):return json.loads(_file(candidate,relative).read_bytes())
    binding=read('parent-binding.json');ticket=read('final-ticket.json')
    candidate_snapshot.verify(project,_file(candidate,'snapshot.json'),expected_sha256=binding['snapshot_sha256'],now=time.time())
    if (ticket['identity']!=binding['identity'] or ticket['snapshot_sha256']!=binding['snapshot_sha256']
            or ticket['deadline']!=binding['deadline'] or ticket['candidate']!=str(candidate) or ticket['output']!=str(output)):
        raise ValueError('Final ticket changed original execution binding')
    phase=ticket['training_phase']
    if phase not in ('continuation','continuation-recovery'):raise ValueError('Final report requires continuation')
    completion_path=_file(candidate,phase+'-completion.json')
    if digest(completion_path)!=ticket['completion_sha256']:raise ValueError('Training completion changed')
    if read(phase+'-supervisor.json')['status']!='PASS':raise ValueError('Training supervisor did not pass')
    if digest(_file(candidate,'final-state-v1/manifest.json'))!=ticket['state_sha256']:raise ValueError('Changed final state snapshot')
    profile=_file(candidate,'final-worker.sb')
    if digest(profile)!=ticket['profile_sha256'] or profile.read_text()!=final_custody.profile(project,candidate,output):
        raise ValueError('Changed final custody evidence')
    supervisor=read('final-run-v1/supervisor.json');started=read('final-run-v1/worker-started.json')
    if (supervisor['status']!='PASS' or supervisor['worker_returncode']!=0 or supervisor['stage_active_ceiling']!=129600
            or started['pid']!=supervisor['worker_pid'] or started['parent_pid']!=ticket['parent_pid']
            or started['ticket_sha256']!=digest(_file(candidate,'final-ticket.json'))):
        raise ValueError('Unverified final worker execution')
    done=read('final-run-v1/completion.json')
    if not exact(done,read('final-run-v1/parent-completion.json')) or done['status']!='NARRATIVE_REVIEW_REQUIRED' or done['final_research_pass'] is not False:
        raise ValueError('Unverified final parent completion')
    pins={}
    for name,key in (('raw.json','raw_sha256'),('receipt.json','receipt_sha256'),('assessment.json','assessment_sha256'),('review-packet.json','review_packet_sha256')):
        pins[name]=digest(_file(output,name))
        if pins[name]!=done[key]:raise ValueError('Final result changed after parent acceptance')
    resource_histories={}
    for relative in (phase+'-supervisor.json','final-run-v1/supervisor.json'):
        path=_file(candidate,relative);rows=verify_resource_history(path)
        resource_histories[relative]={'receipt_sha256':digest(path),'history':read(relative)['resource_history'],
                                      'observed_samples':len(rows)-2}
    receipt=read('final-run-v1/receipt.json')
    if (receipt['selection']!=ticket['selection'] or receipt['result_sha256']!=pins['raw.json']
            or type(receipt['forward_calls']) is not int or receipt['forward_calls']<=0):raise ValueError('Invalid final execution receipt')
    return dict(binding=binding,ticket=ticket,completion=json.loads(completion_path.read_bytes()),receipt=receipt,supervisor=supervisor,
        raw=read('final-run-v1/raw.json'),pending=read('final-run-v1/assessment.json'),packet=read('final-run-v1/review-packet.json'),
        leakage=read('final-run-v1/known-leakage.json'),output_pins=pins,resource_histories=resource_histories)


def assess(project,candidate,*,catalog,quality,pilot,time_budget,dev_verify,copy_verify,reviews,heartbeat):
    def tick():
        if time_budget.terminal() is not None or time.time()>=time_budget.deadline or time_budget.charged()>=time_budget.cap:
            raise ValueError('Research assessment budget exhausted')
        heartbeat()
    tick();bundle=execution_bundle(project,candidate);ticket=bundle['ticket']
    if time_budget.deadline!=ticket['deadline'] or catalog.args['identity']!=ticket['identity'] or catalog.args['expected']['code_hash']!=ticket['snapshot_sha256']:
        raise ValueError('Assessment state differs from final execution')
    prepared=final_checkpoint.prepare(bundle['completion'],catalog=catalog,quality=quality,pilot=pilot,time_budget=time_budget,
                                      dev_verify=dev_verify,copy_verify=copy_verify)
    receipt=bundle['receipt']
    for key in ('selection','parameter_sha256','retained_ledger_snapshot','termination'):
        if not exact(receipt[key],prepared[key]):raise ValueError('Final receipt differs from verified training state')
    if not exact(bundle['raw']['context'],prepared['context']):raise ValueError('Raw final results use another checkpoint')
    live=Ledger.__new__(Ledger);live.db=readonly(Path(candidate)/'exposures.sqlite',immutable=False)
    try:
        if live.snapshot()!=prepared['retained_ledger_snapshot']:raise ValueError('Original work ledger changed after final execution')
    finally:live.close()
    tick();leakage=known_leakage.verify(project)
    if not exact(leakage,bundle['leakage']):raise ValueError('Leakage evidence changed after final execution')
    data=final_evaluation.inputs(Path(project));config=data.pop('config')
    if hashlib.sha256(json.dumps(config.to_dict(),sort_keys=True).encode()).hexdigest()!=catalog.args['expected']['config_hash']:
        raise ValueError('Research model configuration mismatch')
    metrics=final_diagnostics.assess(bundle['raw'],context=prepared['context'],reviews=reviews,review_packet=bundle['packet'],**data)
    if not exact(metrics['metrics'],bundle['pending']['metrics']):raise ValueError('Recomputed metrics differ from accepted raw results')
    allowed=('NARRATIVE_REVIEW_REQUIRED',) if reviews is None else ('METRIC_GATES_PASS','METRIC_GATES_FAIL')
    if metrics['status'] not in allowed:raise ValueError('Unexpected metric verdict')
    tick()
    status='INCONCLUSIVE_REVIEW_REQUIRED' if reviews is None else ('NARRATIVE_RESEARCH_PASS' if metrics['status']=='METRIC_GATES_PASS' else 'NARRATIVE_RESEARCH_FAIL')
    return {'status':status,'final_research_pass':status=='NARRATIVE_RESEARCH_PASS','assessment':metrics,
        'known_leakage':leakage,'selection':prepared['selection'],'termination':prepared['termination'],
        'exposure_counts':prepared['retained_ledger_snapshot'],'parameters':config.parameter_count,
        'resource_histories':bundle['resource_histories'],
        'identity':ticket['identity'],'code_snapshot_sha256':ticket['snapshot_sha256'],'config_sha256':catalog.args['expected']['config_hash'],
        'tokenizer_manifest_sha256':catalog.args['expected']['tokenizer_hash'],'final_output_sha256':bundle['output_pins'],
        'reviews_sha256':None if reviews is None else hashlib.sha256(json.dumps(reviews,sort_keys=True,allow_nan=False).encode()).hexdigest(),
        'charged_active_seconds':time_budget.charged(),'elapsed_seconds':time.time()-(ticket['deadline']-259200),
        'scope':'Frozen narrative research gate only; assistant grading proxy, not independent human certification',
        'full_english_gate_met':False,'further_training_authorized':False}


def publish(candidate,report):
    if report['status'] not in ('NARRATIVE_RESEARCH_PASS','NARRATIVE_RESEARCH_FAIL'):raise ValueError('Complete review required before final publication')
    if report.get('final_research_pass') is not (report['status']=='NARRATIVE_RESEARCH_PASS'):
        raise ValueError('Inconsistent research verdict')
    encoded=json.dumps(report,indent=2,allow_nan=False)+'\n'
    path=Path(candidate)/'research-report-v1.json'
    with path.open('x') as f:f.write(encoded);f.flush();os.fsync(f.fileno())
    return path
