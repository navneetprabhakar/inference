"""Capture missing upload-error evidence and run the still-unstarted decode benchmark.
No optimizer update, no retry of training, no change to the fixed qualification window.
"""
import datetime as dt,fcntl,hashlib,json,subprocess,time,tarfile,sys
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_train import CloudJournal
R=Path('/opt/english-eager');D=R/'qualification-finalization'
lock=(R/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert (R/'completion-normal-stop-ready').exists() and not (R/'completion-backup-failure.txt').exists()
q=json.loads((R/'recovery-completion/qualification.json').read_text())
assert q['status']=='hold_completion_failure' and q['error']=="ValueError('No actual authentication rejection')" and q['backup_verified']
assert all(q[k]['status']=='pass' for k in ('comparison','signal','rollback','traces'))
assert q['replay']['eager']['fresh_process_equal']
cfg=json.loads((R/'config.json').read_text());end=dt.datetime.fromisoformat(cfg['qualification_deadline_utc'].replace('Z','+00:00')).timestamp()
assert end-time.time()>600 and cfg['deadline_utc']=='2026-11-18T03:05:59Z'
assert not (R/'results/decode-benchmark.json').exists(), 'Do not repeat an existing benchmark'
D.mkdir(exist_ok=False)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(argv,timeout=120,check=True):
 p=subprocess.run(argv,capture_output=True,text=True,timeout=min(timeout,end-time.time()-60))
 if check and p.returncode:raise RuntimeError(p.stderr)
 return p
fault=R/'recovery-completion/upload_fault';validate_bundle(fault/'step-00000000')
marker=json.loads((R/'recovery-completion/upload-marker.json').read_text());assert marker['payload_upload_intercepted']
prefix=cfg['backup_prefix']+'/upload-fault/checkpoints'
assert marker['destination'].startswith(prefix+'/checkpoint-') and marker['destination'].endswith('/payload.pt')
token=R/'invalid-test-token';assert token.read_text()=='invalid-qualification-fault-token\n'
# Capture subprocess stderr directly. The earlier SFT exception hid it because
# upload_bundle captured subprocess output then printed only CalledProcessError.
p=run(['gcloud','--access-token-file='+str(token),'storage','cp',str(fault/'step-00000000/payload.pt'),marker['destination'],'--quiet'],check=False)
(D/'actual-upload-rejection.log').write_text(p.stdout+p.stderr)
assert p.returncode!=0 and any(s in (p.stdout+p.stderr).lower() for s in ('401','invalid authentication credentials','invalid credentials'))
journal=json.loads((fault/'retention-journal.json').read_text());remote=run(['gcloud','storage','cat',prefix+'/retention-journal.json']);(D/'remote-fault-journal.json').write_text(remote.stdout);rj=json.loads(remote.stdout)
assert journal['lease_phase']==rj['lease_phase']=='checkpoint_upload_in_progress' and not journal['entries'] and not rj['entries']
try:CloudJournal(D/'rejected-resume.json',campaign_prefix=prefix,identity=journal['identity'],resume_step=0)
except ValueError as e:
 assert 'interrupted operation' in str(e);resume_error=str(e)
else:raise AssertionError('Incomplete upload accepted for resume')
q['upload_rejection']={'real_gcs_rejection':True,'no_committed_receipt':True,'local_bundle_preserved':True,'resume_refused':resume_error,'supplemental_direct_error_capture':True,'error_log_sha256':sha(D/'actual-upload-rejection.log'),'original_error_not_preserved_by_subprocess_wrapper':True}
token.unlink()
with (D/'decode-benchmark.log').open('x') as f:
 subprocess.run([sys.executable,str(R/'decode_benchmark.py')],cwd=R,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=min(300,end-time.time()-180))
q['decode_benchmark']=json.loads((R/'results/decode-benchmark.json').read_text())
q['prior_instrumentation_error']=q.pop('error');q['status']='qualification_pass_pending_provider_stop' if q['decode_benchmark']['fits_predeclared_probe_timeouts'] else 'hold_decode_forecast'
q['quality_accepted']=False;q['pilot_started']=False;q['supplemental_proof_only_no_optimizer_update']=True
qpath=D/'qualification.json';qpath.write_text(json.dumps(q,indent=2)+'\n')
archive=R/'qualification-finalization.tar.gz'
with tarfile.open(archive,'w:gz') as t:
 for p in D.iterdir():
  if p.is_file():t.add(p,arcname=p.name)
 t.add(R/'results/decode-benchmark.json',arcname='decode-benchmark.json')
 t.add(Path(__file__),arcname='finalize_qualification_on_vm.py')
uri=cfg['backup_prefix']+'/qualification-finalization/evidence.tar.gz';run(['gcloud','storage','cp',str(archive),uri,'--quiet'])
readback=R/'qualification-finalization-readback.tar.gz';run(['gcloud','storage','cp',uri,str(readback),'--quiet']);assert sha(archive)==sha(readback)
receipt=D/'backup.json';receipt.write_text(json.dumps({'checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'uri':uri,'sha256':sha(archive),'full_readback_verified':True,'prior_checkpoint_backups_verified':q['backup_verified'],'qualification_sha256':sha(qpath)},indent=2)+'\n')
run(['gcloud','storage','cp',str(receipt),cfg['backup_prefix']+'/qualification-finalization/backup.json','--quiet'])
(R/'final-qualification-ready').write_text('Complete qualification evidence backed up; inspect status before training\n')
print(json.dumps({'status':q['status'],'decode':q['decode_benchmark'],'backup':json.loads(receipt.read_text())},indent=2))
