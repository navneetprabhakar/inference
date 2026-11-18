"""Explicitly reconciled provider-suggested zone handoff; same cap and fixed expiry."""
import datetime as dt,fcntl,hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,v):
 path=P/name
 if path.exists():raise FileExistsError(path)
 path.write_text(json.dumps(v,indent=2)+'\n')
def run(cmd):return subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=120).stdout
with (P/'allocation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 prior=json.loads((P/'allocation-operation-final.json').read_text());assert prior['status']=='DONE'
 errors=prior['error']['errors'];assert all(x['code']=='ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS' for x in errors)
 zones=[d.get('errorInfo',{}).get('metadatas',{}).get('zonesAvailable') for e in errors for d in e.get('errorDetails',[])]
 assert 'us-central1-f' in zones
 for kind in ('instances','disks'):
  v=json.loads(run(['gcloud','compute',kind,'list','--project=executespecv1','--format=json']));assert v==[]
 cfg=json.loads((P/'config.json').read_text());cfg['zone']='us-central1-f';stop=dt.datetime.fromisoformat(cfg['provider_stop_utc'].replace('Z','+00:00'))
 assert (stop-dt.datetime.now(dt.timezone.utc)).total_seconds()>175*60,'Too little remaining time; no lease extension'
 readiness=json.loads((P/'local-readiness.json').read_text())
 for name,h in readiness['evidence'].items():assert sha(P/name)==h,name
 write('config-us-central1-f.json',cfg);uri=cfg['backup_prefix']+'/inputs/config-us-central1-f.json'
 run(['gcloud','storage','cp',str(P/'config-us-central1-f.json'),uri,'--if-generation-match=0','--quiet'])
 readback=ROOT/'runs/ganesh-conversation-execution-v1/config-f.readback';run(['gcloud','storage','cp',uri,str(readback),'--quiet']);assert sha(readback)==sha(P/'config-us-central1-f.json');readback.unlink()
 old=json.loads((P/'launch-request.json').read_text());cmd=[]
 for a in old['argv']:
  if a=='--zone=us-central1-c':a='--zone=us-central1-f'
  if a.startswith('--metadata='):
   parts=a[len('--metadata='):].split(',');parts=[('config-uri='+uri if x.startswith('config-uri=') else 'config-sha256='+sha(P/'config-us-central1-f.json') if x.startswith('config-sha256=') else x) for x in parts];a='--metadata='+','.join(parts)
  cmd.append(a)
 assert '--termination-time='+cfg['provider_stop_utc'] in cmd and '--no-boot-disk-auto-delete' in cmd
 write('zone-handoff-intent.json',{'status':'in_flight','instance':cfg['instance'],'zone':cfg['zone'],'provider_stop_utc':cfg['provider_stop_utc'],'approved_usd':25,'upper_cost_usd':old['cost_upper_usd'],'prior_operation_sha256':sha(P/'allocation-operation-final.json'),'prior_attempt_reconciled_instances':0,'prior_attempt_reconciled_disks':0,'authority':'Earlier explicit user instruction: keep checking in other zones; same new$25cap, same GPU, unchanged absolute lease. No automatic background retry loop.','argv':cmd})
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
 write('zone-handoff-response.json',{'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
 if r.returncode:raise RuntimeError('Zone handoff failed; reconcile; no loop')
 print(r.stdout)
