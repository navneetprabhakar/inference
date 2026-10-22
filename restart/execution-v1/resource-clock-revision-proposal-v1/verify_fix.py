"""No-model real-subprocess regression for the proposed supervisor-only change."""
import hashlib,json,sys,time,types
from pathlib import Path
from slm.restart import supervisor as original
root=Path(__file__).resolve().parent
patched=types.ModuleType('slm.restart.resource_clock_proposed');patched.__package__='slm.restart';patched.__file__=original.__file__
exec(compile((root/'supervisor-proposed.py').read_text(),str(root/'supervisor-proposed.py'),'exec'),patched.__dict__)
records=[]
for name,module,mode,wanted in [('original-race',original,'race','STOP'),('proposed-race',patched,'race','PASS'),
                               ('proposed-future-heartbeat',patched,'future','STOP'),('proposed-rss',patched,'rss','STOP'),
                               ('proposed-future-sample',patched,'sample','STOP')]:
    output=root/name;output.mkdir()
    budget=original.TimeBudget(output/'time.sqlite',identity=name,seconds_cap=5,deadline_utc=time.time()+30)
    def telemetry(pid,cwd,baseline):
        sampled=time.monotonic()
        # Reproduce the native collection/read ordering with a genuine later clock.
        time.sleep(.003)
        heartbeat=time.monotonic()+(10 if mode=='future' else 0)
        original.atomic_json(output/'heartbeat.json',dict(pid=pid,monotonic=heartbeat))
        return dict(now=sampled+(10 if mode=='sample' else 0),rss_gib=19 if mode=='rss' else 1,swap_growth_mib=0,free_disk_gib=100,thermal='nominal')
    result=module.supervise([sys.executable,'-c','import time;time.sleep(.3)'],cwd=output,env={'PATH':'/usr/bin:/bin'},
        heartbeat=output/'heartbeat.json',budget=budget,receipt=output/'supervisor.json',tick=.05,telemetry=telemetry,baseline_reader=lambda:0)
    assert result['status']==wanted,(name,result)
    rows=original.verify_resource_history(output/'supervisor.json')
    if mode=='race' and module is original:assert result['reason']=='StopRun: invalid resource telemetry'
    if mode=='race' and module is patched:
        samples=rows[1:-1];assert samples
        assert all(r['resource_sample_started_monotonic']<r['measurement']['heartbeat_at']<=r['measurement']['now'] for r in samples)
    records.append(dict(case=name,status=result['status'],expected=wanted,reason=result['reason'],receipt_sha256=hashlib.sha256((output/'supervisor.json').read_bytes()).hexdigest()))
    budget.db.close()
result=dict(status='PROPOSED_FIX_REGRESSION_PASS',cases=records,model_operations=False,current_source_modified=False)
(root/'regression-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
