"""One bounded A100 allocation, authorized by user13November; never starts old VM."""
raise SystemExit('Closed campaign: this allocator is retired. Define a new quality-gated, budget-bound run; do not reuse this lease.')
import datetime,hashlib,json,os,subprocess,time
from pathlib import Path
from gcp_api import request
P=Path('reports/ownbase-budget50-v1');R=Path('runs/ownbase-budget50-v1');c=json.loads((P/'launch-config.json').read_text())
vm='forge-ownbase-budget50-v1';zone=c['zone'];project='executespecv1'
listing=request(f'https://compute.googleapis.com/compute/v1/projects/{project}/aggregated/instances')
for group in listing.get('items',{}).values():
 for instance in group.get('instances',[]):
  assert instance['name']!=vm, 'Named VM already exists; inspect rather than create again'
  assert not instance.get('guestAccelerators') or instance['status']=='TERMINATED','Existing GPU allocation active'
assert c['budget']['compute_reservation_usd']+c['budget']['storage_transfer_and_uncertainty_reserve_usd']==50
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
receipt={'run_id':vm,'vm_name':vm,'zone':zone,'project':project,'created_request_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'external_stop_epoch':time.time()+51900,'incremental_cap_usd':50,'compute_upper_usd_per_hour':2.5,'compute_hours_max':14,'reserves_usd':15,'provider_termination':'STOP','guard_pid':None,'original_vm':'retained stopped; not modified','source_sha256':{str(p):sha(p) for p in P.glob('*.py')},'billing':'enabled; no billing export tables, not invoice verified','storage_reserve_horizon_days':7}
(R/'launch-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
log=(R/'guard.log').open('a');guard=subprocess.Popen(['python',str(P/'guard.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True);receipt['guard_pid']=guard.pid;(R/'launch-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
metadata={'bundle-uri':c['bundle_uri'],'code-sha256':c['bundle_sha256'],'config-uri':c.get('config_uri',c['run_prefix']+'/launch/launch-config.json'),'config-sha256':sha(P/'launch-config.json'),'runner-uri':c['run_prefix']+'/launch/run_base.py','runner-sha256':sha(P/'run_base.py'),'seed-journal-uri':c['backup_prefix']+'/retention-journal.json','seed-journal-sha256':sha(R/'new-base-journal.json')}
args=['gcloud','compute','instances','create',vm,'--project='+project,'--zone='+zone,'--machine-type=a2-highgpu-1g','--provisioning-model=FLEX_START','--image=pytorch-2-9-cu129-ubuntu-2404-nvidia-580-v20261029','--image-project=deeplearning-platform-release','--boot-disk-size=200GB','--boot-disk-type=pd-balanced','--no-boot-disk-auto-delete','--maintenance-policy=TERMINATE','--no-restart-on-failure','--max-run-duration=14h','--instance-termination-action=STOP','--no-address','--subnet=default','--service-account=forge-ownbase-bench@executespecv1.iam.gserviceaccount.com','--scopes=https://www.googleapis.com/auth/devstorage.read_write','--labels=purpose=ownbase-training,budget=usd50','--request-valid-for-duration=30m','--metadata='+','.join(k+'='+v for k,v in metadata.items()),'--metadata-from-file=startup-script='+str(P/'startup.sh'),'--quiet','--format=json','--async']
(R/'create-argv.json').write_text(json.dumps(args,indent=2)+'\n');env=dict(os.environ,CLOUDSDK_PYTHON_SITEPACKAGES='1',PYTHONPATH=str((R/'ipv4').resolve()))
result=subprocess.run(args,capture_output=True,text=True,env=env,timeout=120);(R/'create-result.json').write_text(result.stdout);(R/'create-stderr.txt').write_text(result.stderr);print('Create request returncode',result.returncode);print(result.stdout[:3000] or result.stderr[:1500])
