"""Fresh A100 qualification lease, explicitly authorized by next-class request."""
import datetime as dt, hashlib, json, subprocess, sys, tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from cloud_training.nano_l4_lease import plan
P=Path(__file__).parent;OLD=P.parent/'english-first-v1';R=ROOT/'runs/english-a100-v1';R.mkdir(exist_ok=True)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def cloud(*args):return json.loads(subprocess.check_output(['gcloud',*args,'--format=json'],text=True,timeout=60))
require(not (P/'launch-request.json').exists(),'Immutable request already exists')
ledger=json.loads((OLD/'spend-ledger.json').read_text())
require(ledger['active_allocations']==0 and all(a['state']=='closed_capacity_unavailable' and a['no_new_vm_or_disk_verified'] for a in ledger['allocations']),'Prior allocation unresolved')
instances=cloud('compute','instances','list','--project=executespecv1')
require(all(i['status']=='TERMINATED' for i in instances),'Compute already active')
(P/'cloud-before.json').write_text(json.dumps(instances,indent=2)+'\n')
image=json.loads((OLD/'image-status.json').read_text())['name']
got=cloud('compute','images','describe',image,'--project=deeplearning-platform-release')
require(got['status']=='READY' and not got.get('deprecated'),'Image unavailable')
for name,digest in json.loads((OLD/'packet-freeze.json').read_text())['files'].items():require(sha(OLD/name)==digest,'Frozen input changed: '+name)
runtime=ROOT/'runs/english-first-v1/runtime.tar.gz';proof=json.loads((OLD/'input-backup-receipt.json').read_text())['files'][0]
require(proof['independent_readback'] and sha(runtime)==proof['sha256'],'Runtime integrity')
manifest=json.loads((runtime.parent/'runtime.tar.gz.receipt.json').read_text())
for n,item in manifest['files'].items():
 if n.startswith('cloud_training/') and n.endswith('.py'):require(sha(ROOT/n)==item['sha256'],'Runtime source drift: '+n)
now=dt.datetime.now(dt.timezone.utc);name='forge-english-a100-'+now.strftime('%m%d-%H%M%S')
request=plan(project='executespecv1',zone='us-central1-a',name=name,image='projects/deeplearning-platform-release/global/images/'+image,service_account='forge-ownbase-bench@executespecv1.iam.gserviceaccount.com',bootstrap=str(P.resolve()/'bootstrap.sh'),now=now,hours=1.25)
rate=3.673385;compute=rate*1.25*1.25
require(compute+3.5<=10,'Budget exceeded')
request.update(machine='a2-highgpu-1g',gpu='1x A100 40GB',list_rate_usd_per_hour=rate,compute_envelope_usd=compute,run_id=name,price_source='https://cloud.google.com/products/compute/pricing/accelerator-optimized',authorization='User: check the next GPU class and keep going; unchanged $10 operational cap; qualification only')
remote='gs://forge-ownbase-a100-20261110/english-a100-v1/'+name
config=json.loads((OLD/'config.json').read_text());config.update(run_id=name,deadline_utc=request['latest_local_stop_utc'],worker_deadline_utc=(now+dt.timedelta(minutes=60)).strftime('%Y-%m-%dT%H:%M:%SZ'),backup_prefix=remote)
(P/'config.json').write_text(json.dumps(config,indent=2)+'\n')
packet=R/'packet.tar.gz'
with tarfile.open(packet,'w:gz') as tar:
 for f in ['fit-train.jsonl','development-reference.jsonl','development-suite.json','data-review.json','diagnostic-admission.json','diagnostic-manifest.json','diagnostic-contract.json']:tar.add(OLD/f,arcname='packet/'+f)
 tar.add(P/'config.json',arcname='config.json');tar.add(P/'gpu_qualify.py',arcname='gpu_qualify.py')
packet_uri=remote+'/inputs/packet.tar.gz'
metadata='--metadata=own-deadline-utc='+config['deadline_utc']+',bundle-uri='+proof['uri']+',bundle-sha256='+proof['sha256']+',packet-uri='+packet_uri+',packet-sha256='+sha(packet)+',enable-oslogin=TRUE,block-project-ssh-keys=TRUE'
request['create_argv']=[metadata if a.startswith('--metadata=') else '--machine-type=a2-highgpu-1g' if a.startswith('--machine-type=') else a for a in request['create_argv']]+['--quiet','--format=json','--async']
request.update(bootstrap_sha256=sha(P/'bootstrap.sh'),backup_prefix=remote,inputs=[proof,{'path':str(packet),'uri':packet_uri,'sha256':sha(packet)}])
(P/'launch-request.json').write_text(json.dumps(request,indent=2)+'\n')
ledger.update(authorization_context=request['authorization'],active_allocations=1)
ledger['allocations'].append({'name':name,'state':'reserved_before_provisioning','reserved_compute_usd':compute,'hours':1.25,'request_sha256':sha(P/'launch-request.json')})
(P/'spend-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
subprocess.run(['gcloud','storage','cp',str(packet),packet_uri,'--quiet','--if-generation-match=0'],check=True,timeout=120)
copy=R/'packet-readback.tar.gz';subprocess.run(['gcloud','storage','cp',packet_uri,str(copy),'--quiet'],check=True,timeout=120)
require(sha(copy)==sha(packet),'Packet readback mismatch');copy.unlink()
request['inputs'][1]['independent_readback']=True
(P/'input-backup-receipt.json').write_text(json.dumps({'all_verified':True,'files':request['inputs']},indent=2)+'\n')
print(name,compute+3.5,request['latest_local_stop_utc'])
