import hashlib,json,sqlite3
from types import SimpleNamespace
import pytest
from slm.restart.pilot_evidence import Measurements,collect
from slm.restart.pilot_gate import assess
from slm.restart.schedule import ScheduledUpdate
from slm.restart.ledger import Ledger
from slm.restart.supervisor import TimeBudget


@pytest.fixture
def measured(tmp_path):
    updates=(ScheduledUpdate(1,1,250000,250000,.001,(),()),ScheduledUpdate(2,1,1750000,2000000,.001,(),()))
    s=SimpleNamespace(sha256='schedule',updates=updates)
    m=Measurements(tmp_path/'measurements',identity='run',schedule=s)
    ledger=Ledger(tmp_path/'ledger','run',target_cap=3000000,update_cap=3,presentation_cap=2,deadline=10000)
    clock=TimeBudget(tmp_path/'time',identity='run',seconds_cap=129600,deadline_utc=10000)
    yield m,ledger,clock,updates
    m.close();ledger.close();clock.db.close()


def record(m,ledger,clock,update,active):
    while clock.charged()<active:clock.reserve(10,1)
    rid=str(update.step);ledger.reserve(rid,[('doc',update.cumulative_targets-update.targets,update.cumulative_targets)],now=1)
    ledger.complete(rid);m.completed(update,reservation=rid,ledger=ledger,time_budget=clock)


def test_throughput_from_completed_work_and_persistent_clock(measured):
    m,l,c,u=measured;record(m,l,c,u[0],100);record(m,l,c,u[1],800)
    assert m.throughput()==dict(start_targets=250000,end_targets=2000000,start_active_seconds=100.,end_active_seconds=800.)
    with pytest.raises(sqlite3.IntegrityError):m.completed(u[1],reservation='2',ledger=l,time_budget=c)


def test_unfinished_or_terminal_work_has_no_timing_point(measured):
    m,l,c,u=measured;c.reserve(10,1);l.reserve('x',[('doc',0,250000)],now=1)
    with pytest.raises(ValueError):m.completed(u[0],reservation='x',ledger=l,time_budget=c)
    l.complete('x');c.stop('resource stop')
    with pytest.raises(ValueError):m.completed(u[0],reservation='x',ledger=l,time_budget=c)
    with pytest.raises(ValueError):m.throughput()


def accepted():
    db=sqlite3.connect(':memory:')
    db.execute('CREATE TABLE evidence(step INTEGER,event TEXT,raw BLOB,sha256 TEXT)')
    for step,(target,nll) in enumerate(zip((0,500000,1000000,1500000,2000000),(4.,3.9,3.85,3.8,3.7))):
        p={'context':{'targets':target,'event':'dev_loss_checkpoint'},'metrics':{'targets':200000,'nll':nll}}
        raw=json.dumps(p).encode();db.execute('INSERT INTO evidence VALUES (?,?,?,?)',(step,'dev_loss_checkpoint',raw,hashlib.sha256(raw).hexdigest()))
    p={'context':{'targets':2000000,'event':'full_development_diagnostics'},'grammar':{'outputs':[None]*200},
       'grounded':{'outputs':[None]*100},'narratives':{'outputs':[None]*100}}
    raw=json.dumps(p).encode();db.execute('INSERT INTO evidence VALUES (?,?,?,?)',(4,'full_development_diagnostics',raw,hashlib.sha256(raw).hexdigest()))
    return SimpleNamespace(db=db,position=lambda:1,pending=lambda:(),schedule=SimpleNamespace(updates=(SimpleNamespace(cumulative_targets=2000000),)))


def test_collector_reverifies_all_records_and_passes_gate(measured):
    m,l,c,u=measured;record(m,l,c,u[0],100);record(m,l,c,u[1],800);b=accepted();calls=[]
    def dev(raw,context):calls.append(context['targets']);return {'nll':json.loads(raw)['metrics']['nll']}
    def full(raw,context):calls.append('full');return {'degenerate_outputs':0}
    try:
        e,receipt=collect(barrier=b,measurements=m,time_budget=c,elapsed_seconds=2000,target_cap=43409847,dev_verify=dev,full_verify=full)
        assert len(calls)==6 and receipt['measurement_rows']==2
        assert assess(**e)['status']=='PILOT_METRIC_RULES_PASS'
        b.db.execute("UPDATE evidence SET sha256='changed' WHERE step=0")
        with pytest.raises(ValueError):collect(barrier=b,measurements=m,time_budget=c,elapsed_seconds=2000,target_cap=43409847,dev_verify=dev,full_verify=full)
    finally:b.db.close()


from test_restart_update_step import setup as arithmetic_update


def test_measurement_wrapper_records_actual_update_completion(arithmetic_update,tmp_path):
    from slm.restart.pilot_evidence import execute_measured
    update,kwargs,calls,_=arithmetic_update
    schedule=SimpleNamespace(sha256='fixture',updates=(update,))
    m=Measurements(tmp_path/'timings',identity='fixture',schedule=schedule)
    clock=TimeBudget(tmp_path/'clock',identity='fixture',seconds_cap=100,deadline_utc=100)
    clock.reserve(10,1)
    try:
        result=execute_measured(update,measurements=m,time_budget=clock,**kwargs)
        assert result['targets']==3 and calls==['read','gradient','read','gradient']
        assert m.db.execute('SELECT step,targets,active FROM completions').fetchall()==[(1,3,10.)]
    finally:m.close();clock.db.close()
