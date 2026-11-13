"""Read-only original lineage restore; CPU validation, no active base mutation."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path('/opt/ownbase-nano');OUT=ROOT/'results/budget50-v1';dest=ROOT/'retained-lineage';dest.mkdir(exist_ok=True);prefix='gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1/sft-packet-v2'
CONFIG_SHA256 = None  # Bound into the uploaded copy.
def cp(src,dst):subprocess.run(['gcloud','storage','cp',str(src),str(dst),'--quiet'],check=True,timeout=600)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
cp(prefix+'/config.json',dest/'config.json');assert CONFIG_SHA256 and sha(dest/'config.json')==CONFIG_SHA256
cfg=json.loads((dest/'config.json').read_text());sys.path[:0]=[str(OUT/'sft-preflight/code'),str(ROOT/'vendor'),str(ROOT/'nanochat-source')]
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_sft import validate_parent_chain
paths=[];entries=[]
for item in cfg['retained_lineage']['items']:
 path=ROOT/'resume' if item['name']=='base6b' else dest/item['name'];path.mkdir(exist_ok=True)
 if item['name']!='base6b':
  for name in ['payload.pt','metadata.json','manifest.json','COMMITTED']:
   # Existing verified files may be reused on a failed-transfer retry.
   expected=item['manifest']['files'].get(name,{}).get('sha256',item['manifest_sha256'] if name=='manifest.json' else None)
   if not (expected and (path/name).is_file() and sha(path/name)==expected):cp(item['uri']+'/'+name,path/name)
 assert sha(path/'manifest.json')==item['manifest_sha256'];assert validate_bundle(path)==item['manifest'];paths.append(path);entries.append({'name':item['name'],'manifest_sha256':item['manifest_sha256'],'payload_sha256_verified':True})
validate_parent_chain(paths[0],cfg['retained_lineage']['items'][0]['manifest_sha256'],'ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5',stage='targeted',ancestors=paths[1:])
env=os.environ.copy();env.update(PYTHONPATH=str(OUT/'sft-preflight/code')+':'+str(ROOT/'vendor')+':'+str(ROOT/'nanochat-source'),NANOCHAT_DTYPE='bfloat16',HF_HUB_OFFLINE='1')
args=[sys.executable,'-m','cloud_training.nano_sft','--validate-only','--manifest',str(OUT/'sft-preflight/data/manifest.json'),'--base',str(paths[0]),'--base-manifest-sha',cfg['retained_lineage']['items'][0]['manifest_sha256'],'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha','ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5','--repo',str(ROOT/'nanochat-source'),'--output',str(OUT/'retained605-preflight'),'--stage','targeted','--epochs','4','--batch-tokens','8192','--microbatch','4','--lr-multiplier','0.125']
for path in paths[1:]:args+=['--ancestor',str(path)]
r=subprocess.run(args,env=env,cwd=OUT/'sft-preflight/code',capture_output=True,text=True,timeout=300)
receipt={'scope':'All7originalpayloads independently SHAverified; original6Bseed reused, sixSFTparents copied read-only. No model/GPU allocation or optimizer writes.','entries':entries,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr};(OUT/'retained-preflight.json').write_text(json.dumps(receipt,indent=2)+'\n');cp(OUT/'retained-preflight.json',prefix+'/retained-preflight.json');assert r.returncode==0,r.stderr;print('Retained605 CPU preflight and all7payloads verified.',flush=True)
