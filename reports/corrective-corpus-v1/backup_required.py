"""Future-use packet, reviews, referenced lineage and code only; no model duplication."""
import json,hashlib,tarfile,datetime,subprocess
from pathlib import Path
from cloud_training.nano_corpus_guard import verify_freeze
ROOT=Path('.').resolve();P=Path('reports/corrective-corpus-v1');D=Path('runs/corrective-corpus-v1');D.mkdir(exist_ok=True)
if (P/'backup-receipt.json').exists():raise FileExistsError('Already backed up; do not create redundant snapshots')
verify_freeze(P);files={p for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
for row in json.loads((P/'candidate-4k/assembly-audit.json').read_text())['historical_review_bindings']:
 files.update(Path(row[k]) for k in ['source_file','review_file'])
files.update(Path(p) for p in ['AGENTS.md','OWN_BASE_HANDOFF.txt','OWN_BASE_NEXT_STEPS.txt','cloud_training/nano_sft.py','cloud_training/nano_quality.py','cloud_training/nano_quality_gate.py','cloud_training/nano_corpus_guard.py','verify_nano_corrective_corpus.py','verify_nano_quality_gate.py'])
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');manifest={'utc':stamp,'files':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)]};mp=D/'snapshot-manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n');archive=D/(stamp+'.tar.gz')
with tarfile.open(archive,'w:gz') as tar:
 for p in sorted(files):tar.add(p,arcname=str(p),recursive=False)
 tar.add(mp,arcname='corrective-packet-snapshot.json',recursive=False)
digest=sha(archive);uri=f'gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1/corrective-corpus-v1/{stamp}-{digest}.tar.gz'
subprocess.run(['gcloud','storage','cp',str(archive),uri,'--quiet'],check=True,timeout=300);back=D/'readback.tar.gz';subprocess.run(['gcloud','storage','cp',uri,str(back),'--quiet'],check=True,timeout=300);assert sha(back)==digest
with tarfile.open(back,'r:gz') as tar:
 for row in manifest['files']:
  stream=tar.extractfile(row['path']);assert stream is not None and hashlib.sha256(stream.read()).hexdigest()==row['sha256']
back.unlink();report={'utc':stamp,'uri':uri,'sha256':digest,'bytes':archive.stat().st_size,'files':len(files),'independent_sha_readback':True,'all_member_hashes_verified':True,'release_model_exposures':0,'scope':'Admitted candidate,reviewed source/release,selected historical raw/review lineage,code andhandoff. No weights or obsolete experiment payloads duplicated.'};(P/'backup-receipt.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
