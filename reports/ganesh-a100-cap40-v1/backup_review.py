import datetime,hashlib,json,subprocess,tarfile,time
from pathlib import Path
P=Path('reports/ganesh-a100-cap40-v1');start=time.monotonic()
while not (P/'local-fit-smoke.json').exists():
 if time.monotonic()-start>7200:raise TimeoutError('Local check not completed')
 time.sleep(30)
a=Path('runs/ganesh-a100-cap40-v1/english-review.tar.gz')
with tarfile.open(a,'w:gz') as t:
 for p in sorted(P.rglob('*')):
  if p.is_file() and p.suffix not in ('.lock','.pyc') and '__pycache__' not in p.parts and p.name not in ('review-backup.json','review-backup.log'):
   t.add(p,arcname=str(p))
 for n in ['OWN_BASE_HANDOFF.txt','cloud_training/nano_sft.py','cloud_training/nano_recovery_gate.py','cloud_training/nano_recovery_tasks.py','verify_nano_sft.py','verify_nano_recovery_gate.py','verify_nano_recovery_tasks.py']:t.add(n,arcname=n)
uri='gs://forge-ownbase-a100-20261110/ganesh-a100-cap40-v1/ganesh-a100-1117-203113/eager-r2/english/final-review/evidence.tar.gz'
subprocess.run(['gcloud','storage','cp',str(a),uri,'--quiet'],check=True,timeout=300)
b=a.with_name('english-review-readback.tar.gz');subprocess.run(['gcloud','storage','cp',uri,str(b),'--quiet'],check=True,timeout=300)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(a)==sha(b)
r={'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'uri':uri,'sha256':sha(a),'full_readback_verified':True,'contains_full_reviews_and_local_weights_receipts':True}
(P/'review-backup.json').write_text(json.dumps(r,indent=2)+'\n');subprocess.run(['gcloud','storage','cp',str(P/'review-backup.json'),uri.rsplit('/',1)[0]+'/backup.json','--quiet'],check=True,timeout=180);print(json.dumps(r))
