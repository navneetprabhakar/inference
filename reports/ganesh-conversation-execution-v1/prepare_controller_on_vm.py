"""Bind actual readback/qualification evidence; fail before any learning dispatch."""
import datetime as dt,hashlib,json,time
from pathlib import Path
from cloud_training.nano_conversation_controller import validate_request,training_argv
ROOT=Path('/opt/ganesh-conversation');P=ROOT/'reports/ganesh-conversation-execution-v1';Q=ROOT/'qualification-v2'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
cfg=json.loads((ROOT/'config-v2.json').read_text());runtime=cfg['runtime_sha256'];provider=json.loads((P/'provider-instance.json').read_text())
stop=dt.datetime.fromisoformat(cfg['provider_stop_utc'].replace('Z','+00:00')).timestamp()
assert provider['name']==cfg['instance'] and provider['status']=='RUNNING'
assert provider['scheduling']['terminationTime']==cfg['provider_stop_utc'] and provider['scheduling']['instanceTerminationAction']=='STOP' and provider['scheduling']['automaticRestart'] is False
assert len(provider['disks'])==1 and provider['disks'][0]['autoDelete'] is False and provider['disks'][0]['diskSizeGb']=='200'
assert provider['machineType'].endswith('/a2-highgpu-1g')
assert all(not n.get('accessConfigs') for n in provider['networkInterfaces'])
ready=json.loads((P/'local-readiness-v2.json').read_text());assert ready['status']=='pass' and ready['tests']==219 and ready['runtime_sha256']==runtime
# Runtime archive already extracted and validated at boot. Recheck source byte identities.
package=json.loads((ROOT/'package-manifest.json').read_text())
for name,item in package['files'].items():assert sha(ROOT/name)==item['sha256'],name
qual=json.loads((Q/'qualification.json').read_text());assert qual['status']=='pass' and qual['runtime_sha256']==runtime and qual['instance']==cfg['instance']
bench=json.loads((Q/'decode-benchmark.json').read_text());assert bench['generation_fits'] and bench['generation_seconds_upper']<=5400
# Two12min training stages + measured worst-case generation +19min scheduling allowance.
remaining=1440+bench['generation_seconds_upper']+1140
assert time.time()+remaining+1500<=stop, 'Full remaining stages plus backups do not fit; HOLD'
receipts={}
def receipt(name,**extra):
 path=P/(name+'-receipt.json');assert not path.exists()
 path.write_text(json.dumps({'status':'pass','check':name,'runtime_sha256':runtime,'instance':cfg['instance'],**extra},indent=2)+'\n');receipts[name]={'path':str(path.relative_to(ROOT)),'sha256':sha(path)}
receipt('local_tests',raw_sha256=sha(P/'local-readiness-v2.json'),tests=219)
receipt('input_readback',raw_sha256=sha(P/'input-backups.json'),runtime_archive_rechecked=True,parent_readback_verified=True)
receipt('provider_readback',raw_sha256=sha(P/'provider-instance.json'),stop_utc=cfg['provider_stop_utc'],auto_delete=False)
receipt('cuda_changed_path',raw_sha256=sha(Q/'qualification.json'),restart=qual['restart'],rollback=qual['rollback'],signal_resume=qual['signal_resume'])
receipt('measured_forecast',raw_sha256=sha(Q/'decode-benchmark.json'),remaining_seconds=remaining,measured_utc=dt.datetime.now(dt.timezone.utc).isoformat())
files={}
for folder in ('cloud_training','tools','reports/ganesh-conversation-pilot-v1','reports/ganesh-conversation-execution-v1'):
 for p in (ROOT/folder).rglob('*'):
  if p.is_file() and '__pycache__' not in p.parts:files[str(p.relative_to(ROOT))]=sha(p)
for name in ['parent/manifest.json','ancestor/manifest.json','tokenizer/tokenizer.pkl','qualification-v2/qualification.json','qualification-v2/decode-benchmark.json']:
 files[name]=sha(ROOT/name)
request={'schema':1,'experiment':'ganesh-conversation-execution-v1','machine':'a2-highgpu-1g','resource_count':1,'provider_action':'STOP','disk_auto_delete':False,'automatic_retry':False,'release_eligible':False,'files':files,'authorization':'reports/ganesh-conversation-execution-v1/authorization.json','lease_start_utc':cfg['lease_start_utc'],'provider_stop_utc':cfg['provider_stop_utc'],'training_stop_utc':dt.datetime.fromtimestamp(stop-1500,dt.timezone.utc).isoformat(),'hourly_compute_disk_usd':3.673385+200*.000136986,'storage_network_recovery_reserve_usd':7,'prior_attempt_upper_usd':0,'block_plan_sha256':'82a15f380ae90f3fd4f24904ef88886674dc6218f6345e3603223e3b17a07f5c','backup_reserve_seconds':1500,'runtime_sha256':runtime,'instance':cfg['instance'],'receipts':receipts,'parent':'parent','ancestor':'ancestor','tokenizer':'tokenizer','repo':'nanochat-source','parent_manifest_sha256':cfg['parent_manifest_sha256'],'tokenizer_sha256':cfg['tokenizer_sha256'],'backup_prefix':cfg['backup_prefix']+'/pilot'}
assert not validate_request(request,ROOT),validate_request(request,ROOT)
for arm in ('broad','control'):training_argv(request,ROOT,arm,ROOT/'pilot'/arm)
out=ROOT/'controller-request.json';assert not out.exists();out.write_text(json.dumps(request,indent=2)+'\n')
print(json.dumps({'status':'ready_for_bounded_training','remaining_forecast_seconds':remaining,'backup_reserve_seconds':1500,'quality_accepted':False}))
