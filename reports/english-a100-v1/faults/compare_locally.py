"""Preserve both mismatch checkpoints locally and quantify the failed exact comparison."""
import concurrent.futures,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_restart_compare import compare_bundles
P=Path(__file__).parent;parent=P.parent
ref=json.loads((parent/'repair/backup-reconciliation.json').read_text())
reference=next(x for x in ref['required_bundle_readbacks'] if '/split/checkpoints/' in x['uri'] and x['manifest']['step']==1)
fault=json.loads((P/'worker-qualification.json').read_text())
resumed=next(x for x in fault['bundle_readbacks'] if x['source'].endswith('/signal_resume/step-00000001'))['receipt']
items=[{'name':'reference-step1','uri':reference['uri'],'manifest':reference['manifest']},{'name':'signal-resumed-step1','uri':resumed['remote_prefix'],'manifest':resumed['manifest']}]
def download(item):
 dst=ROOT/'runs/english-a100-v1'/item['name'];dst.mkdir(exist_ok=True)
 for n in ('payload.pt','metadata.json','manifest.json','COMMITTED'):
  if n in item['manifest']['files'] and (dst/n).exists() and hashlib.sha256((dst/n).read_bytes()).hexdigest()==item['manifest']['files'][n]['sha256']:continue
  subprocess.run(['gcloud','storage','cp',item['uri']+'/'+n,str(dst/n),'--quiet'],check=True,timeout=3600)
 if validate_bundle(dst)!=item['manifest']:raise ValueError('Mismatch-state backup validation failed')
 return {**item,'local_path':str(dst),'manifest_sha256':hashlib.sha256((dst/'manifest.json').read_bytes()).hexdigest(),'local_readback_verified':True}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:receipts=list(pool.map(download,items))
(P/'mismatch-local-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
comparison=compare_bundles(receipts[0]['local_path'],receipts[1]['local_path'])
(P/'local-signal-resume-comparison.json').write_text(json.dumps({'comparison':comparison,'provenance':receipts,'scope':'CPU comparison of exact preserved CUDA-produced states; no training'},indent=2)+'\n')
print(json.dumps(comparison,indent=2))
