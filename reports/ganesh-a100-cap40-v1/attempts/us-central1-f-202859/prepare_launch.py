"""Prepare verified inputs and one approval-bound qualification request; no VM allocation."""
import json,subprocess,hashlib,datetime as dt,tarfile,base64
from pathlib import Path
from cloud_training.nano_recovery_gate import inspect
P=Path('reports/ganesh-a100-cap40-v1/attempts/us-central1-f-202859');R=Path('runs/ganesh-a100-cap40-v1/us-central1-f-202859');R.mkdir(parents=True);ROOT=Path.cwd()
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n')
def command(a,timeout=180):return subprocess.run(a,check=True,capture_output=True,text=True,timeout=timeout)
def cloud(a):return json.loads(command(['gcloud',*a,'--project=executespecv1','--format=json']).stdout)
def upload(p,uri):
 command(['gcloud','storage','cp',str(p),uri,'--if-generation-match=0','--quiet'],600)
 dest=R/(Path(p).name+'.readback');command(['gcloud','storage','cp',uri,str(dest),'--quiet'],600)
 assert sha(dest)==sha(p);dest.unlink()
 return {'path':str(p),'uri':uri,'sha256':sha(p),'bytes':Path(p).stat().st_size,'independent_readback':True}
assert not (P/'launch-request.json').exists(),'Do not regenerate or extend a prepared lease'
assert not cloud(['compute','instances','list']) and not cloud(['compute','disks','list'])
now=dt.datetime.now(dt.timezone.utc);stamp=lambda d:d.strftime('%Y-%m-%dT%H:%M:%SZ')
name='ganesh-a100-'+now.strftime('%m%d-%H%M%S');prefix='gs://forge-ownbase-a100-20261110/ganesh-a100-cap40-v1/'+name
# Two-hour first allocation; never extend past the separately recorded 12-hour campaign deadline.
stop=dt.datetime.fromisoformat('2026-11-18T03:05:59Z'.replace('Z','+00:00'));qualification_stop=now+dt.timedelta(hours=2);worker=qualification_stop-dt.timedelta(minutes=30)
old=json.loads(Path('reports/english-cap15-v2/config.json').read_text())
config={k:old[k] for k in ('base_uri','base_manifest_sha256','tokenizer_sha256')}
config.update(schema=1,run_id=name,deadline_utc=stamp(stop),qualification_deadline_utc=stamp(qualification_stop),worker_deadline_utc=stamp(worker),backup_prefix=prefix,qualification_only=True,pilot_authorized_by_worker=False)
write(P/'config.json',config)
# Check retained base manifest and remote payload against local known-good bytes.
base=Path('runs/local-readiness-v1/base10b');remote=config['base_uri'];remote_meta=[]
for n in ('manifest.json','metadata.json','COMMITTED'):
 dst=R/('base-'+n);command(['gcloud','storage','cp',remote+'/'+n,str(dst),'--quiet']);assert dst.read_bytes()==(base/n).read_bytes()
obj=json.loads(command(['gcloud','storage','objects','describe',remote+'/payload.pt','--format=json']).stdout)
with (base/'payload.pt').open('rb') as f:md5=base64.b64encode(hashlib.file_digest(f,'md5').digest()).decode()
assert obj['md5_hash']==md5 and int(obj['size'])==(base/'payload.pt').stat().st_size
write(P/'base-backup-check.json',{'remote':remote,'remote_object':obj,'metadata_readback':True,'local_payload_md5_matches_remote':True,'prior_full_verification':'reports/gcp-cleanup-20261117/own-plan.json','worker_full_payload_readback_required':True})
# Immutable packet contains data, current worker and signal helper. No sealed release.
packet=R/'qualification-packet.tar.gz'
with tarfile.open(packet,'w:gz',compresslevel=1) as t:
 with tarfile.open('runs/ganesh-controller-v1/data-packet.tar.gz') as source:
  for member in source.getmembers():
   assert member.isfile() and not member.name.startswith('/') and '..' not in Path(member.name).parts
   t.addfile(member,source.extractfile(member))
 for n in ('config.json','gpu_qualify.py','signal_inject.py','capture_compare.py','upload_fault_shim.py','decode_benchmark.py'):t.add(P/n,arcname=n)
runtime=Path('runs/ganesh-a100-cap40-v1/runtime.tar.gz')
assert sha(runtime)=='23645f6fbd5706a0a99c73b6f06e0764551b04cdfa4951815aea81f7239e1b86'
prior=json.loads(Path('reports/ganesh-a100-cap40-v1/input-backups.json').read_text())['inputs'][0]
assert prior['independent_readback'] and prior['sha256']==sha(runtime)
remote_runtime=json.loads(command(['gcloud','storage','objects','describe',prior['uri'],'--format=json']).stdout)
runtime_hashes=json.loads(command(['gcloud','storage','hash',str(runtime),'--format=json']).stdout)[0]
assert remote_runtime['crc32c_hash']==runtime_hashes['crc32c_hash'] and int(remote_runtime['size'])==runtime.stat().st_size
write(P/'runtime-reuse-check.json',{'prior_independent_readback':prior,'current_remote_metadata':remote_runtime,'crc32c_match':True,'sha256_matches_prior_readback':True})
inputs=[prior,upload(packet,prefix+'/inputs/qualification-packet.tar.gz')]
write(P/'input-backups.json',{'inputs':inputs,'base_check':sha(P/'base-backup-check.json'),'checked_utc':stamp(dt.datetime.now(dt.timezone.utc))})
cat=json.loads((P/'price-catalog.json').read_text())
def rate(code):
 s=next(s for s in cat['skus'] if s['skuId']==code);v=s['pricingInfo'][-1]['pricingExpression']['tieredRates'][0]['unitPrice'];return int(v['units'])+v['nanos']/1e9
vm=12*rate('2922-40C5-B19F')+85*rate('2390-DCAF-DA38')+rate('039F-D0DA-4055');disk=200*rate('6AE1-525F-8B80')/730
assert abs(vm-3.673385)<.000001
hours=(stop-now).total_seconds()/3600
assert 2<hours<12
assert all('us-central1' in x['serviceRegions'] for x in cat['skus'] if x['skuId'] in ('2922-40C5-B19F','2390-DCAF-DA38','039F-D0DA-4055','6AE1-525F-8B80'))
full=hours*(vm+disk)*1.25+8;assert full<=40
image=json.loads((P/'image.json').read_text())['selfLink'].split('/projects/',1)[1];image='projects/'+image
metadata='own-deadline-utc='+stamp(stop)+',bundle-uri='+inputs[0]['uri']+',bundle-sha256='+inputs[0]['sha256']+',packet-uri='+inputs[1]['uri']+',packet-sha256='+inputs[1]['sha256']+',enable-oslogin=TRUE,block-project-ssh-keys=TRUE'
argv=['gcloud','compute','instances','create',name,'--project=executespecv1','--zone=us-central1-f','--machine-type=a2-highgpu-1g','--provisioning-model=STANDARD','--maintenance-policy=TERMINATE','--no-restart-on-failure','--termination-time='+stamp(stop),'--instance-termination-action=STOP','--boot-disk-size=200GB','--boot-disk-type=pd-balanced','--no-boot-disk-auto-delete','--image='+image,'--service-account=forge-ownbase-bench@executespecv1.iam.gserviceaccount.com','--scopes=https://www.googleapis.com/auth/devstorage.read_write','--no-address','--tags=ganesh-a100-cap40-iap','--subnet=default','--metadata='+metadata,'--metadata-from-file=startup-script='+str((P/'bootstrap.sh').resolve()),'--quiet','--format=json','--async']
request=json.loads(Path('reports/ganesh-controller-v1/request-template.json').read_text())
request['files'].pop('runs/ganesh-controller-v1/runtime-qualified-local.tar.gz',None)
request['files'][str(runtime)]=sha(runtime)
request['files']['cloud_training/nano_recovery_gate.py']=sha('cloud_training/nano_recovery_gate.py')
request['machine']='a2-highgpu-1g'
request.update(lease_start_utc=stamp(now),provider_stop_utc=stamp(stop),worker_stop_utc=stamp(worker),backup_reserve_seconds=1800,maximum_incremental_cost_usd=full,reserve_usd=6,backup_prefix=prefix,launch_argv=argv,campaign_deadline_utc=stamp(stop),qualification_only=True,approval_scope='User approved $40 cumulative cap and A100; retain same VM through useful work; bounded qualification and conditional English pilots')
for f in ('bootstrap.sh','gpu_qualify.py','signal_inject.py','capture_compare.py','upload_fault_shim.py','decode_benchmark.py','config.json','input-backups.json','base-backup-check.json'):
 request['files'][str(P/f)]=sha(P/f)
request['evidence']={}
spec=hashlib.sha256(json.dumps({k:v for k,v in request.items() if k not in ('authorization','evidence')},sort_keys=True,separators=(',',':')).encode()).hexdigest()
request['authorization']={'spec_sha256':spec,'explicit_user_approval':True,'approval_reference':'User explicitly selected $40 total cap and use A100; same VM retained through approved stages','cap_usd':40,'expires_utc':stamp(stop)}
for check,extra in [('fresh_inventory',{'instances':cloud(['compute','instances','list']),'disks':cloud(['compute','disks','list'])}),('input_backups',{'raw_receipt':str(P/'input-backups.json'),'raw_sha256':sha(P/'input-backups.json')}),('price_quote',{'hourly_rate_usd':vm+disk,'margin_multiplier':1.25,'raw_receipt':str(P/'price-catalog.json'),'raw_sha256':sha(P/'price-catalog.json')})]:
 if check=='fresh_inventory':assert not extra['instances'] and not extra['disks']
 receipt=P/(check+'-receipt.json');write(receipt,{'status':'pass','check':check,'spec_sha256':spec,'checked_utc':stamp(dt.datetime.now(dt.timezone.utc)),**extra});request['evidence'][check]={'path':str(receipt),'sha256':sha(receipt)}
write(P/'launch-request.json',request)
gate=inspect(ROOT,request,'qualification');write(P/'qualification-gate.json',gate);assert gate['allowed'],gate
assert (stop-dt.datetime.now(dt.timezone.utc)).total_seconds()>6000,'Input preparation consumed qualification window; HOLD, do not extend'
write(P/'spend-ledger.json',{'approved_usd':40,'reserved_campaign_usd':full,'qualification_max_hours':2,'qualification_compute_disk_margin_usd':2*(vm+disk)*1.25,'reserve_usd':6,'prior_cost_reserve_usd':2,'prior_compute_estimate_usd':0.5366515,'vm_rate_usd':vm,'disk_rate_usd':disk,'campaign_deadline_utc':request['campaign_deadline_utc'],'full_lease_hours':hours,'user_requested_retain_vm_between_stages':True,'status':'prepared_not_allocated','automatic_retry':False})
print(json.dumps({'status':'prepared_not_allocated','run_id':name,'provider_stop_utc':stamp(stop),'campaign_max_cost':full,'inputs_readback':True,'qualification_gate':gate['allowed']}))
