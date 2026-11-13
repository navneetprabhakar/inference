"""After verified10B backup and oldVMstop, transfer the persistent disk to a bounded lease."""
import sys,json,time,datetime,hashlib,fcntl,os,subprocess
from pathlib import Path
from urllib.parse import quote
P=Path('reports/ownbase-budget50-v1/extension-v5');R=Path('runs/ownbase-budget50-v1/extension-v5');R.mkdir(exist_ok=True)
sys.path.insert(0,str(P.parent.resolve()));from gcp_api import request
lock=(R/'launch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
api='https://compute.googleapis.com/compute/v1/projects/executespecv1';zone='us-central1-b';old='forge-ownbase-budget50-v1';new='forge-ownbase-extension-v5';prefix='gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1'
env=dict(os.environ,CLOUDSDK_PYTHON_SITEPACKAGES='1',PYTHONPATH=str(Path('runs/ownbase-budget50-v1/ipv4').resolve()))
def call(args,timeout=300):return subprocess.run(args,env=env,check=True,timeout=timeout)
def record(name,data): (R/name).write_text(json.dumps(data,indent=2)+'\n')
def read_obj(name):return request('https://storage.googleapis.com/storage/v1/b/forge-ownbase-a100-20261110/o/'+quote('ownbase-v2/budget50-v1/'+name,safe='')+'?alt=media')
def waitop(op):
 end=time.time()+300
 while time.time()<end:
  x=request(api+'/zones/'+zone+'/operations/'+op['name'])
  if x['status']=='DONE':assert 'error' not in x,x.get('error');return
  time.sleep(5)
 raise TimeoutError('Provider operation did not complete')
try:
 deadline=time.time()+5*3600
 while time.time()<deadline:
  vm=request(api+'/zones/'+zone+'/instances/'+old)
  if vm['status']=='TERMINATED':break
  time.sleep(30)
 else:raise TimeoutError('OldVMdidnotstop; do not create overlappingGPU')
 backup=read_obj('backup-complete.json')
 assert backup['status']=='backup_verified' and backup['base_readback_verified'] and 18834*524288<=backup['base_tokens']<=19074*524288
 start=datetime.datetime.fromisoformat(vm['lastStartTimestamp']);stop=datetime.datetime.fromisoformat(vm['lastStopTimestamp']);prior=(stop-start).total_seconds()/3600
 duration=min(7200,int((16-prior)*3600)-10);assert 6900<=duration<=7200,'Insufficient remaining55USDbudget for plannedlease'
 assert prior*2.5+duration/3600*2.5+15<=55
 instances=request(api+'/aggregated/instances')
 for group in instances.get('items',{}).values():
  for item in group.get('instances',[]):
   assert item['name']!=new,'ExtensionVMalreadyexists; inspect manually instead ofduplicate'
   gpu=item.get('guestAccelerators') or item['machineType'].rsplit('/',1)[-1].startswith(('a2-','a3-','a4-','g2-','g4-'))
   assert not gpu or item['status']=='TERMINATED','AnotherGPUactive'
 disk=vm['disks'][0];assert len(vm['disks'])==1 and disk['boot'] and not disk['autoDelete']
 budget={'total_cap_usd':55,'prior_compute_hours':prior,'duration_seconds':duration,'compute_rate_upper':2.5,'reserve_usd':15,'base_manifest_sha256':backup['final_base_manifest_sha256'],'previous_vm':old,'current_vm':new,'previous_backup':backup}
 record('budget.json',budget)
 call(['gcloud','storage','cp',str(R/'budget.json'),prefix+'/extension-v5/budget.json','--quiet'])
 back=R/'budget-readback.json';call(['gcloud','storage','cp',prefix+'/extension-v5/budget.json',str(back),'--quiet']);assert back.read_bytes()==(R/'budget.json').read_bytes()
 record('verified-prelaunch.json',{'old_status':vm['status'],'backup':backup,'budget':budget,'disk':disk})
 # Reversible transfer; never delete the oldVM, disk, or existing retainedVM.
 waitop(request(api+'/zones/'+zone+'/instances/'+old+'/detachDisk?deviceName='+quote(disk['deviceName']),method='POST',payload={}))
 record('disk-detached.json',{'disk':disk['source'],'old_vm':old})
 digest=hashlib.sha256((R/'budget.json').read_bytes()).hexdigest()
 args=['gcloud','compute','instances','create',new,'--project=executespecv1','--zone='+zone,'--machine-type=a2-highgpu-1g','--provisioning-model=FLEX_START','--disk=name='+disk['source'].rsplit('/',1)[-1]+',boot=yes,auto-delete=no','--maintenance-policy=TERMINATE','--no-restart-on-failure','--max-run-duration='+str(duration)+'s','--instance-termination-action=STOP','--no-address','--subnet=default','--service-account=forge-ownbase-bench@executespecv1.iam.gserviceaccount.com','--scopes=https://www.googleapis.com/auth/devstorage.read_write','--tags=forge-ownbase-budget50','--labels=purpose=ownbase-training,budget=usd55','--request-valid-for-duration=30m','--metadata=extension-budget-uri='+prefix+'/extension-v5/budget.json,extension-budget-sha='+digest,'--metadata-from-file=startup-script='+str(P/'startup.sh'),'--quiet','--format=json','--async']
 record('create-argv.json',args)
 with (R/'guard.log').open('a') as log:
  guard=subprocess.Popen([sys.executable,'-u',str(P/'guard.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 record('guard-pid.json',{'pid':guard.pid})
 subprocess.Popen(['caffeinate','-i','-w',str(guard.pid)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
 result=subprocess.run(args,env=env,capture_output=True,text=True,timeout=180);(R/'create-stdout.json').write_text(result.stdout);(R/'create-stderr.txt').write_text(result.stderr);assert result.returncode==0,result.stderr[:1000]
 end=time.time()+3600
 while time.time()<end:
  current=request(api+'/zones/'+zone+'/instances/'+new)
  if current['status']=='RUNNING':
   assert int(current['scheduling']['maxRunDuration']['seconds'])==duration
   active={'vm_name':new,'zone':zone,'project':'executespecv1','prior_compute_hours':prior,'cap_usd':55,'duration_seconds':duration,'provider_status':'RUNNING','lastStartTimestamp':current['lastStartTimestamp']}
   record('launch-receipt.json',active);Path('runs/ownbase-budget50-v1/active-vm.json').write_text(json.dumps(active,indent=2)+'\n');print(json.dumps(active),flush=True);break
  if current['status']=='TERMINATED':raise RuntimeError('Extension allocation failed; disk andGCS preserved')
  time.sleep(30)
 else:raise TimeoutError('Extensionallocationnotrunningafterqueuewindow')
except BaseException as e:
 record('failure.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'type':type(e).__name__,'message':str(e)[:2000]});raise
