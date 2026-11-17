"""Install only the approved retention-order gate after qualification has joined."""
import fcntl,hashlib,json,os,subprocess,tarfile
from pathlib import Path
from cloud_training.nano_package import extract_verified
ROOT=Path('/opt/english');P=ROOT/'pilot-evidence';controls=json.loads((P/'controls.json').read_text())
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
with (ROOT/'worker.lock').open('a') as worker,Path('/tmp/ganesh-gpu-writer.lock').open('a') as gpu:
 fcntl.flock(worker,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(gpu,fcntl.LOCK_EX|fcntl.LOCK_NB)
 assert (ROOT/'normal-stop-ready').is_file() and not (ROOT/'backup-failure.txt').exists()
 q=json.loads((ROOT/'results/qualification.json').read_text());assert q['status']=='qualification_pass_pending_provider_stop' and q['backup_verified']
 assert not (ROOT/'pilot-request.json').exists() and not (ROOT/'qualification-runtime.tar.gz').exists() and not (P/'control-update-intent.json').exists()
 old=ROOT/'runtime.tar.gz';assert sha(old)==controls['qualification_runtime_sha256']
 b=json.loads((P/'input-backups.json').read_text())['inputs'][0];assert b['sha256']==controls['runtime_sha256'] and b['independent_readback']
 pending=ROOT/'pilot-runtime.pending.tar.gz';subprocess.run(['gcloud','storage','cp',b['uri'],str(pending),'--quiet'],check=True,timeout=180);assert sha(pending)==controls['runtime_sha256']
 with tarfile.open(old) as t:before=json.load(t.extractfile('package-manifest.json'))
 with tarfile.open(pending) as t:
  manifest_bytes=t.extractfile('package-manifest.json').read();after=json.loads(manifest_bytes);gate=t.extractfile('cloud_training/nano_recovery_gate.py').read();index_bytes=t.extractfile('nanochat-source/.git/index').read()
 assert set(before['files'])==set(after['files'])
 changed=[n for n in before['files'] if before['files'][n]!=after['files'][n]];assert changed==['cloud_training/nano_recovery_gate.py']
 repo=ROOT/'nanochat-source'
 assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()==before['revision']
 assert not subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip()
 # Git status refreshes the index stat cache; all actual source/dependency bytes
 # remain exact. Preserve that metadata, then normalize to the archived index.
 for n,entry in before['files'].items():
  if n!='nanochat-source/.git/index':assert sha(ROOT/n)==entry['sha256'],n
 assert hashlib.sha256(gate).hexdigest()==controls['recovery_gate_sha256']
 (P/'control-update-intent.json').write_text(json.dumps({'old_runtime_sha256':sha(old),'new_runtime_sha256':sha(pending),'changed_files':changed,'qualification_writer_joined':True,'training_optimizer_serving_files_unchanged':True},indent=2)+'\n')
 (P/'qualification-nano_recovery_gate.py').write_bytes((ROOT/'cloud_training/nano_recovery_gate.py').read_bytes())
 (P/'qualification-package-manifest.json').write_bytes((ROOT/'package-manifest.json').read_bytes())
 (P/'qualification-git-index').write_bytes((repo/'.git/index').read_bytes())
 (repo/'.git/index').write_bytes(index_bytes)
 (ROOT/'cloud_training/nano_recovery_gate.pending').write_bytes(gate);os.replace(ROOT/'cloud_training/nano_recovery_gate.pending',ROOT/'cloud_training/nano_recovery_gate.py')
 (ROOT/'package-manifest.pending').write_bytes(manifest_bytes);os.replace(ROOT/'package-manifest.pending',ROOT/'package-manifest.json')
 old.rename(ROOT/'qualification-runtime.tar.gz');pending.rename(old)
 extract_verified(old,ROOT)
 (P/'control-update-complete.json').write_text(json.dumps({'status':'verified_control_plane_update','training_source_identity_unchanged':True,'runtime_sha256':sha(old)},indent=2)+'\n')
 print('Control-plane update verified; no training started; actual STOP deferred to closeout')
