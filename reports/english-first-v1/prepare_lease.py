"""Prepare a single two-hour L4 qualification request; does not provision."""
import datetime as dt,json,hashlib,tarfile,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from cloud_training.nano_l4_lease import plan
P=Path(__file__).parent;R=ROOT/'runs/english-first-v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
if (P/'launch-request.json').exists():raise FileExistsError('Do not replace lease/reservation evidence')
now=dt.datetime.now(dt.timezone.utc);name='forge-english-q-'+now.strftime('%m%d-%H%M%S')
image=json.loads((P/'image-status.json').read_text());assert image['status']=='READY' and not image.get('deprecated')
instances=json.loads((P/'cloud-status.json').read_text());assert all(i['status']=='TERMINATED' for i in instances)
request=plan(project='executespecv1',zone='us-central1-a',name=name,image='projects/deeplearning-platform-release/global/images/'+image['name'],service_account='forge-ownbase-bench@executespecv1.iam.gserviceaccount.com',bootstrap=str(P.resolve()/'bootstrap.sh'),now=now,hours=2)
remote='gs://forge-ownbase-a100-20261110/english-first-v1/'+name
config={'schema':1,'run_id':name,'deadline_utc':request['latest_local_stop_utc'],'worker_deadline_utc':(now+dt.timedelta(hours=2,minutes=-15)).strftime('%Y-%m-%dT%H:%M:%SZ'),'backup_prefix':remote,'base_uri':'gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1/base/checkpoints/checkpoint-bcfb32abdbba44eaa3c7107af1adb7b2','base_manifest_sha256':'7d803e32928ca9ecc1fe38bf7d47c54bca80c0996d6bb006b718cfd851975e53','tokenizer_sha256':'ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5','qualification_only':True,'pilot_authorized_by_worker':False}
(P/'config.json').write_text(json.dumps(config,indent=2)+'\n')
files=['fit-train.jsonl','development-reference.jsonl','development-suite.json','data-review.json','diagnostic-admission.json','diagnostic-manifest.json','diagnostic-contract.json']
packet=R/'packet.tar.gz'
with tarfile.open(packet,'w:gz') as tar:
 for f in files:tar.add(P/f,arcname='packet/'+f)
 tar.add(P/'config.json',arcname='config.json');tar.add(P/'gpu_qualify.py',arcname='gpu_qualify.py')
runtime=R/'runtime.tar.gz'
receipt=json.loads((R/'runtime.tar.gz.receipt.json').read_text())
assert receipt['bundle_sha256']==sha(runtime)
for n,item in receipt['files'].items():
 if n.startswith('cloud_training/') and n.endswith('.py'):assert sha(ROOT/n)==item['sha256'],n
runtime_uri='gs://forge-ownbase-a100-20261110/english-first-v1/runtime/'+sha(runtime)+'.tar.gz';packet_uri=remote+'/inputs/packet.tar.gz'
metadata='--metadata=own-deadline-utc='+config['deadline_utc']+',bundle-uri='+runtime_uri+',bundle-sha256='+sha(runtime)+',packet-uri='+packet_uri+',packet-sha256='+sha(packet)+',enable-oslogin=TRUE,block-project-ssh-keys=TRUE'
request['create_argv']=[metadata if x.startswith('--metadata=') else x for x in request['create_argv']]+['--quiet','--format=json','--async']
request.update(bootstrap_sha256=sha(P/'bootstrap.sh'),run_id=name,backup_prefix=remote,inputs=[{'path':str(runtime),'uri':runtime_uri,'sha256':sha(runtime)},{'path':str(packet),'uri':packet_uri,'sha256':sha(packet)}],status='prepared_qualification_only',price_source='https://cloud.google.com/products/compute/pricing/accelerator-optimized',price_checked_utc=now.isoformat(),limits='No pilot until exact recovery and fault drills pass. No A100 upgrade.')
(P/'launch-request.json').write_text(json.dumps(request,indent=2)+'\n')
ledger={'schema':1,'operational_cap_usd':10,'previous_discussed_ceiling_usd':15,'reserve_usd':3.5,'authorization_context':'User: ok lets start; use cheaper GPU please; go handsoff, following changed assessment. L4 only, below prior15USDceiling.','allocations':[{'name':name,'reserved_compute_usd':request['compute_envelope_usd'],'hours':2,'state':'reserved_before_provisioning','request_sha256':sha(P/'launch-request.json')}],'no_automatic_extension':True}
(P/'spend-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
print(name,request['compute_envelope_usd']+3.5)
