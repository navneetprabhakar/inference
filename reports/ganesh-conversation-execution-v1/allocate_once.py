"""One A10040 create; durable intent, no retry and no learning dispatch."""
import datetime as dt,fcntl,hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];R=ROOT/'runs/ganesh-conversation-execution-v1'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,data):
 p=P/name
 if p.exists():raise FileExistsError(p)
 p.write_text(json.dumps(data,indent=2)+'\n')
def run(cmd,timeout=120):return subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=timeout).stdout
with (P/'allocation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if (P/'allocation-intent.json').exists():raise RuntimeError('Attempt already exists; reconcile, never automatically retry')
 auth=json.loads((P/'authorization.json').read_text());assert auth['approved'] is True and auth['approved_usd']==25
 readiness=json.loads((P/'local-readiness.json').read_text());assert readiness['status']=='pass' and readiness['tests']==218
 for name,h in readiness['evidence'].items():assert sha(P/name)==h
 for kind in ('instances','disks'):
  inventory=json.loads(run(['gcloud','compute',kind,'list','--project=executespecv1','--format=json']))
  assert inventory==[],('Existing resources',kind)
 now=dt.datetime.now(dt.timezone.utc);stop=now+dt.timedelta(minutes=195);stamp=lambda d:d.strftime('%Y-%m-%dT%H:%M:%SZ')
 name='ganesh-conv-'+now.strftime('%m%d-%H%M%S');prefix='gs://forge-ownbase-a100-20261110/ganesh-conversation-execution-v1/'+name
 cfg=json.loads((P/'config-template.json').read_text());cfg.update(instance=name,zone='us-central1-c',lease_start_utc=stamp(now),provider_stop_utc=stamp(stop),backup_prefix=prefix)
 price=json.loads((P/'price-refresh.json').read_text());bound=196/60*(price['machine_usd_per_hour']+200*price['disk_usd_per_gib_hour'])*1.25+7
 assert bound<=25
 write('config.json',cfg);config_uri=prefix+'/inputs/config.json'
 run(['gcloud','storage','cp',str(P/'config.json'),config_uri,'--if-generation-match=0','--quiet'])
 readback=R/'config.readback';run(['gcloud','storage','cp',config_uri,str(readback),'--quiet']);assert sha(readback)==sha(P/'config.json');readback.unlink()
 inputs=json.loads((P/'input-backups.json').read_text());runtime,packet=inputs
 assert all(x['readback_verified'] for x in inputs) and runtime['sha256']==readiness['runtime_sha256']
 image=json.loads((P/'image.json').read_text())['selfLink'].split('/projects/',1)[1]
 metadata=','.join(['own-deadline-utc='+stamp(stop),'bundle-uri='+runtime['uri'],'bundle-sha256='+runtime['sha256'],'packet-uri='+packet['uri'],'packet-sha256='+packet['sha256'],'config-uri='+config_uri,'config-sha256='+sha(P/'config.json'),'enable-oslogin=TRUE','block-project-ssh-keys=TRUE'])
 cmd=['gcloud','compute','instances','create',name,'--project=executespecv1','--zone=us-central1-c','--machine-type=a2-highgpu-1g','--provisioning-model=STANDARD','--maintenance-policy=TERMINATE','--no-restart-on-failure','--termination-time='+stamp(stop),'--instance-termination-action=STOP','--boot-disk-size=200GB','--boot-disk-type=pd-balanced','--no-boot-disk-auto-delete','--image=projects/'+image,'--service-account=forge-ownbase-bench@executespecv1.iam.gserviceaccount.com','--scopes=https://www.googleapis.com/auth/devstorage.read_write','--no-address','--tags=ganesh-a100-cap40-iap','--subnet=default','--metadata='+metadata,'--metadata-from-file=startup-script='+str(P/'bootstrap.sh'),'--quiet','--format=json','--async']
 write('launch-request.json',{'argv':cmd,'config_sha256':sha(P/'config.json'),'bootstrap_sha256':sha(P/'bootstrap.sh'),'local_readiness_sha256':sha(P/'local-readiness.json'),'adverse_review_sha256':sha(P/'ADVERSE_REVIEW.md'),'price_refresh_sha256':sha(P/'price-refresh.json'),'cost_upper_usd':bound,'approved_usd':25})
 write('allocation-intent.json',{'instance':name,'zone':'us-central1-c','requested_utc':stamp(now),'provider_stop_utc':stamp(stop),'status':'in_flight','approved_usd':25,'upper_cost_usd':bound})
 result=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
 write('allocation-response.json',{'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
 if result.returncode:raise RuntimeError('Allocation failed; reconcile before any action; no retry')
 print(json.dumps({'status':'allocation_submitted','instance':name,'stop_utc':stamp(stop),'cost_upper_usd':bound}))
