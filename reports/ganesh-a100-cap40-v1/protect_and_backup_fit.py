"""Read-only protected probes and full stopped-fit backup verification."""
import datetime as dt,fcntl,hashlib,json,os,subprocess,tarfile,time
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
R=Path('/opt/english-eager');os.chdir(R);D=R/'fit-closeout';D.mkdir(exist_ok=False)
assert (R/'termination-diagnosis/result.json').exists()
lock=open('/tmp/ganesh-gpu-writer.lock','a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
r=json.loads((R/'pilot-request.json').read_text());c=r['training_inputs'];state=R/'runs/ganesh-recovery-next/controller/state.json'
assert json.loads(state.read_text())['running'] is None
assert json.loads(state.read_text())['failed']['id']=='fit_train'
assert dt.datetime.now(dt.timezone.utc)<dt.datetime.fromisoformat('2026-11-18T01:00:00+00:00')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(a,timeout=900):return subprocess.run(a,check=True,timeout=timeout)
original=sha(state);suite='cloud_training/evaluation/conversation-tools-dev.json'
assert sha(R/suite)==r['files'][suite]
for step in (0,20,30):
 ck=R/f'runs/ganesh-recovery-next/fit/step-{step:08d}';out=D/f'tools-{step:08d}.json'
 run(['/usr/bin/python3','-m','cloud_training.nano_fit_probe','--checkpoint',str(ck),'--checkpoint-sha',sha(ck/'manifest.json'),'--suite',suite,'--suite-sha',sha(suite),'--repo',c['repo'],'--tokenizer',c['tokenizer'],'--tokenizer-sha',c['tokenizer_sha256'],'--output',str(out),'--scope','development','--device','cuda','--timeout-seconds','900','--allow-base'],timeout=1000)
assert sha(state)==original
# No child remains after subprocess joins; retain the lock throughout backup.
j=json.loads((R/'runs/ganesh-recovery-next/fit/retention-journal.json').read_text());proof=[]
for e in j['entries']:
 if e['state']!='committed':continue
 rec=e['receipt'];step=rec['step'];ck=R/f'runs/ganesh-recovery-next/fit/step-{step:08d}';validate_bundle(ck)
 b=D/f'readback-{step:08d}';b.mkdir()
 for n in ('manifest.json','metadata.json','payload.pt','COMMITTED'):
  run(['gcloud','storage','cp',rec['remote_prefix']+'/'+n,str(b/n),'--quiet'])
 validate_bundle(b);assert (b/'manifest.json').read_bytes()==(ck/'manifest.json').read_bytes()
 proof.append({'step':step,'uri':rec['remote_prefix'],'manifest_sha256':sha(ck/'manifest.json'),'full_readback_verified':True})
 # Remove only verified redundant readback; original + GCS remain.
 for n in ('manifest.json','metadata.json','payload.pt','COMMITTED'):(b/n).unlink()
 b.rmdir()
(D/'checkpoint-readbacks.json').write_text(json.dumps(proof,indent=2)+'\n')
archive=R/'fit-closeout-evidence.tar.gz'
with tarfile.open(archive,'w:gz') as t:
 for directory in ('fit-closeout','stopped-fit-assessment','termination-diagnosis','runs/ganesh-recovery-next/controller','runs/ganesh-recovery-next/fit-probes'):
  t.add(R/directory,arcname=directory)
 for n in ('result.json','updates.jsonl','progress.json','quality-preflight.json','retention-journal.json'):
  t.add(R/'runs/ganesh-recovery-next/fit'/n,arcname='training/'+n)
 t.add(R/'runs/ganesh-recovery-next/fit_probes-receipt.json',arcname='fit_probes-receipt.json')
 t.add(Path(__file__),arcname='protect_and_backup_fit.py')
 t.add(Path('/home/admin_executespec_ai/diagnose_end_tokens.py'),arcname='diagnose_end_tokens.py')
prefix=json.loads((R/'config.json').read_text())['backup_prefix']+'/english/fit-closeout';uri=prefix+'/evidence.tar.gz'
run(['gcloud','storage','cp',str(archive),uri,'--quiet']);b=R/'fit-closeout-evidence-readback.tar.gz';run(['gcloud','storage','cp',uri,str(b),'--quiet']);assert sha(b)==sha(archive)
receipt={'checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'uri':uri,'sha256':sha(archive),'checkpoint_readbacks':proof,'evidence_full_readback':True,'controller_failure_preserved':sha(state)==original,'training_accepted':False,'gpu_children_joined':True}
p=D/'backup.json';p.write_text(json.dumps(receipt,indent=2)+'\n');run(['gcloud','storage','cp',str(p),prefix+'/backup.json','--quiet'])
print(json.dumps(receipt),flush=True)
