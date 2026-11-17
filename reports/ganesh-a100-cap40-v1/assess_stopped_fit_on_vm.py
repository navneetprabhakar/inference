"""Read-only full assessment after a quality-stopped fit. Never clears controller failure."""
import datetime as dt,fcntl,json
from pathlib import Path
from cloud_training.nano_recovery_gate import inspect,digest,timestamp
from cloud_training.nano_recovery_tasks import probe_all
R=Path('/opt/english-eager');r=json.loads((R/'pilot-request.json').read_text());C=R/'runs/ganesh-recovery-next/controller';state=json.loads((C/'state.json').read_text())
assert state['running'] is None and state['failed']['id']=='fit_train'
result=R/'runs/ganesh-recovery-next/fit/result.json';j=json.loads(result.read_text())
assert j['reason']=='quality_regression_stop' and j['quality_accepted'] is False
assert any(g['stopped'] for g in j['quality_guards'].values())
assert 0<j['step']<=64
lock=Path('/tmp/ganesh-gpu-writer.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
gate=inspect(R,r,'fit');assert gate['allowed'],gate
assert (timestamp(r['provider_stop_utc'])-dt.datetime.now(dt.timezone.utc)).total_seconds()>7200+600+r['backup_reserve_seconds']
P=R/'stopped-fit-assessment';P.mkdir(exist_ok=False)
(P/'intent.json').write_text(json.dumps({'scope':'Read-only assessment; original failed controller and stopped quality guards preserved; no training or curriculum authorization','checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'original_controller_sha256':digest(C/'state.json'),'training_result_sha256':digest(result),'request_spec_sha256':r['authorization']['spec_sha256'],'step':j['step'],'best_step':j['best_development_step'],'gate':gate},indent=2)+'\n')
t=next(t for t in r['tasks'] if t['id']=='fit_probes');assert t['timeout_seconds']==7200 and t['per_probe_seconds']==1800
probe_all(r,t,R)
assert digest(C/'state.json')==json.loads((P/'intent.json').read_text())['original_controller_sha256']
(P/'complete.json').write_text(json.dumps({'status':'full_raw_probes_collected_requires_review','receipt_sha256':digest(R/t['result']),'quality_accepted':False,'training_restart_forbidden':True},indent=2)+'\n')
print((P/'complete.json').read_text())
