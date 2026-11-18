"""Add the tested one-load evaluation adapter before allocation; verify GCS bytes."""
import hashlib,json,subprocess,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1];R=ROOT/'runs/ganesh-conversation-execution-v1'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert not (P/'allocation-intent.json').exists()
assert 'Ran 9 tests' in (P/'controlled-tests.log').read_text() and '\nOK\n' in (P/'controlled-tests.log').read_text()
old=json.loads((P/'input-backups.json').read_text());packet=R/'packet-complete.tar.gz'
assert not packet.exists()
with tarfile.open(packet,'w:gz',compresslevel=1) as dst:
 with tarfile.open(R/'packet.tar.gz') as src:
  for m in src.getmembers():dst.addfile(m,src.extractfile(m))
 for name in ('combined-development-suite.json','evaluation-composition.json','generate_snapshot.py'):
  dst.add(P/name,arcname=str((P/name).relative_to(ROOT)),recursive=False)
uri='gs://forge-ownbase-a100-20261110/ganesh-conversation-execution-v1/inputs/'+sha(packet)+'-packet-complete.tar.gz'
subprocess.run(['gcloud','storage','cp',str(packet),uri,'--if-generation-match=0','--quiet'],check=True,timeout=120)
copy=R/'packet-complete.readback';subprocess.run(['gcloud','storage','cp',uri,str(copy),'--quiet'],check=True,timeout=120);assert sha(copy)==sha(packet);copy.unlink()
(P/'superseded-input-packet.json').write_text(json.dumps(old[1],indent=2)+'\n')
new=[old[0],{'uri':uri,'sha256':sha(packet),'bytes':packet.stat().st_size,'readback_verified':True}]
(P/'input-backups.json').write_text(json.dumps(new,indent=2)+'\n')
r=json.loads((P/'local-readiness.json').read_text());r['tests']=218
for name in [*r['evidence'],'bootstrap.sh','ADVERSE_REVIEW.md','combined-development-suite.json','evaluation-composition.json','generate_snapshot.py','gpu_qualify.py','decode_benchmark.py']:
 r['evidence'][name]=sha(P/name)
(P/'local-readiness.json').write_text(json.dumps(r,indent=2)+'\n')
print('Evaluation packet readback verified;218local tests; VM still off.')
