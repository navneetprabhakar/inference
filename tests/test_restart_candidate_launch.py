from types import SimpleNamespace
import pytest
from slm.restart import candidate_launch as launch


def test_existing_candidate_attempt_is_never_reused(tmp_path,monkeypatch):
    output=tmp_path/'restart/execution-v1/candidate-run-v1';output.mkdir(parents=True)
    monkeypatch.setattr(launch.sys,'executable',str(tmp_path/'.venv/bin/python'))
    monkeypatch.setattr(launch.candidate_snapshot,'preflight',lambda *a,**kw:pytest.fail('Must refuse before preparation'))
    with pytest.raises(FileExistsError):launch.prepare(tmp_path)


@pytest.mark.parametrize('stdout,code',[('1 failed',1),('3 passed, 1 skipped',0),('3 passed, 1 xfailed',0),('',0)])
def test_incomplete_controls_do_not_reserve_candidate(tmp_path,monkeypatch,stdout,code):
    (tmp_path/'tests').mkdir();(tmp_path/'tests/test_restart_fixture.py').write_text('pass')
    monkeypatch.setattr(launch.sys,'executable',str(tmp_path/'.venv/bin/python'))
    monkeypatch.setattr(launch.candidate_snapshot,'preflight',lambda *a,**kw:{'original_deadline':100})
    monkeypatch.setattr(launch.candidate_snapshot,'inventory',lambda *a:[])
    monkeypatch.setattr(launch.subprocess,'run',lambda *a,**kw:SimpleNamespace(returncode=code,stdout=stdout,stderr=''))
    with pytest.raises(ValueError,match='controls'):launch.prepare(tmp_path)
    assert not (tmp_path/'restart/execution-v1/candidate-run-v1').exists()


def binding(tmp_path,monkeypatch):
    output=tmp_path/'restart/execution-v1/candidate-run-v1';output.mkdir(parents=True)
    policy='fixture-profile';(output/'worker.sb').write_text(policy)
    b=dict(project=str(tmp_path),output=str(output),snapshot_sha256='a'*64,identity='candidate-v1:'+'a'*64,deadline=9999999999,profile_sha256=launch.digest(output/'worker.sb'))
    monkeypatch.setattr(launch.candidate_snapshot,'verify',lambda *a,**kw:{'original_deadline':b['deadline'],'target_cap':43409847})
    monkeypatch.setattr(launch.candidate_custody,'profile',lambda *a:policy)
    return b,output


def test_probe_failure_prevents_worker_and_is_terminal(tmp_path,monkeypatch):
    b,output=binding(tmp_path,monkeypatch)
    def fail(*a):raise ValueError('sandbox probe failure')
    monkeypatch.setattr(launch,'probe',fail)
    monkeypatch.setattr(launch,'supervise',lambda *a,**kw:pytest.fail('Worker must not launch'))
    with pytest.raises(ValueError,match='sandbox'):launch.stage(b,'pilot')
    clock=launch.TimeBudget(output/'time.sqlite',identity=b['identity'],seconds_cap=129600,deadline_utc=b['deadline'])
    try:assert clock.terminal()=='sandbox probe failure'
    finally:clock.db.close()
    with pytest.raises(FileExistsError):launch.stage(b,'pilot')


def test_continuation_requires_prior_pilot_before_dispatch(tmp_path,monkeypatch):
    b,output=binding(tmp_path,monkeypatch)
    monkeypatch.setattr(launch,'probe',lambda *a:pytest.fail('Cannot probe/launch yet'))
    with pytest.raises(FileNotFoundError):launch.stage(b,'continuation')
    assert not (output/'continuation-ticket.json').exists()


def test_profile_change_prevents_ticket_creation(tmp_path,monkeypatch):
    b,output=binding(tmp_path,monkeypatch);(output/'worker.sb').write_text('changed')
    with pytest.raises(ValueError,match='custody'):launch.stage(b,'pilot')
    assert not (output/'pilot-ticket.json').exists()


@pytest.fixture
def interrupted(tmp_path,monkeypatch):
    import json,sqlite3
    from slm.restart import interruption_recovery
    b,output=binding(tmp_path,monkeypatch)
    ticket={key:b[key] for key in ('project','output','snapshot_sha256','identity','deadline')}
    ticket.update(phase='pilot',active_ceiling=7200)
    original=output/'pilot-ticket.json';original.write_text(json.dumps(ticket))
    (output/'pilot-worker-started.json').write_text(json.dumps({'ticket_sha256':launch.digest(original)}))
    db=sqlite3.connect(output/'quality.sqlite')
    db.executescript('CREATE TABLE barrier(id INTEGER,step INTEGER,terminal TEXT);INSERT INTO barrier VALUES(1,1,NULL);CREATE TABLE interruption(id INTEGER,original_boot TEXT,recovery TEXT);')
    db.execute('INSERT INTO interruption VALUES(1,?,NULL)',(json.dumps({'host':'fixture','boot_seconds':10,'boot_microseconds':0}),));db.commit();db.close()
    checkpoint=output/'checkpoints/state-1';checkpoint.mkdir(parents=True);(checkpoint/'manifest.json').write_text('{}')
    db=sqlite3.connect(output/'catalog.sqlite')
    db.execute('CREATE TABLE checkpoints(seq INTEGER,name TEXT,pin TEXT,step INTEGER,status TEXT)')
    db.execute('INSERT INTO checkpoints VALUES(1,?,?,0,?)',('state-1',launch.digest(checkpoint/'manifest.json'),'retained'));db.commit();db.close()
    monkeypatch.setattr(interruption_recovery,'boot_identity',lambda:{'host':'fixture','boot_seconds':20,'boot_microseconds':0})
    return b,output,checkpoint


def test_parent_selects_owned_checkpoint_after_verified_reboot(interrupted):
    b,_,checkpoint=interrupted
    assert launch.recovery_checkpoint(b,'pilot-recovery')==(checkpoint,launch.digest(checkpoint/'manifest.json'))


@pytest.mark.parametrize('fault',['same_boot','changed_host','consumed','terminal','completed','supervised','checkpoint','ahead'])
def test_parent_recovery_refusal_before_ticket(interrupted,monkeypatch,fault):
    import sqlite3
    from slm.restart import interruption_recovery
    b,output,checkpoint=interrupted
    if fault in ('same_boot','changed_host'):
        monkeypatch.setattr(interruption_recovery,'boot_identity',lambda:{'host':'other' if fault=='changed_host' else 'fixture','boot_seconds':10,'boot_microseconds':0})
    if fault in ('consumed','terminal'):
        db=sqlite3.connect(output/'quality.sqlite')
        db.execute("UPDATE interruption SET recovery='{}'" if fault=='consumed' else "UPDATE barrier SET terminal='quality failure'");db.commit();db.close()
    if fault=='completed':(output/'pilot-completion.json').write_text('{}')
    if fault=='supervised':(output/'pilot-supervisor.json').write_text('{}')
    if fault=='checkpoint':(checkpoint/'manifest.json').write_text('changed')
    if fault=='ahead':
        db=sqlite3.connect(output/'catalog.sqlite');db.execute('UPDATE checkpoints SET step=2');db.commit();db.close()
    monkeypatch.setattr(launch,'probe',lambda *a:pytest.fail('Recovery must be refused before launch'))
    with pytest.raises(ValueError):launch.stage(b,'pilot-recovery')
    assert not (output/'pilot-recovery-ticket.json').exists()


def test_recovery_dispatch_preserves_pilot_ceiling_and_original_deadline(interrupted,monkeypatch):
    import json
    b,output,checkpoint=interrupted
    monkeypatch.setattr(launch,'probe',lambda *a:None)
    def supervise(*a,**kw):
        ticket=json.loads((output/'pilot-recovery-ticket.json').read_bytes())
        assert ticket['checkpoint']==str(checkpoint) and ticket['deadline']==b['deadline']
        assert kw['active_ceiling']==7200 and kw['budget'].cap==129600
        (output/'pilot-recovery-completion.json').write_text(json.dumps({'status':'PILOT_PASS','targets':2000000}))
        return {'status':'PASS'}
    monkeypatch.setattr(launch,'supervise',supervise)
    assert launch.stage(b,'pilot-recovery')['status']=='PILOT_PASS'
    with pytest.raises(FileExistsError):launch.stage(b,'pilot-recovery')


@pytest.mark.parametrize('fault',[None,'missing_copy','wrong_checkpoint','wrong_targets'])
def test_parent_accepts_only_bound_plateau_completion(tmp_path,monkeypatch,fault):
    import hashlib,json,sqlite3
    b,output=binding(tmp_path,monkeypatch)
    checkpoint=output/'checkpoints/plateau';checkpoint.mkdir(parents=True);(checkpoint/'manifest.json').write_text('{}')
    pin=launch.digest(checkpoint/'manifest.json')
    monkeypatch.setattr(launch,'recovery_checkpoint',lambda *a:(checkpoint,pin))
    monkeypatch.setattr(launch,'probe',lambda *a:None)
    def supervised(*a,**kw):
        context=dict(identity=b['identity'],schedule_sha256=launch.candidate_snapshot.SCHEDULE,
            step=6,targets=3000000,event='dev_loss_checkpoint',checkpoint_sha256=pin)
        stop={'reason':'development plateau','context':context}
        copy_context=dict(context,event='copying_probes')
        if fault=='wrong_checkpoint':copy_context['checkpoint_sha256']='b'*64
        if fault=='wrong_targets':copy_context['targets']=3500000
        raw=json.dumps({'context':copy_context}).encode()
        db=sqlite3.connect(output/'quality.sqlite')
        db.executescript("CREATE TABLE barrier(id INTEGER,terminal TEXT); INSERT INTO barrier VALUES(1,'development plateau'); CREATE TABLE clean_stop(id INTEGER,copy_raw BLOB,copy_pin TEXT,receipt TEXT);")
        if fault!='missing_copy':db.execute('INSERT INTO clean_stop VALUES(1,?,?,?)',(raw,hashlib.sha256(raw).hexdigest(),json.dumps(stop)))
        db.commit();db.close()
        (output/'continuation-recovery-completion.json').write_text(json.dumps({'status':'PLATEAU_END','step':6,'targets':3000000,'checkpoint':str(checkpoint)}))
        return {'status':'PASS'}
    monkeypatch.setattr(launch,'supervise',supervised)
    if fault is None:assert launch.stage(b,'continuation-recovery')['status']=='PLATEAU_END'
    else:
        with pytest.raises(ValueError):launch.stage(b,'continuation-recovery')
        assert (output/'parent-stop.json').is_file()
