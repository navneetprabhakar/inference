import hashlib,json,tarfile,subprocess,datetime
from pathlib import Path
R=Path('/opt/english');D=R/'diagnostic-results';archive=R/'optimizer-diagnosis-evidence.tar.gz';prefix=json.loads((R/'config.json').read_text())['backup_prefix']+'/diagnosis'
assert D.is_dir()
with tarfile.open(archive,'w:gz',compresslevel=1) as t:
 for p in D.rglob('*'):
  if p.is_file() and not any('cache' in x for x in p.relative_to(D).parts):t.add(p,arcname='diagnostic-results/'+str(p.relative_to(D)))
 for name in ('capture-logical-difference.json','normal-comparison-supplemental.json','trace-boundary-diagnosis.json','first-update-different-tensors.json'):
  p=R/'results'/name
  if p.is_file():t.add(p,arcname='results/'+name)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
subprocess.run(['gcloud','storage','cp',str(archive),prefix+'/evidence.tar.gz','--quiet'],check=True,timeout=300)
readback=R/'optimizer-diagnosis-readback.tar.gz';subprocess.run(['gcloud','storage','cp',prefix+'/evidence.tar.gz',str(readback),'--quiet'],check=True,timeout=300);assert sha(archive)==sha(readback)
receipt=R/'diagnosis-backup.json';receipt.write_text(json.dumps({'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'uri':prefix+'/evidence.tar.gz','sha256':sha(archive),'bytes':archive.stat().st_size,'full_readback_verified':True},indent=2)+'\n')
subprocess.run(['gcloud','storage','cp',str(receipt),prefix+'/receipt.json','--quiet'],check=True,timeout=90);print(receipt.read_text())
