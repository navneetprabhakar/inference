"""Real subprocess checks for the telemetry/heartbeat read-order race."""
import json
import sys
import time
import pytest
from slm.restart.supervisor import TimeBudget, supervise, atomic_json, verify_resource_history


@pytest.mark.parametrize('mode,wanted',[
    ('race','PASS'),('future-heartbeat','STOP'),('future-sample','STOP'),
    ('nan-sample','STOP'),('rss','STOP'),
])
def test_fresh_heartbeat_during_sampling_and_invalid_telemetry(tmp_path,mode,wanted):
    budget=TimeBudget(tmp_path/'time.sqlite',identity=mode,seconds_cap=5,deadline_utc=time.time()+20)
    def telemetry(pid,cwd,baseline):
        sampled=time.monotonic();time.sleep(.003)
        heartbeat=time.monotonic()+(10 if mode=='future-heartbeat' else 0)
        atomic_json(tmp_path/'heartbeat.json',dict(pid=pid,monotonic=heartbeat))
        if mode=='future-sample':sampled+=10
        if mode=='nan-sample':sampled=float('nan')
        return dict(now=sampled,rss_gib=19 if mode=='rss' else 1,
                    swap_growth_mib=0,free_disk_gib=100,thermal='nominal')
    try:
        result=supervise([sys.executable,'-c','import time;time.sleep(.35)'],cwd=tmp_path,
            env={'PATH':'/usr/bin:/bin'},heartbeat=tmp_path/'heartbeat.json',budget=budget,
            receipt=tmp_path/'receipt.json',tick=.05,telemetry=telemetry,baseline_reader=lambda:0)
        assert result['status']==wanted,result
        if mode=='race':
            rows=verify_resource_history(tmp_path/'receipt.json')[1:-1]
            assert rows and all(r['resource_sample_started_monotonic']<r['measurement']['heartbeat_at']<=r['measurement']['now'] for r in rows)
        elif mode=='rss':assert 'RSS' in result['reason']
        else:assert 'clock' in result['reason']
    finally:budget.db.close()
