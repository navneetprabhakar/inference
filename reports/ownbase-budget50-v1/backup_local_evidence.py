"""Content-addressed local evidence archive with independent GCS SHA readback."""
import datetime,hashlib,json,subprocess,tarfile
from pathlib import Path
R=Path('runs/ownbase-budget50-v1');D=R/'evidence-backups';D.mkdir(exist_ok=True)
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');tmp=D/(stamp+'.tar.gz');files=[]
for root in [Path('reports/ownbase-budget50-v1'),R/'eval-candidates',R/'corpus-expansion']:
 files.extend(p for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for name in ['OWN_BASE_HANDOFF.txt','OWN_BASE_NEXT_STEPS.txt','TRAINING_AUDIT.txt','chat-own.sh','cloud_training/nano_chat_cli.py']:files.append(Path(name))
for p in R.glob('*.json'):files.append(p)
for name in ['sft-dispatch.log','sft-dispatch-v2.log','local-cli-smoke.txt','sft-preflight.log','snapshots.jsonl','local-baseline-assessment.log']:
 p=R/name
 if p.exists():files.append(p)
with tarfile.open(tmp,'w:gz') as tar:
 for p in sorted(set(files)):tar.add(p,arcname=str(p),recursive=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();digest=sha(tmp);uri='gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1/local-evidence/'+stamp+'-'+digest+'.tar.gz'
subprocess.run(['gcloud','storage','cp',str(tmp),uri,'--quiet'],check=True,timeout=300)
back=D/(stamp+'.readback.tar.gz');subprocess.run(['gcloud','storage','cp',uri,str(back),'--quiet'],check=True,timeout=300);assert sha(back)==digest;back.unlink()
receipt={'utc':stamp,'uri':uri,'sha256':digest,'bytes':tmp.stat().st_size,'files':len(set(files)),'independent_sha_readback':True,'note':'Snapshot; live generation/training files can advance afterward and require a later backup.'}
(D/(stamp+'.json')).write_text(json.dumps(receipt,indent=2)+'\n');Path('reports/ownbase-budget50-v1/latest-local-backup.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
