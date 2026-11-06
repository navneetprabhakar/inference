"""CPU-only real subprocess verification of the prospective optimizer supervisor."""
import fcntl
import json
from pathlib import Path
import tempfile
import threading
import time
from unittest.mock import patch
from optimizer_ablation_supervise import (supervise, signed_write, signed_read, digest, canonical,
                                          disk_reserve, atomic, parent_wait_reason, parent_record)

WORKER = '''import json,hashlib,time,sys,os
from pathlib import Path
spec=json.loads(Path(sys.argv[1]).read_bytes());run=Path(sys.argv[2]);run.mkdir(exist_ok=True)
count=run/'count';n=int(count.read_text()) if count.exists() else 0;count.write_text(str(n+1))
state=spec['test_states'][min(n,len(spec['test_states'])-1)]
if state=='preflight-resource':
 print('resource threshold: thermal=2',flush=True);sys.exit(1)
if state=='preflight-invalid':sys.exit(2)
def save(record):
 raw=json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
 record['sha256']=hashlib.sha256(raw).hexdigest()
 (run/'campaign.json').write_text(json.dumps(record))
cs={'identity':{'protocol':spec}}
(run/'campaign-spec.json').write_text(json.dumps(cs))
record=dict(spec=cs,state=state,reason='',started=time.time(),active_seconds=.001,
 reserved_tokens=0,trained_tokens=0,lease_active_base=0,lease_allowance=.01)
if state=='completed':record.update(reserved_tokens=spec['target_tokens'],trained_tokens=spec['target_tokens'])
if state=='partial':record.update(state='completed',reserved_tokens=spec['target_tokens'],trained_tokens=1)
if state=='budget':record.update(state='paused-resource',reserved_tokens=spec['target_tokens'])
if state=='stop':record.update(state='paused-resource',reason='explicit STOP');(run/'STOP').touch()
save(record)
if state=='running':os._exit(9)
'''
REPORTER = '''import json,sys
from pathlib import Path
Path(sys.argv[sys.argv.index('--output')+1]).write_text(json.dumps({'selection':'not-a-quality-pass'}))
'''


def fixture(root, states=None):
    root.mkdir()
    worker=root/'worker.py'; worker.write_text(WORKER)
    reporter=root/'reporter.py'; reporter.write_text(REPORTER)
    protocol=root/'protocol.json'; protocol.write_text('{}')
    parent=root/'foundation'; parent.mkdir()
    original=root/'foundation-budget.json'
    base=Path(__file__).with_name('base_train.py').resolve()
    original.write_text(json.dumps({'code_sha256':{str(base):digest(base)}}))
    cs={'identity':{'protocol':json.loads(original.read_text())}}
    (parent/'campaign-spec.json').write_bytes(canonical(cs))
    blob=parent/'step-000001.pt'; blob.write_bytes(b'tiny-cpu-fixture')
    entry=dict(file=blob.name,bytes=blob.stat().st_size,sha256=digest(blob))
    (parent/'latest.json').write_text(json.dumps([entry]));(parent/'protected.json').write_text(json.dumps([blob.name]))
    record=dict(spec=cs,state='completed',trained_tokens=99_999_744,reserved_tokens=99_999_744,checkpoints=[entry])
    signed_write(parent/'campaign.json',record)
    (parent/'status.json').write_text(json.dumps({'timestamp':time.time()}))
    ps=dict(state='completed',updated=time.time(),resource_since=None,
            identity=dict(spec=str(original),spec_sha256=digest(original),trainer=str(base),trainer_sha256=digest(base)))
    parent.with_name(parent.name+'-supervisor.json').write_text(json.dumps(ps))
    arms=[]
    for i in range(3):
        template=root/f'template-{i}.json'
        template.write_text(json.dumps(dict(target_tokens=100,active_seconds=.1,calendar_seconds=1000,
                  lease_seconds=.01,test_states=(states or [['completed']]*3)[i])))
        arms.append(dict(name=str(i),run=str(root/f'arm-{i}'),template=str(template),template_sha256=digest(template)))
    spec=dict(schema=1,parent=dict(run=str(parent),spec=str(original),spec_sha256=digest(original),required_trained_tokens=99_999_744),
              arms=arms,active_seconds=.3,target_tokens=300,calendar_seconds=1000,
              code_sha256={str(worker):digest(worker),str(reporter):digest(reporter)},protocol_path=str(protocol),protocol_sha256=digest(protocol))
    # Floating point sum .1+.1+.1 exceeds .3; use an exactly representable budget.
    spec['active_seconds']=1
    path=root/'experiment.json'; path.write_text(json.dumps(spec))
    return path,root/'experiment-run',worker,reporter,parent


def run_case(args, **kw):
    path,directory,worker,reporter,parent=args
    options=dict(trainer=worker,reporter=reporter,parent_verifier=lambda _:None,
                 poll_seconds=.005,cooldown=.01,resource_limit=.2,disk_free=lambda _:10**15)
    options.update(kw)
    return supervise(path,directory,**options)


def set_parent_waiting(args, ledger_state, supervisor_state, *, status_age=0, supervisor_age=0,
                       resource_age=None):
    parent=args[4]
    record=signed_read(parent/'campaign.json');record['state']=ledger_state
    signed_write(parent/'campaign.json',record)
    path=parent.with_name(parent.name+'-supervisor.json')
    value=json.loads(path.read_bytes())
    value.update(state=supervisor_state,updated=time.time()-supervisor_age,
                 resource_since=time.time()-resource_age if resource_age is not None else None)
    atomic(path,value)
    atomic(parent/'status.json',{'timestamp':time.time()-status_age})


def run():
    count=0
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        a=fixture(root/'sequential',[['paused-lease','completed'],['paused-resource','completed'],['completed']])
        assert run_case(a)=='completed';count+=1
        state=signed_read(a[1]/'supervisor.json')
        assert [v['launches'] for v in state['arms']]==[2,2,1]
        assert state['comparison_sha256']==digest(a[1]/'comparison.json')
        assert run_case(a)=='completed';count+=1
        for name,states,expected,launches in [
            ('crash',[['running'],['completed'],['completed']],'crash-limit',3),
            ('stop',[['stop'],['completed'],['completed']],'stopped',1),
            ('failed',[['failed'],['completed'],['completed']],'failed',1),
            ('diverged',[['diverged'],['completed'],['completed']],'diverged',1),
            ('partial',[['partial'],['completed'],['completed']],'budget-exhausted',1),
            ('budget',[['budget'],['completed'],['completed']],'budget-exhausted',1),
            ('preflight',[['paused-lease','preflight-resource','completed'],['completed'],['completed']],'completed',3),
            ('preflightbad',[['paused-lease','preflight-invalid'],['completed'],['completed']],'failed',2)]:
            a=fixture(root/name,states);assert run_case(a)==expected,name
            state=signed_read(a[1]/'supervisor.json');assert state['arms'][0]['launches']==launches,name
            if expected!='completed':assert state['arms'][1]['launches']==0,name
            count+=1
        a=fixture(root/'resource',[['paused-resource'],['completed'],['completed']])
        assert run_case(a)=='resource-timeout';count+=1
        a=fixture(root/'disk')
        assert supervise(a[0],a[1],trainer=a[2],reporter=a[3],parent_verifier=lambda _:None,
                         poll_seconds=.005,cooldown=.01,resource_limit=.03,disk_free=lambda _:0)=='resource-timeout'
        assert signed_read(a[1]/'supervisor.json')['arms'][0]['launches']==0;count+=1
        a=fixture(root/'disk-threshold')
        spec=json.loads(a[0].read_text())
        parent_bytes=(a[4]/'step-000001.pt').stat().st_size
        required=20*1024**3+disk_reserve(spec,[None]*3,parent_bytes)
        assert supervise(a[0],a[1],trainer=a[2],reporter=a[3],parent_verifier=lambda _:None,
                         poll_seconds=.005,cooldown=.01,resource_limit=.03,
                         disk_free=lambda _:required-1)=='resource-timeout'
        assert signed_read(a[1]/'supervisor.json')['arms'][0]['launches']==0;count+=1
        a=fixture(root/'disk-exact-threshold')
        spec=json.loads(a[0].read_text())
        required=20*1024**3+disk_reserve(spec,[None]*3,(a[4]/'step-000001.pt').stat().st_size)
        assert supervise(a[0],a[1],trainer=a[2],reporter=a[3],parent_verifier=lambda _:None,
                         poll_seconds=.005,cooldown=.01,resource_limit=.2,
                         disk_free=lambda _:required)=='completed';count+=1
        # An oversized orphan may fill its own arm's forecast but cannot consume
        # reservations for the other two arms. Completed arms need no more pairs.
        a=fixture(root/'disk-orphan-credit');spec=json.loads(a[0].read_text())
        parent_bytes=100*1024**2;estimate=110*1024**2+16*1024**2
        arm=Path(spec['arms'][0]['run']);arm.mkdir()
        with (arm/'orphan.pt').open('wb') as f:f.truncate(10*estimate)
        assert disk_reserve(spec,[None]*3,parent_bytes)==5*estimate+256*1024**2
        assert disk_reserve(spec,[{'state':'completed'},None,None],parent_bytes)==5*estimate+256*1024**2
        (arm/'orphan.pt').unlink()
        assert disk_reserve(spec,[{'state':'completed'},None,None],parent_bytes)==5*estimate+256*1024**2
        count+=1
        for mode in ['failed','diverged','interrupted','partial','unprotected','badbytes']:
            a=fixture(root/('parent-'+mode));p=a[4];record=signed_read(p/'campaign.json')
            if mode in ['failed','diverged','interrupted']:record['state']=mode
            elif mode=='partial':record['trained_tokens']=1
            elif mode=='unprotected':(p/'protected.json').write_text('[]')
            elif mode=='badbytes':(p/'step-000001.pt').write_bytes(b'changed')
            signed_write(p/'campaign.json',record)
            assert run_case(a)=='parent-rejected',mode;count+=1
        # Completed ledger must wait for parent supervisor and global GPU lock release.
        a=fixture(root/'parent-exit-race');p=a[4];sp=p.with_name(p.name+'-supervisor.json')
        value=json.loads(sp.read_text());value['state']='running';sp.write_text(json.dumps(value))
        lock=(p.parent/'mps.lock').open('a+b');fcntl.flock(lock,fcntl.LOCK_EX)
        def release():
            time.sleep(.04);value['state']='completed';sp.write_text(json.dumps(value))
            time.sleep(.04);lock.close()
        t=threading.Thread(target=release);t.start();assert run_case(a)=='completed';t.join();count+=1
        a=fixture(root/'waiting-stop');p=a[4];record=signed_read(p/'campaign.json');record['state']='running';signed_write(p/'campaign.json',record)
        set_parent_waiting(a,'running','running')
        t=threading.Thread(target=lambda:(time.sleep(.04),(p/'STOP').touch()));t.start()
        assert run_case(a)=='stopped';t.join();assert signed_read(a[1]/'supervisor.json')['arms'][0]['launches']==0;count+=1
        a=fixture(root/'stale');p=a[4];record=signed_read(p/'campaign.json');record['state']='running';signed_write(p/'campaign.json',record)
        set_parent_waiting(a,'running','running',status_age=900,supervisor_age=900)
        assert run_case(a)=='parent-rejected';count+=1
        a=fixture(root/'calendar');p=a[4];record=signed_read(p/'campaign.json');record['state']='running';signed_write(p/'campaign.json',record)
        set_parent_waiting(a,'running','running')
        s=json.loads(a[0].read_text());s['calendar_seconds']=.02;a[0].write_text(json.dumps(s))
        assert run_case(a)=='budget-exhausted';count+=1
        # Parent recovery must not be mistaken for a terminal foundation failure.
        for label, ledger_state, supervisor_state, age in [
                ('interrupted-ready','interrupted','ready',None),
                ('interrupted-relaunched','interrupted','running',None),
                ('resource-cooldown','paused-resource','cooldown',900),
                ('lease-preflight-cooldown','paused-lease','cooldown',900),
                ('active-old-supervisor','running','running',None)]:
            a=fixture(root/label)
            active=label=='active-old-supervisor'
            set_parent_waiting(a,ledger_state,supervisor_state,status_age=0 if active else 900,
                               supervisor_age=900 if active else 0,resource_age=age)
            no_early_launch=[]
            def recover(args=a):
                time.sleep(.04)
                no_early_launch.append(all(not Path(x['run']).exists() for x in json.loads(args[0].read_bytes())['arms']))
                parent=args[4];record=signed_read(parent/'campaign.json');record['state']='completed'
                signed_write(parent/'campaign.json',record)
                path=parent.with_name(parent.name+'-supervisor.json');value=json.loads(path.read_bytes())
                value.update(state='completed',updated=time.time());atomic(path,value)
            t=threading.Thread(target=recover);t.start()
            result=run_case(a,resource_limit=3600)
            assert result=='completed',(label,result,signed_read(a[1]/'supervisor.json')['reason'])
            t.join();assert no_early_launch==[True];count+=1
        for label, ledger_state, supervisor_state, status_age, supervisor_age, resource_age, expected in [
                ('recovery-terminal','paused-resource','failed',900,0,900,'parent-rejected'),
                ('recovery-supervisor-interrupted','interrupted','interrupted',0,0,None,'parent-rejected'),
                ('recovery-stale-ready','interrupted','ready',900,900,None,'parent-rejected'),
                ('recovery-stale-cooldown','paused-resource','cooldown',900,900,1000,'parent-rejected'),
                ('recovery-window','paused-resource','cooldown',900,0,3601,'resource-timeout')]:
            a=fixture(root/label)
            set_parent_waiting(a,ledger_state,supervisor_state,status_age=status_age,
                               supervisor_age=supervisor_age,resource_age=resource_age)
            assert run_case(a,resource_limit=3600)==expected,label
            assert signed_read(a[1]/'supervisor.json')['arms'][0]['launches']==0;count+=1
        a=fixture(root/'recovery-identity')
        set_parent_waiting(a,'paused-resource','cooldown',status_age=900,resource_age=900)
        path=a[4].with_name(a[4].name+'-supervisor.json');value=json.loads(path.read_bytes())
        value['identity']['trainer_sha256']='0'*64;atomic(path,value)
        assert run_case(a,resource_limit=3600)=='parent-rejected';count+=1
        a=fixture(root/'cooldown-stop')
        set_parent_waiting(a,'paused-resource','cooldown',status_age=900,resource_age=900)
        t=threading.Thread(target=lambda:(time.sleep(.04),(a[4]/'STOP').touch()));t.start()
        assert run_case(a,resource_limit=3600)=='stopped';t.join()
        assert signed_read(a[1]/'supervisor.json')['arms'][0]['launches']==0;count+=1
        # A fresh launch timestamp is a finite grace, not indefinite permission.
        record={'state':'running'};supervision={'state':'running','updated':10000}
        assert parent_wait_reason(record,supervision,{'timestamp':9000},now=10000)
        try:parent_wait_reason(record,supervision,{'timestamp':9000},now=10601)
        except ValueError:pass
        else:raise AssertionError('stale falsely-running parent admitted indefinitely')
        count+=1
        # Fresh cooldown publications do not reset the original resource deadline.
        supervision={'state':'cooldown','updated':10000,'resource_since':9000}
        assert parent_wait_reason({'state':'paused-resource'},supervision,{'timestamp':9000},now=10000)
        supervision['updated']=12600
        try:parent_wait_reason({'state':'paused-resource'},supervision,{'timestamp':9000},now=12600)
        except TimeoutError:pass
        else:raise AssertionError('cooldown publications reset parent resource deadline')
        count+=1
        a=fixture(root/'parent-completion-read-race');first=[True]
        def raced_record(spec):
            value=parent_record(spec)
            if first[0]:
                first[0]=False;value['state']='running'
            return value
        with patch('optimizer_ablation_supervise.parent_record',raced_record):
            assert run_case(a)=='completed'
        count+=1
        a=fixture(root/'tamper');assert run_case(a)=='completed'
        state=json.loads((a[1]/'supervisor.json').read_text());state['arms'][0]['launches']=999
        (a[1]/'supervisor.json').write_text(json.dumps(state))
        try:run_case(a)
        except ValueError:pass
        else:raise AssertionError('tampered supervisor accepted')
        count+=1
        a=fixture(root/'identity');assert run_case(a)=='completed'
        a[2].write_text(WORKER+'\n# changed\n')
        try:run_case(a)
        except ValueError:pass
        else:raise AssertionError('changed code accepted')
        count+=1
    print(f'PASS {count} CPU cases, including real subprocesses: parent/lease/resource/STOP/budget/identity/reporting; no GPU or live run touched')

if __name__=='__main__':run()
