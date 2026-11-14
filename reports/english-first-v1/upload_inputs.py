"""Upload and independently read back immutable qualification inputs; no VM action."""
import json,hashlib,subprocess,tempfile
from pathlib import Path
P=Path(__file__).parent;request=json.loads((P/'launch-request.json').read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(P/'bootstrap.sh')==request['bootstrap_sha256']
proofs=[]
for item in request['inputs']:
 assert sha(item['path'])==item['sha256']
 subprocess.run(['gcloud','storage','cp',item['path'],item['uri'],'--quiet','--if-generation-match=0'],check=True,timeout=600)
 with tempfile.TemporaryDirectory() as d:
  target=Path(d)/'readback'
  subprocess.run(['gcloud','storage','cp',item['uri'],str(target),'--quiet'],check=True,timeout=600)
  assert sha(target)==item['sha256']
 proofs.append({**item,'independent_readback':True})
(P/'input-backup-receipt.json').write_text(json.dumps({'files':proofs,'all_verified':True},indent=2)+'\n')
