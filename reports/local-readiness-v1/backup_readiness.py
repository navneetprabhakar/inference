"""Back up required readiness delta only; no duplicate model/corpus/runtime payloads."""
import datetime,hashlib,json,subprocess,tarfile
from pathlib import Path
P=Path('reports/local-readiness-v1');D=Path('runs/local-readiness-v1');D.mkdir(exist_ok=True)
if (P/'backup-receipt.json').exists():raise FileExistsError('Already backed up')
validation=json.loads((P/'validation.json').read_text());assert validation['local_checks']=='pass' and not validation['gpu_authorized']
files={p for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
files.update(Path(p) for p in ['AGENTS.md','OWN_BASE_HANDOFF.txt','OWN_BASE_NEXT_STEPS.txt','cloud_training/nano_sft.py','cloud_training/nano_quality.py','cloud_training/nano_package.py','cloud_training/nano_restart_compare.py','verify_nano_sft.py','verify_nano_quality.py','verify_nano_campaign_watch.py','verify_nano_package.py','verify_nano_restart_compare.py'])
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
index={str(p):sha(p) for p in sorted(files)};mp=D/'readiness-snapshot.json';mp.write_text(json.dumps(index,indent=2)+'\n');archive=D/(stamp+'-readiness.tar.gz')
with tarfile.open(archive,'w:gz') as tar:
 for p in sorted(files):tar.add(p,arcname=str(p),recursive=False)
 tar.add(mp,arcname='readiness-snapshot.json',recursive=False)
digest=sha(archive);uri=f'gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1/local-readiness-v1/{stamp}-{digest}.tar.gz'
subprocess.run(['gcloud','storage','cp',str(archive),uri,'--quiet'],check=True,timeout=300)
back=D/'readiness-readback.tar.gz';subprocess.run(['gcloud','storage','cp',uri,str(back),'--quiet'],check=True,timeout=300);assert sha(back)==digest
with tarfile.open(back,'r:gz') as tar:
 for name,expected in index.items():assert hashlib.sha256(tar.extractfile(name).read()).hexdigest()==expected
back.unlink();receipt={'utc':stamp,'uri':uri,'sha256':digest,'files':len(files),'bytes':archive.stat().st_size,'independent_readback_and_all_member_hashes':True,'weights_or_corpus_duplicated':False}
(P/'backup-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
