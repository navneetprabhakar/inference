import hashlib,json
from types import SimpleNamespace
import pytest
from slm.restart import research_report as report
from slm.restart.ledger import Ledger


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))


@pytest.fixture
def evidence(tmp_path,monkeypatch):
    candidate=tmp_path/'restart/execution-v1/candidate-run-v1';candidate.mkdir(parents=True)
    output=candidate/'final-run-v1';output.mkdir()
    binding=dict(identity='fixture',snapshot_sha256='a'*64,deadline=9999999999)
    write(candidate/'parent-binding.json',binding);write(candidate/'snapshot.json',{})
    write(candidate/'continuation-completion.json',{'status':'NORMAL_BUDGET_END'})
    write(candidate/'continuation-supervisor.json',{'status':'PASS'})
    write(candidate/'final-state-v1/manifest.json',{})
    (candidate/'final-worker.sb').write_text('fixture-profile')
    ticket=dict(binding,candidate=str(candidate),output=str(output),training_phase='continuation',parent_pid=12,
        selection={'path':'selected'},completion_sha256=report.digest(candidate/'continuation-completion.json'),
        state_sha256=report.digest(candidate/'final-state-v1/manifest.json'),profile_sha256=report.digest(candidate/'final-worker.sb'))
    write(candidate/'final-ticket.json',ticket)
    write(output/'supervisor.json',dict(status='PASS',worker_returncode=0,stage_active_ceiling=129600,worker_pid=13))
    write(output/'worker-started.json',dict(pid=13,parent_pid=12,ticket_sha256=report.digest(candidate/'final-ticket.json')))
    write(output/'raw.json',{'context':{}})
    write(output/'receipt.json',dict(selection=ticket['selection'],result_sha256=report.digest(output/'raw.json'),forward_calls=1))
    write(output/'assessment.json',{'metrics':{}});write(output/'review-packet.json',{})
    write(output/'known-leakage.json',{'status':'PASS'})
    done=dict(status='NARRATIVE_REVIEW_REQUIRED',final_research_pass=False)
    for name,key in [('raw.json','raw_sha256'),('receipt.json','receipt_sha256'),('assessment.json','assessment_sha256'),('review-packet.json','review_packet_sha256')]:
        done[key]=report.digest(output/name)
    write(output/'completion.json',done);write(output/'parent-completion.json',done)
    monkeypatch.setattr(report.candidate_snapshot,'verify',lambda *a,**kw:None)
    monkeypatch.setattr(report.final_custody,'profile',lambda *a:'fixture-profile')
    from slm.restart.supervisor import ResourceHistory
    for path in (candidate/'continuation-supervisor.json',output/'supervisor.json'):
        value=json.loads(path.read_bytes())
        for key,val in dict(reason='worker_completed',charged_active_seconds=10,observed_seconds=1,baseline_swap_mib=0,stage_active_ceiling=129600).items():value.setdefault(key,val)
        history=ResourceHistory(path.with_name(path.name+'.resources.jsonl'))
        history.append('start',baseline_swap_mib=0,stage_active_ceiling=129600)
        history.append('completion',**{key:value[key] for key in ('status','reason','charged_active_seconds','observed_seconds')})
        value['resource_history']=history.close();write(path,value)
    return tmp_path,candidate


def test_execution_bundle_requires_parent_and_worker_evidence(evidence):
    project,candidate=evidence
    assert report.execution_bundle(project,candidate)['receipt']['forward_calls']==1


@pytest.mark.parametrize('fault',['stop','raw','review','profile','state','training','parent','supervisor','started'])
def test_changed_execution_evidence_rejected(evidence,fault):
    project,candidate=evidence;output=candidate/'final-run-v1'
    targets={'stop':candidate/'parent-stop.json','raw':output/'raw.json','review':output/'review-packet.json',
        'profile':candidate/'final-worker.sb','state':candidate/'final-state-v1/manifest.json',
        'training':candidate/'continuation-completion.json','parent':output/'parent-completion.json'}
    if fault in targets:write(targets[fault],{'changed':True})
    else:
        path=output/('supervisor.json' if fault=='supervisor' else 'worker-started.json')
        value=json.loads(path.read_text());value['status' if fault=='supervisor' else 'pid']='STOP';write(path,value)
    with pytest.raises(ValueError):report.execution_bundle(project,candidate)


@pytest.fixture
def assessment(evidence,monkeypatch):
    project,candidate=evidence
    bundle=report.execution_bundle(project,candidate)
    config=SimpleNamespace(to_dict=lambda:{'fixture':True},parameter_count=5114112)
    ledger=Ledger(candidate/'exposures.sqlite','fixture',target_cap=100,update_cap=10,presentation_cap=3,deadline=9999999999)
    snap=ledger.snapshot();ledger.close()
    prepared=dict(selection=bundle['ticket']['selection'],parameter_sha256='b'*64,retained_ledger_snapshot=snap,termination={'status':'NORMAL_BUDGET_END'},context={})
    bundle['receipt'].update(prepared)
    monkeypatch.setattr(report,'execution_bundle',lambda *a:bundle)
    monkeypatch.setattr(report.final_checkpoint,'prepare',lambda *a,**kw:prepared)
    monkeypatch.setattr(report.known_leakage,'verify',lambda *a:bundle['leakage'])
    monkeypatch.setattr(report.final_evaluation,'inputs',lambda *a:{'config':config})
    monkeypatch.setattr(report.final_diagnostics,'assess',lambda *a,**kw:dict(metrics={},status='METRIC_GATES_PASS'))
    catalog=SimpleNamespace(args=dict(identity='fixture',expected=dict(code_hash='a'*64,
        config_hash=hashlib.sha256(json.dumps(config.to_dict(),sort_keys=True).encode()).hexdigest(),tokenizer_hash='c'*64)))
    clock=SimpleNamespace(terminal=lambda:None,deadline=9999999999,charged=lambda:100,cap=129600)
    kwargs=dict(catalog=catalog,quality=None,pilot=None,time_budget=clock,dev_verify=None,copy_verify=None,heartbeat=lambda:None)
    return project,candidate,bundle,kwargs


@pytest.mark.parametrize('reviews,metric_status,expected',[(None,'NARRATIVE_REVIEW_REQUIRED','INCONCLUSIVE_REVIEW_REQUIRED'),([], 'METRIC_GATES_PASS','NARRATIVE_RESEARCH_PASS'),([], 'METRIC_GATES_FAIL','NARRATIVE_RESEARCH_FAIL')])
def test_report_status_requires_verified_metrics_and_review(assessment,monkeypatch,reviews,metric_status,expected):
    project,candidate,_,kwargs=assessment
    # Review completeness itself is independently enforced by final_diagnostics.
    monkeypatch.setattr(report.final_diagnostics,'assess',lambda *a,**kw:dict(metrics={},status=metric_status))
    result=report.assess(project,candidate,reviews=reviews,**kwargs)
    assert result['status']==expected
    assert result['final_research_pass']==(expected=='NARRATIVE_RESEARCH_PASS')
    assert result['full_english_gate_met'] is False and result['further_training_authorized'] is False


@pytest.mark.parametrize('fault',['clock','leakage','metrics','receipt','ledger'])
def test_report_refuses_changed_or_terminal_authority(assessment,monkeypatch,fault):
    project,candidate,bundle,kwargs=assessment
    if fault=='clock':kwargs['time_budget'].terminal=lambda:'STOP'
    if fault=='leakage':monkeypatch.setattr(report.known_leakage,'verify',lambda *a:{'changed':True})
    if fault=='metrics':bundle['pending']['metrics']={'changed':True}
    if fault=='receipt':bundle['receipt']['parameter_sha256']='changed'
    if fault=='ledger':
        ledger=Ledger(candidate/'exposures.sqlite','fixture',target_cap=100,update_cap=10,presentation_cap=3,deadline=9999999999)
        ledger.reserve('later',[('doc',0,1)],now=100);ledger.close()
    with pytest.raises(ValueError):report.assess(project,candidate,reviews=[],**kwargs)


def test_publication_is_once_only_and_requires_complete_review(tmp_path):
    with pytest.raises(ValueError):report.publish(tmp_path,{'status':'INCONCLUSIVE_REVIEW_REQUIRED'})
    result={'status':'NARRATIVE_RESEARCH_FAIL','final_research_pass':False}
    path=report.publish(tmp_path,result)
    assert json.loads(path.read_text())==result
    with pytest.raises(FileExistsError):report.publish(tmp_path,result)


def test_unexpected_metric_verdict_cannot_pass(assessment,monkeypatch):
    project,candidate,_,kwargs=assessment
    monkeypatch.setattr(report.final_diagnostics,'assess',lambda *a,**kw:dict(metrics={},status='UNKNOWN'))
    with pytest.raises(ValueError,match='Unexpected'):report.assess(project,candidate,reviews=[],**kwargs)


def test_inconsistent_publication_leaves_no_file(tmp_path):
    with pytest.raises(ValueError,match='Inconsistent'):
        report.publish(tmp_path,dict(status='NARRATIVE_RESEARCH_PASS',final_research_pass=False))
    assert not (tmp_path/'research-report-v1.json').exists()
