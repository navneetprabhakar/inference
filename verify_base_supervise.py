"""CPU-only real subprocess checks of bounded supervision; no model loading."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from base_supervise import supervise

WORKER = '''import json,hashlib,time,sys,os
from pathlib import Path
spec=json.loads(Path(sys.argv[1]).read_bytes());run=Path(sys.argv[2]);run.mkdir(exist_ok=True)
count=run/'count';n=int(count.read_text()) if count.exists() else 0;count.write_text(str(n+1))
state=spec['steps'][min(n,len(spec['steps'])-1)]
if state=='preflight-resource':
 print('guards.ResourceStop: resource threshold: thermal=2',flush=True);sys.exit(1)
if state=='preflight-invalid':
 print('ValueError: immutable identity changed',flush=True);sys.exit(1)
record=dict(spec={'identity':{'protocol':spec}},state=state,reason='test resource' if state=='paused-resource' else '',started=time.time(),active_seconds=0,reserved_tokens=0,lease_active_base=0,lease_allowance=1)
if state=='budget':record.update(state='paused-resource',reserved_tokens=spec['target_tokens'],reason='target token ceiling exhausted')
if state=='stop':record.update(state='paused-resource',reason='explicit STOP');(run/'STOP').touch()
raw=json.dumps(record,sort_keys=True,separators=(',',':'),allow_nan=False).encode();record['sha256']=hashlib.sha256(raw).hexdigest()
(run/'campaign.json').write_text(json.dumps(record))
if state=='running':os._exit(9)
if state=='stop':time.sleep(.5)
'''

def run():
    with TemporaryDirectory() as directory:
        root=Path(directory);trainer=root/'fake_worker.py';trainer.write_text(WORKER)
        def case(name,steps,expected,launches,**kw):
            spec=root/(name+'.json');spec.write_text(json.dumps(dict(steps=steps,lease_seconds=1,active_seconds=30,calendar_seconds=1000,target_tokens=100)))
            target=root/name
            actual=supervise(spec,target,trainer=trainer,poll_seconds=.01,cooldown=.02,resource_limit=.07,**kw)
            assert actual==expected,(name,actual)
            status=json.loads((root/(name+'-supervisor.json')).read_bytes())
            assert status['launches']==launches,(name,status)
            return spec,target,status
        spec,target,status=case('leases',['paused-lease','completed'],'completed',2)
        assert supervise(spec,target,trainer=trainer)=='completed'
        assert int((target/'count').read_text())==2
        _,_,status=case('crashes',['running'],'crash-limit',3)
        assert status['crash_recoveries']==2
        case('resource-recovered',['paused-resource','completed'],'completed',2)
        _,_,recovered=case('lease-preflight',['paused-lease','preflight-resource','completed'],'completed',3)
        assert recovered['crash_recoveries']==0
        case('lease-invalid',['paused-lease','preflight-invalid'],'failed',2)
        # Time spent running subprocesses also consumes the one-hour retry window.
        spec=root/'resource.json';spec.write_text(json.dumps(dict(steps=['paused-resource'],lease_seconds=1,active_seconds=30,calendar_seconds=1000,target_tokens=100)))
        assert supervise(spec,root/'resource',trainer=trainer,poll_seconds=.01,cooldown=.02,resource_limit=.12)=='resource-timeout'
        spec=root/'preflight-timeout.json';spec.write_text(json.dumps(dict(steps=['paused-lease','preflight-resource'],lease_seconds=1,active_seconds=30,calendar_seconds=1000,target_tokens=100)))
        assert supervise(spec,root/'preflight-timeout',trainer=trainer,poll_seconds=.01,cooldown=.02,resource_limit=.12)=='resource-timeout'
        unchanged=json.loads((root/'preflight-timeout'/'campaign.json').read_bytes())
        assert unchanged['state']=='paused-lease' and unchanged['reserved_tokens']==0
        case('budget',['budget'],'budget-exhausted',1)
        case('failure',['failed'],'failed',1)
        case('divergence',['diverged'],'diverged',1)
        _,target,_=case('stop',['stop'],'stopped',1)
        assert (target/'STOP').exists()
        # A changed spec cannot cause another launch under persisted supervision.
        spec=root/'leases.json';changed=json.loads(spec.read_bytes());changed['target_tokens']=99;spec.write_text(json.dumps(changed))
        try:supervise(spec,root/'leases',trainer=trainer)
        except ValueError:pass
        else:raise AssertionError('changed spec resumed')
        (root/'STOP').touch()
        case('prestop',['completed'],'stopped',0)
    print('PASS real CPU subprocess lease resume, terminal states, two-crash ceiling, bounded resource retry, STOP and frozen identity')

if __name__=='__main__':run()
