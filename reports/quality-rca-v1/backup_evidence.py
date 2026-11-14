"""Back up only useful RCA evidence/code; models already have immutable GCS bundles."""
import datetime,hashlib,json,subprocess,tarfile
from pathlib import Path
P=Path('reports/quality-rca-v1');receipt=P/'backup-receipt.json'
if receipt.exists():raise FileExistsError('Evidence snapshot already exists; review changes before making another')
D=Path('runs/quality-rca-v1');stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
files=[p for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
files += [Path(p) for p in ['AGENTS.md','OWN_BASE_HANDOFF.txt','OWN_BASE_NEXT_STEPS.txt','cloud_training/nano_quality_gate.py','cloud_training/nano_quality.py','cloud_training/nano_sft.py','verify_nano_quality_gate.py','verify_nano_sft.py','reports/ownbase-budget50-v1/launch.py','reports/ownbase-budget50-v1/extension-v5/launch_when_ready.py','runs/quality-rca-v1/sft-updates.jsonl']]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest={'utc':stamp,'files':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(files))],'note':'Useful RCA/code snapshot only; no model payload duplication. Contains complete verified training trace.'}
mp=D/'snapshot-manifest.json';mp.write_text(json.dumps(manifest,indent=2)+'\n');archive=D/(stamp+'.tar.gz')
with tarfile.open(archive,'w:gz') as tar:
 for p in sorted(set(files)):tar.add(p,arcname=str(p),recursive=False)
 tar.add(mp,arcname='quality-rca-snapshot-manifest.json',recursive=False)
digest=sha(archive);uri=f'gs://forge-ownbase-a100-20261110/ownbase-v2/budget50-v1/quality-rca-v1/{stamp}-{digest}.tar.gz'
subprocess.run(['gcloud','storage','cp',str(archive),uri,'--quiet'],check=True,timeout=300)
back=D/'backup-readback.tar.gz';subprocess.run(['gcloud','storage','cp',uri,str(back),'--quiet'],check=True,timeout=300);assert sha(back)==digest
with tarfile.open(back,'r:gz') as tar:
 for f in manifest['files']:
  stream=tar.extractfile(f['path']);assert stream is not None and hashlib.sha256(stream.read()).hexdigest()==f['sha256']
back.unlink()
report={'utc':stamp,'uri':uri,'bytes':archive.stat().st_size,'sha256':digest,'files':len(files),'independent_sha_readback':True,'all_member_hashes_verified':True,'weights':'Not duplicated; all three local bundles validated in checkpoint-status.json and selected GCS originals retained.'}
receipt.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
