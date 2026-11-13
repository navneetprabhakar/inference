"""Download one completed run candidate, verify immutable bundle; never promote."""
import argparse,datetime,hashlib,json,re,subprocess,sys
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path('.').resolve()))
from cloud_training.nano_checkpoint import validate_bundle
from gcp_api import request
p=argparse.ArgumentParser(description=__doc__);p.add_argument('name',choices=['new-base-2k-8epochs','retained605-2k-4epochs']);a=p.parse_args()
bucket='forge-ownbase-a100-20261110';prefix='ownbase-v2/budget50-v1';uri='gs://'+bucket+'/'+prefix
registry=request('https://storage.googleapis.com/storage/v1/b/'+bucket+'/o/'+quote(prefix+'/sft-stage/candidates.json',safe='')+'?alt=media')
assert isinstance(registry,list)
row=next(r for r in registry if r['name']==a.name);assert row['independent_readback'] and re.fullmatch('[0-9a-f]{64}',row['manifest_sha256'])
assert re.fullmatch(re.escape(uri+'/sft/'+a.name+'/checkpoints/checkpoint-')+'[0-9a-f]+',row['remote_prefix'])
root=Path('runs/ownbase-budget50-v1/local-candidates');root.mkdir(exist_ok=True);dest=root/a.name;dest.mkdir(exist_ok=True)
sha=lambda path:hashlib.file_digest(path.open('rb'),'sha256').hexdigest()
for name in ['metadata.json','manifest.json','COMMITTED','payload.pt']:
 subprocess.run(['gcloud','storage','cp',row['remote_prefix']+'/'+name,str(dest/name),'--quiet'],check=True,timeout=900)
assert sha(dest/'manifest.json')==row['manifest_sha256'];manifest=validate_bundle(dest)
meta=json.loads((dest/'metadata.json').read_text());assert meta['identity']['phase']=='sft' and meta['step']>0
receipt={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'name':a.name,'checkpoint':str(dest),'remote_prefix':row['remote_prefix'],'manifest_sha256':row['manifest_sha256'],'payload_sha256':sha(dest/'payload.pt'),'payload_bytes':(dest/'payload.pt').stat().st_size,'step':meta['step'],'training_status':row['training_status'],'trained_assistant_targets':row['trained_assistant_targets'],'local_bundle_verified':True,'local_inference_verified':False,'promoted':False}
(root/(a.name+'-download.json')).write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
