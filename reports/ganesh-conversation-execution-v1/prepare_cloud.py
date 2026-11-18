"""Verify and back up launch inputs. No allocation, lease, or training dispatch."""
import base64,datetime as dt,hashlib,json,subprocess,tarfile
from pathlib import Path
ROOT=Path.cwd();P=ROOT/'reports/ganesh-conversation-execution-v1';C=ROOT/'reports/ganesh-conversation-pilot-v1';R=ROOT/'runs/ganesh-conversation-execution-v1'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,data):
 path=P/name
 if path.exists():raise FileExistsError(path)
 path.write_text(json.dumps(data,indent=2)+'\n')
def run(cmd,timeout=600):return subprocess.run(cmd,check=True,capture_output=True,text=True,timeout=timeout).stdout
def cloud(cmd):return json.loads(run(['gcloud',*cmd,'--project=executespecv1','--format=json'],120))
assert '\nOK\n' in (P/'controlled-tests.log').read_text() and 'Ran 8 tests' in (P/'controlled-tests.log').read_text()
assert '\nOK\n' in (P/'regression-tests.log').read_text() and 'Ran 209 tests' in (P/'regression-tests.log').read_text()
run([str(ROOT/'.venv/bin/python'),str(C/'validate_packet.py')],120)
instances=cloud(['compute','instances','list']);disks=cloud(['compute','disks','list'])
assert not instances and not disks
write('preallocation-inventory.json',{'instances':instances,'disks':disks,'utc':dt.datetime.now(dt.timezone.utc).isoformat()})
image=cloud(['compute','images','describe','pytorch-2-9-cu129-ubuntu-2404-nvidia-580-v20261111','--project=deeplearning-platform-release']) if False else json.loads(run(['gcloud','compute','images','describe','pytorch-2-9-cu129-ubuntu-2404-nvidia-580-v20261111','--project=deeplearning-platform-release','--format=json'],120))
assert image['status']=='READY';write('image.json',image)
weights=json.loads((ROOT/'reports/ganesh-a100-cap40-v1/local-fit-weights.json').read_text());fit=next(x for x in weights['checkpoints'] if x['step']==30)
base=json.loads((ROOT/'reports/english-cap15-v2/config.json').read_text())
config={'parent_uri':fit['remote_prefix'],'parent_manifest_sha256':fit['manifest_sha256'],'ancestor_uri':base['base_uri'],'ancestor_manifest_sha256':base['base_manifest_sha256'],'tokenizer_sha256':base['tokenizer_sha256']}
backups=[]
for name,local in [('parent',ROOT/'runs/ganesh-a100-cap40-v1/local-fit/step-00000030'),('ancestor',ROOT/'runs/local-readiness-v1/base10b')]:
 uri=config[name+'_uri']
 for file in ('manifest.json','metadata.json','COMMITTED'):
  dest=R/(name+'-'+file+'.readback');run(['gcloud','storage','cp',uri+'/'+file,str(dest),'--quiet']);assert dest.read_bytes()==(local/file).read_bytes();dest.unlink()
 obj=json.loads(run(['gcloud','storage','objects','describe',uri+'/payload.pt','--format=json']))
 with (local/'payload.pt').open('rb') as f:md5=base64.b64encode(hashlib.file_digest(f,'md5').digest()).decode()
 assert obj['md5_hash']==md5 and int(obj['size'])==(local/'payload.pt').stat().st_size
 backups.append({'bundle':name,'uri':uri,'manifest_sha256':sha(local/'manifest.json'),'metadata_readback':True,'remote_payload_md5_matches_local':True,'full_worker_readback_required':True})
write('parent-backup-checks.json',backups)
runtime=R/'runtime.tar.gz';receipt=json.loads(runtime.with_suffix('.gz.receipt.json').read_text());assert sha(runtime)==receipt['bundle_sha256']
config['runtime_sha256']=sha(runtime)
# No absolute lease yet: input upload must not consume the purchased compute window.
packet=R/'packet.tar.gz'
with tarfile.open(packet,'w:gz',compresslevel=1) as t:
 for name in [*json.loads((C/'freeze.json').read_text())['files'],'freeze.json']:
  path=C/name;t.add(path,arcname=str(path.relative_to(ROOT)),recursive=False)
 for name in ('authorization.json','broad-admission.json','control-admission.json','broad-manifest.json','control-manifest.json','broad-contract.json','control-contract.json','gpu_qualify.py','signal_inject.py','upload_fault_shim.py','decode_benchmark.py'):
  t.add(P/name,arcname=str((P/name).relative_to(ROOT)),recursive=False)
prefix='gs://forge-ownbase-a100-20261110/ganesh-conversation-execution-v1/inputs'
receipts=[]
for artifact in (runtime,packet):
 uri=prefix+'/'+sha(artifact)+'-'+artifact.name
 run(['gcloud','storage','cp',str(artifact),uri,'--if-generation-match=0','--quiet'])
 dest=R/(artifact.name+'.readback');run(['gcloud','storage','cp',uri,str(dest),'--quiet']);assert sha(dest)==sha(artifact);dest.unlink()
 receipts.append({'uri':uri,'sha256':sha(artifact),'bytes':artifact.stat().st_size,'readback_verified':True})
write('input-backups.json',receipts);write('config-template.json',config)
write('local-readiness.json',{'status':'pass','scope':'Local bounded block trainer/controller and immutable input checks; NOT CUDA qualification or model acceptance','tests':217,'runtime_sha256':sha(runtime),'frozen_packet_sha256':sha(C/'freeze.json'),'arm_preflights':['broad','control'],'evidence':{n:sha(P/n) for n in ('controlled-tests.log','regression-tests.log','broad-preflight.log','control-preflight.log','input-backups.json','parent-backup-checks.json')},'gpu_learning_requires':['Changed-path CUDA exact restart/signal/upload failure','Measured remaining stage forecast','Provider deadline and disk readback'],'release_eligible':False})
print(json.dumps({'status':'inputs_backed_up_no_VM','runtime_sha256':sha(runtime),'packet_sha256':sha(packet)}))
