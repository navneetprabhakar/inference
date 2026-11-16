"""Stage/read back approved inputs, then bind a fresh lease; does not provision."""
import datetime as dt,hashlib,json,subprocess,tarfile
from pathlib import Path
ROOT=Path.cwd();P=ROOT/'reports/english-cap15-v2';R=ROOT/'runs/english-cap15-v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def call(a):return subprocess.run(a,check=True,capture_output=True,text=True,timeout=600)
def cp(a,b,exclusive=False):return call(['gcloud','storage','cp',str(a),str(b),'--quiet',*(['--if-generation-match=0'] if exclusive else [])])
assert not (P/'launch-request.json').exists()
proof=json.loads((P/'local-preflight.json').read_text())
for n,h in proof['bound_files'].items():assert sha(ROOT/n)==h
assert json.loads((P/'image.json').read_text())['status']=='READY'
assert json.loads((P/'subnet.json').read_text())['privateIpGoogleAccess']
assert all(x['status']=='TERMINATED' for x in json.loads((P/'instances-before.json').read_text()))
archive=ROOT/'runs/english-local-readiness-v1/runtime-final.tar.gz'
uri='gs://forge-ownbase-a100-20261110/english-cap15-v2/inputs/runtime-'+sha(archive)+'.tar.gz'
readback=R/'runtime-readback.tar.gz';cp(uri,readback);assert sha(readback)==sha(archive);readback.unlink()
now=dt.datetime.now(dt.timezone.utc);name='forge-english-cap15-'+now.strftime('%m%d-%H%M%S')
stop=(now+dt.timedelta(minutes=60)).strftime('%Y-%m-%dT%H:%M:%SZ')
remote='gs://forge-ownbase-a100-20261110/english-cap15-v2/'+name
config=json.loads((ROOT/'reports/english-a100-v1/repair/config.json').read_text())
config.update(run_id=name,deadline_utc=stop,worker_deadline_utc=(now+dt.timedelta(minutes=45)).strftime('%Y-%m-%dT%H:%M:%SZ'),backup_prefix=remote,qualification_only=True,pilot_authorized_by_worker=False)
(P/'config.json').write_text(json.dumps(config,indent=2)+'\n')
packet=R/'packet.tar.gz'
with tarfile.open(packet,'w:gz') as tar:
 for f in ['fit-train.jsonl','development-reference.jsonl','development-suite.json','data-review.json','diagnostic-admission.json','diagnostic-manifest.json','diagnostic-contract.json']:tar.add(ROOT/'reports/english-first-v1'/f,arcname='packet/'+f)
 for f in ['config.json','gpu_qualify.py','signal_inject.py']:tar.add(P/f,arcname=f)
packet_uri=remote+'/inputs/packet.tar.gz';cp(packet,packet_uri,True);rb=R/'packet-readback.tar.gz';cp(packet_uri,rb);assert sha(rb)==sha(packet);rb.unlink()
inputs=[{'path':str(archive),'uri':uri,'sha256':sha(archive),'independent_readback':True},{'path':str(packet),'uri':packet_uri,'sha256':sha(packet),'independent_readback':True}]
(P/'input-backup-receipt.json').write_text(json.dumps({'all_verified':True,'files':inputs},indent=2)+'\n')
metadata='own-deadline-utc='+stop+',bundle-uri='+uri+',bundle-sha256='+sha(archive)+',packet-uri='+packet_uri+',packet-sha256='+sha(packet)+',enable-oslogin=TRUE,block-project-ssh-keys=TRUE'
argv=['gcloud','compute','instances','create',name,'--project=executespecv1','--zone=us-central1-f','--machine-type=a2-highgpu-1g','--provisioning-model=STANDARD','--maintenance-policy=TERMINATE','--no-restart-on-failure','--termination-time='+stop,'--instance-termination-action=STOP','--boot-disk-size=100GB','--boot-disk-type=pd-balanced','--no-boot-disk-auto-delete','--image=projects/deeplearning-platform-release/global/images/'+json.loads((P/'image.json').read_text())['name'],'--service-account=forge-ownbase-bench@executespecv1.iam.gserviceaccount.com','--scopes=https://www.googleapis.com/auth/devstorage.read_write','--no-address','--subnet=default','--metadata='+metadata,'--metadata-from-file=startup-script='+str(P/'bootstrap.sh'),'--quiet','--format=json','--async']
request={'run_id':name,'zone':'us-central1-f','provider_stop_utc':stop,'max_runtime_seconds':3600,'list_rate_usd_per_hour':3.673385,'compute_reserved_usd':3.673385*1.25,'bootstrap_sha256':sha(P/'bootstrap.sh'),'inputs':inputs,'create_argv':argv,'qualification_only':True,'approval':'User new $15 cap; A100 permitted; plan/double-check before action'}
(P/'launch-request.json').write_text(json.dumps(request,indent=2)+'\n')
ledger={'approved_total_usd':15,'qualification_slice_usd':5,'fit_slice_usd':6,'reserve_usd':4,'rate_margin':1.25,'allocations':[{'run_id':name,'state':'reserved_before_provisioning','compute_reserved_usd':request['compute_reserved_usd'],'request_sha256':sha(P/'launch-request.json')}],'fit_started':False,'new_storage_transfer_estimate_ceiling_usd':4}
assert ledger['allocations'][0]['compute_reserved_usd']<=5
(P/'spend-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(name,stop,'reserved',request['compute_reserved_usd'])
