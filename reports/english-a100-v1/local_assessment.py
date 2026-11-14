"""Preserve and assess the preselected diagnostic step2; never change serving default."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from cloud_training.nano_checkpoint import validate_bundle
P=Path(__file__).parent;selection=json.loads((P/'selected-diagnostic.json').read_text());dst=ROOT/'runs/english-a100-v1/local-diagnostic-step2'
dst.mkdir(exist_ok=True)
for name in ('payload.pt','metadata.json','manifest.json','COMMITTED'):
 subprocess.run(['gcloud','storage','cp',selection['uri']+'/'+name,str(dst/name),'--quiet'],check=True,timeout=900)
if validate_bundle(dst)!=selection['manifest']:raise ValueError('Selected diagnostic bundle readback differs')
sha=hashlib.sha256((dst/'manifest.json').read_bytes()).hexdigest();selection.update(local_path=str(dst),manifest_sha256=sha,local_independent_readback=True);(P/'selected-diagnostic.json').write_text(json.dumps(selection,indent=2)+'\n')
a=[sys.executable,'-m','cloud_training.nano_quality','--repo',str(ROOT/'runs/nanochat-source'),'--checkpoint',str(dst),'--checkpoint-manifest-sha256',sha,'--tokenizer',str(ROOT/'runs/ownbase-v2-data/tokenizer'),'--tokenizer-sha256',json.loads((ROOT/'reports/english-first-v1/diagnostic-manifest.json').read_text())['tokenizer_sha256'],'--suite',str(ROOT/'reports/english-first-v1/development-suite.json'),'--output',str(P/'diagnostic2-conversation.json'),'--device','mps','--seconds','600','--reply-budget','192']
r=subprocess.run(a,cwd=ROOT);raise SystemExit(r.returncode)
