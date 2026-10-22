import json,sqlite3
import pytest
from slm.restart import final_launch as launch
from slm.restart.ledger import Ledger
from slm.restart.supervisor import TimeBudget


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    candidate=tmp_path/'restart/execution-v1/candidate-run-v1';candidate.mkdir(parents=True)
    b=dict(project=str(tmp_path),output=str(candidate),snapshot_sha256='a'*64,identity='candidate-v1:'+'a'*64,deadline=9999999999)
    (candidate/'parent-binding.json').write_text(json.dumps(b))
    completion={'status':'NORMAL_BUDGET_END','targets':3000000,'best':{'path':'fixture-best'}}
    (candidate/'continuation-completion.json').write_text(json.dumps(completion))
    (candidate/'continuation-supervisor.json').write_text(json.dumps({'status':'PASS'}))
    clock=TimeBudget(candidate/'time.sqlite',identity=b['identity'],seconds_cap=129600,deadline_utc=b['deadline']);clock.reserve(10,100)
    ledger=Ledger(candidate/'exposures.sqlite',b['identity'],target_cap=3000000,update_cap=6000,presentation_cap=3,deadline=b['deadline'])
    for name in ('quality','pilot','catalog'):
        db=sqlite3.connect(candidate/(name+'.sqlite'));db.execute('CREATE TABLE fixture(value INTEGER)');db.commit();db.close()
    monkeypatch.setattr(launch.candidate_snapshot,'verify',lambda *a,**kw:{'original_deadline':b['deadline']})
    monkeypatch.setattr(launch.final_custody,'profile',lambda *a:'fixture-profile')
    monkeypatch.setattr(launch.known_leakage,'verify',lambda *a:{'status':'KNOWN_LEAKAGE_RECHECK_PASS','fixture':True})
    yield b,candidate,clock,ledger
    ledger.close();clock.db.close()


def test_parent_final_dispatch_retains_time_and_checks_output_hashes(fixture,monkeypatch):
    b,candidate,clock,ledger=fixture
    def supervise(argv,**kw):
        assert 'slm.restart.final_worker' in argv and kw['active_ceiling']==129600
        assert kw['budget'].charged()==10 and kw['budget'].deadline==b['deadline']
        kw['budget'].reserve(10,100)
        output=kw['cwd'];ticket=json.loads((candidate/'final-ticket.json').read_bytes())
        assert ticket['deadline']==b['deadline'] and ticket['selection']=={'path':'fixture-best'}
        (output/'raw.json').write_text('{}')
        receipt={'selection':ticket['selection'],'result_sha256':launch.final_state.digest(output/'raw.json'),
                 'retained_ledger_snapshot':ledger.snapshot()}
        (output/'receipt.json').write_text(json.dumps(receipt))
        (output/'assessment.json').write_text('{}');(output/'review-packet.json').write_text('{}')
        done=dict(status='NARRATIVE_REVIEW_REQUIRED',final_research_pass=False)
        for file,key in [('raw.json','raw_sha256'),('receipt.json','receipt_sha256'),('assessment.json','assessment_sha256'),('review-packet.json','review_packet_sha256')]:
            done[key]=launch.final_state.digest(output/file)
        (output/'completion.json').write_text(json.dumps(done))
        return {'status':'PASS'}
    monkeypatch.setattr(launch,'supervise',supervise)
    assert launch.launch(b)['status']=='NARRATIVE_REVIEW_REQUIRED'
    assert clock.charged()==20 and clock.terminal() is None
    with pytest.raises(FileExistsError):launch.launch(b)


@pytest.mark.parametrize('fault',['prior_failure','pilot_only','supervisor_failure','already_reserved','expired_clock'])
def test_invalid_final_attempt_never_launches(fixture,monkeypatch,fault):
    b,candidate,clock,_=fixture
    if fault=='prior_failure':(candidate/'worker-stop.json').write_text('{}')
    if fault=='pilot_only':(candidate/'continuation-completion.json').write_text(json.dumps({'status':'PILOT_PASS','targets':2000000}))
    if fault=='supervisor_failure':(candidate/'continuation-supervisor.json').write_text(json.dumps({'status':'STOP'}))
    if fault=='already_reserved':(candidate/'final-run-v1').mkdir()
    if fault=='expired_clock':clock.stop('budget exhausted')
    monkeypatch.setattr(launch,'supervise',lambda *a,**kw:pytest.fail('Final worker must not launch'))
    with pytest.raises((ValueError,FileExistsError)):launch.launch(b)


def test_failed_final_worker_cannot_retry(fixture,monkeypatch):
    b,candidate,clock,_=fixture
    monkeypatch.setattr(launch,'supervise',lambda *a,**kw:{'status':'STOP'})
    with pytest.raises(ValueError):launch.launch(b)
    assert clock.terminal() and (candidate/'final-stop.json').exists()
    with pytest.raises(FileExistsError):launch.launch(b)


def test_new_leakage_failure_stops_before_final_dispatch(fixture,monkeypatch):
    b,candidate,clock,_=fixture
    def reject(*a):raise ValueError('known overlap')
    monkeypatch.setattr(launch.known_leakage,'verify',reject)
    monkeypatch.setattr(launch,'supervise',lambda *a,**kw:pytest.fail('Known leakage must block final'))
    with pytest.raises(ValueError,match='overlap'):launch.launch(b)
    assert clock.terminal() and (candidate/'final-stop.json').exists()
    assert not (candidate/'final-run-v1').exists()
