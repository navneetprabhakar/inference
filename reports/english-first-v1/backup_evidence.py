"""Compact required future-use evidence backup; no weights/caches duplicated."""
import datetime as dt,hashlib,json,subprocess,tarfile,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];P=Path(__file__).parent;R=ROOT/'runs/english-first-v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=[p for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='backup-receipt.json' and p.suffix!='.lock']
files += [ROOT/n for n in ['AGENTS.md','OWN_BASE_HANDOFF.txt','OWN_BASE_NEXT_STEPS.txt','cloud_training/nano_sft.py','cloud_training/nano_quality_gate.py','cloud_training/nano_fit_contract.py','cloud_training/nano_package.py','cloud_training/nano_qualification_schedule.py','cloud_training/nano_l4_lease.py','verify_nano_fit_contract.py','verify_nano_qualification_schedule.py','verify_nano_l4_lease.py']]
bindings={str(p.relative_to(ROOT)):sha(p) for p in files}
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');archive=R/('evidence-'+stamp+'.tar.gz')
with tarfile.open(archive,'w:gz') as tar:
 for p in files:tar.add(p,arcname=str(p.relative_to(ROOT)))
uri='gs://forge-ownbase-a100-20261110/english-first-v1/evidence/'+stamp+'-'+sha(archive)+'.tar.gz'
subprocess.run(['gcloud','storage','cp',str(archive),uri,'--quiet','--if-generation-match=0'],check=True,timeout=180)
with tempfile.TemporaryDirectory() as d:
 copy=Path(d)/'readback.tar.gz';subprocess.run(['gcloud','storage','cp',uri,str(copy),'--quiet'],check=True,timeout=180)
 assert sha(copy)==sha(archive)
 with tarfile.open(copy) as tar:
  assert set(tar.getnames())==set(bindings)
  for member in tar:
   assert member.isfile() and hashlib.sha256(tar.extractfile(member).read()).hexdigest()==bindings[member.name]
receipt={'utc':stamp,'uri':uri,'sha256':sha(archive),'bytes':archive.stat().st_size,'files':len(files),'independent_readback_and_member_hashes':True,'weights_or_caches_duplicated':False,'bindings':bindings}
(P/'backup-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(uri)
