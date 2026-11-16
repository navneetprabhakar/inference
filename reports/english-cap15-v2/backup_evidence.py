"""Back up required new review/qualification evidence and verify independent readback."""
import datetime as dt,hashlib,json,subprocess,tarfile
from pathlib import Path
ROOT=Path.cwd();P=ROOT/'reports/english-cap15-v2';R=ROOT/'runs/english-cap15-v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[]
for folder in [P,ROOT/'reports/oasst-memory-remaining-v1']:
 files.extend(p for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.lock' and p.name not in ['final-backup-receipt.json','evidence-receipt.json'])
files += [ROOT/n for n in ['OWN_BASE_HANDOFF.txt','OWN_BASE_NEXT_STEPS.txt','AGENTS.md']]
receipt={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'capacity_hold_no_worker','bound_files':{str(p.relative_to(ROOT)):sha(p) for p in sorted(files)}}
(P/'evidence-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');files.append(P/'evidence-receipt.json')
archive=R/'closeout-evidence.tar.gz'
with tarfile.open(archive,'w:gz') as tar:
 for p in files:tar.add(p,arcname=str(p.relative_to(ROOT)))
digest=sha(archive);uri='gs://forge-ownbase-a100-20261110/english-cap15-v2/closeout/'+digest+'.tar.gz'
subprocess.run(['gcloud','storage','cp',str(archive),uri,'--quiet','--if-generation-match=0'],check=True,timeout=120)
rb=R/'closeout-readback.tar.gz';subprocess.run(['gcloud','storage','cp',uri,str(rb),'--quiet'],check=True,timeout=120);assert sha(rb)==digest
with tarfile.open(rb) as tar:
 for n,h in receipt['bound_files'].items():assert hashlib.sha256(tar.extractfile(n).read()).hexdigest()==h,n
proof={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'uri':uri,'sha256':digest,'bytes':archive.stat().st_size,'independent_readback':True,'member_hashes_verified':len(receipt['bound_files']),'required_new_evidence_backed_up':True,'new_checkpoints_generated':0,'local_models_preserved':True,'scope':'New campaign/source review evidence and current handoff; existing historical GCS objects not all reverified'}
(P/'final-backup-receipt.json').write_text(json.dumps(proof,indent=2)+'\n');rb.unlink();print(json.dumps(proof))
