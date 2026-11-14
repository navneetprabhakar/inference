"""Independently verify a finished stage's GCS archive and materialize review evidence."""
import hashlib,json,subprocess,sys,tarfile
from pathlib import Path
stage=sys.argv[1]
if stage not in ('repair','faults'):raise ValueError('Unknown stage')
p=Path(__file__).parent;q=p/stage;root=p.resolve().parents[1]
remote=json.loads((p/'config.json').read_text())['backup_prefix']+'/'+stage
archive=root/'runs/english-a100-v1'/('worker-'+stage+'-evidence.tar.gz')
subprocess.run(['gcloud','storage','cp',remote+'/closeout.json',str(q/'worker-closeout.json'),'--quiet'],check=True,timeout=120)
proof=json.loads((q/'worker-closeout.json').read_text())
subprocess.run(['gcloud','storage','cp',remote+'/'+proof.get('evidence_object','evidence.tar.gz'),str(archive),'--quiet'],check=True,timeout=120)
if hashlib.sha256(archive.read_bytes()).hexdigest()!=proof['evidence_sha256']:raise ValueError('Evidence hash mismatch')
with tarfile.open(archive) as tar:
 for n in tar.getnames():
  if n=='results/qualification.json' or n.endswith('/result.json') or n.endswith('/updates.jsonl'):
   target=q/('worker-'+n.replace('/','-'));target.write_bytes(tar.extractfile(n).read())
 (q/'worker-qualification.json').write_bytes(tar.extractfile('results/qualification.json').read())
proof['local_archive_readback_verified']=True;(q/'worker-backup-check.json').write_text(json.dumps(proof,indent=2)+'\n')
result=json.loads((q/'worker-qualification.json').read_text());print(json.dumps({k:result.get(k) for k in ['status','comparison','error','backup_verified']},indent=2))
