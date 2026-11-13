"""CPU-only verification on the active VM; no model allocation or training."""
import hashlib,json,os,subprocess,tarfile,sys
from pathlib import Path
root=Path('/opt/ownbase-nano');out=root/'results/budget50-v1/sft-preflight';out.mkdir(exist_ok=False);packet='gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1/sft-packet'
def cp(src,dst):subprocess.run(['gcloud','storage','cp',str(src),str(dst),'--quiet'],check=True,timeout=120)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
cp(packet+'/config.json',out/'config.json');assert sha(out/'config.json')=='6353cbcb47d6a3ff5aa02f9352aff4b7d4fee3eba214f398de494bba952ccfdf'
cfg=json.loads((out/'config.json').read_text());cp(cfg['code_uri'],out/'code.tar.gz');assert sha(out/'code.tar.gz')==cfg['code_sha256'];code=out/'code';code.mkdir()
with tarfile.open(out/'code.tar.gz') as t:
 for m in t.getmembers():assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
 t.extractall(code,filter='data')
for item in cfg['files']:
 dst=out/item['path'];dst.parent.mkdir(parents=True,exist_ok=True);cp(item['uri'],dst);assert sha(dst)==item['sha256']
env=os.environ.copy();env.update(PYTHONPATH=str(code)+':'+str(root/'vendor')+':'+str(root/'nanochat-source'),HF_HUB_OFFLINE='1',NANOCHAT_DTYPE='bfloat16')
reports=[]
for epochs in [4,8]:
 args=[sys.executable,'-m','cloud_training.nano_sft','--validate-only','--manifest',str(out/'data/manifest.json'),'--base',str(root/'resume'),'--base-manifest-sha',sha(root/'resume/manifest.json'),'--tokenizer',str(root/'tokenizer'),'--tokenizer-sha','ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5','--repo',str(root/'nanochat-source'),'--output',str(out/f'validate-{epochs}'),'--stage','general','--batch-tokens','8192','--microbatch','4','--epochs',str(epochs)]
 r=subprocess.run(args,env=env,cwd=code,capture_output=True,text=True,timeout=180);reports.append({'epochs':epochs,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});assert r.returncode==0,r.stderr
(out/'receipt.json').write_text(json.dumps({'scope':'CPU-only input/lineage verification; no GPU model allocation and no optimizer writes','reports':reports},indent=2)+'\n');cp(out/'receipt.json',packet+'/preflight.json');print(json.dumps(reports))
