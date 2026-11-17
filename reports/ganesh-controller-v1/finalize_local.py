"""Bind actual local readiness and packet; no cloud writes or training."""
import datetime as dt,hashlib,json,sys,tarfile,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from cloud_training.nano_package import extract_verified,verify_module_closure
from cloud_training.nano_recovery_controller import validate_graph,canonical
from cloud_training.nano_checkpoint import validate_bundle
P=Path(__file__).parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
archive=ROOT/'runs/ganesh-controller-v1/runtime-qualified-local.tar.gz'
with tempfile.TemporaryDirectory() as tmp:
 manifest=extract_verified(archive,Path(tmp).resolve()/'runtime')
 for name,entry in manifest['files'].items():
  if name.startswith('cloud_training/') or name=='ganesh_recovery_task.py':
   assert sha(ROOT/name)==entry['sha256'],name
frozen={}
for folder,filename in [('reports/corrective-corpus-v1','freeze.json'),('reports/english-first-v1','packet-freeze.json'),('reports/ganesh-english-curriculum-v2','freeze.json')]:
 files=json.loads((ROOT/folder/filename).read_text())['files']
 assert all(sha(ROOT/folder/n)==h for n,h in files.items())
 frozen[folder]={'count':len(files),'unchanged':True}
models={}
for name,folder in [('base','runs/local-readiness-v1/base10b'),('local_default','runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs')]:
 m=validate_bundle(ROOT/folder);models[name]={'step':m['step'],'manifest_sha256':sha(ROOT/folder/'manifest.json'),'payload_verified':True}
request=json.loads((P/'request-template.json').read_text())
request['files'][str(archive.relative_to(ROOT))]=sha(archive)
# A real controller request is finalized only after the user cap and cloud facts exist.
request['authorization']=None;validate_graph(request,ROOT)
requestsha=canonical({k:v for k,v in request.items() if k not in ('authorization','evidence')})
(P/'request-template.json').write_text(json.dumps(request,indent=2)+'\n')
proofs={}
for name,source in [('production_admission','reports/ganesh-english-curriculum-v2/admission.json'),('production_preflight','reports/ganesh-controller-v1/integrated-curriculum-preflight.log')]:
 path=P/(name+'-receipt.json')
 body={'status':'pass','check':name,'spec_sha256':requestsha,'checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'LOCAL pilot admission/preflight only; not GPU or release proof','source':source,'source_sha256':sha(ROOT/source)}
 path.write_text(json.dumps(body,indent=2)+'\n');proofs[name]={'path':str(path.relative_to(ROOT)),'sha256':sha(path)}
request['evidence']=proofs;(P/'request-template.json').write_text(json.dumps(request,indent=2)+'\n')
packet=ROOT/'runs/ganesh-controller-v1/data-packet.tar.gz'
if not packet.exists():
 with tarfile.open(packet,'w:gz') as t:
  for name in request['files']:
   if name.startswith('reports/english-first-v1/') or name.startswith('reports/ganesh-english-curriculum-v2/') or name=='reports/english-local-readiness-v1/fit-suite.json':t.add(ROOT/name,arcname=name)
with tarfile.open(packet,'r:gz') as t:
 for m in t.getmembers():
  assert m.isfile() and m.name in request['files'] and hashlib.sha256(t.extractfile(m).read()).hexdigest()==request['files'][m.name]
fit=json.loads((ROOT/request['fit_inputs']['suite']).read_text());dev=json.loads((ROOT/request['fit_inputs']['development_suite']).read_text());curr=json.loads((ROOT/request['curriculum_inputs']['suite']).read_text());protected=json.loads((ROOT/request['curriculum_inputs']['protected_suite']).read_text())
budget=lambda s:sum(t.get('reply_budget',128)*3 for row in s['sessions'] for t in row['turns'])
result={'status':'local_pilot_readiness_checked_not_cloud_authorization','runtime_sha256':sha(archive),'runtime_bytes':archive.stat().st_size,'runtime_members':len(manifest['files'])+1,'module_closure':verify_module_closure(ROOT),'data_packet_sha256':sha(packet),'data_packet_bytes':packet.stat().st_size,'packet_contains_sealed_release':False,'models':models,'frozen':frozen,'controller_tasks':len(request['tasks']),'spec_sha256':requestsha,'generation_bound':{'fit_and_frozen_dev_tokens':budget(fit)*6+budget(dev)*3,'curriculum_baseline_best_last_tokens':budget(curr)*3,'protected_baseline_best_last_tokens':budget(protected)*3,'total_max_generated_tokens':budget(fit)*6+budget(dev)*3+budget(curr)*3+budget(protected)*3},'training':False,'cloud_writes':False,'launch_authorized':False,'release_eligible':False}
(P/'local-readiness.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
