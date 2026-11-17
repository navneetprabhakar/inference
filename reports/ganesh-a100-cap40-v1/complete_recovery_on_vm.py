import datetime as dt,hashlib,json,os,signal,subprocess,sys,time,tarfile
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_restart_compare import compare_bundles,compare_and_record
from cloud_training.nano_update_trace import compare_traces
from cloud_training.l4_recovery_check import upload_bundle
from cloud_training.nano_qualification_schedule import restart_branches,validate_restart_branches

import fcntl
ROOT=Path('/opt/english-eager');ORIGINAL=ROOT/'results';OUT=ROOT/'recovery-completion'
worker=(ROOT/'worker.lock').open('a');fcntl.flock(worker,fcntl.LOCK_EX|fcntl.LOCK_NB)
assert (ROOT/'normal-stop-ready').exists() and not (ROOT/'backup-failure.txt').exists()
old=json.loads((ORIGINAL/'qualification.json').read_text())
assert old['status']=='hold_worker_failure' and old['backup_verified']
assert old['comparison']['status']=='pass' and old['replay']['eager']['fresh_process_equal']
assert all(c['matches_captured_output_exact'] for k in ('first','second') for c in old['replay']['eager'][k]['calls'])
assert all(json.loads((ORIGINAL/'capture-comparison.json').read_text())[k] for k in ('input_values_layout_equal','output_values_layout_equal','context_equal'))
assert 'nano_sft.py: error: Deadline must allow reserve and be within6hours' in (ORIGINAL/'signal_resume.log').read_text()
assert not (ORIGINAL/'signal_resume').exists(), 'Never retry a started writer'
marker=json.loads((ORIGINAL/'signal-marker.json').read_text());assert marker['partial_gradients_present'] and marker['live_post_rollback_saved']
rollback=json.loads((ORIGINAL/'rollback-comparison.json').read_text());assert rollback['status']=='pass'
config=json.loads((ROOT/'config.json').read_text());assert config['qualification_deadline_utc']=='2026-11-17T22:31:13Z'
config['worker_deadline_utc']='2026-11-17T22:26:13Z'
DEADLINE=dt.datetime.fromisoformat(config['qualification_deadline_utc'].replace('Z','+00:00')).timestamp()
assert DEADLINE-time.time()>1500, 'Need 10 minutes for pending checks and 15 minutes reserve'
REMOTE=config['backup_prefix'];BASE=ROOT/'base';PACKET=ROOT/'reports/english-first-v1'
OUT.mkdir(exist_ok=False)
(OUT/'completion-plan.json').write_text(json.dumps({'scope':'Only previously unstarted signal-resume, actual upload rejection, and decode timing; no English pilot or rerun of passed checks','original_qualification_deadline_utc':config['qualification_deadline_utc'],'child_deadline_utc':config['worker_deadline_utc'],'provider_stop_utc':config['deadline_utc'],'operational_command_reserve_seconds':900,'approved_cap_usd':40,'old_qualification_sha256':hashlib.sha256((ORIGINAL/'qualification.json').read_bytes()).hexdigest()},indent=2)+'\n')
result={**old,'status':'running_completion','backup_verified':False,'original_qualification_error':old['error']};result.pop('error')

def remaining(reserve=0):
 value=DEADLINE-time.time()-reserve
 if value<=0:raise TimeoutError('Fixed lease exhausted')
 return value

def run(argv,log=None,reserve=900,env=None,check=True):
 with (OUT/(log or 'commands.log')).open('a') as f:
  p=subprocess.Popen(argv,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env=env)
  try:code=p.wait(timeout=remaining(reserve))
  except BaseException:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=20)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   raise
  if check and code:raise RuntimeError('Command failed with exit'+str(code)+': '+str(argv[:4]))
  return code

def copy(src,dst,reserve=900):run(['gcloud','storage','cp',str(src),str(dst),'--quiet'],reserve=reserve)

def download_bundle(remote,destination,reserve=900):
 destination.mkdir()
 for name in ('payload.pt','metadata.json','manifest.json','COMMITTED'):copy(remote+'/'+name,destination/name,reserve)
 return validate_bundle(destination)

def sft(branch,*,resume=None,signal_test=False,env=None,check=True):
 spec=restart_branches().get(branch,restart_branches()["split_first"]);name=branch
 argv=[sys.executable,'-m','cloud_training.nano_sft','--repo',str(ROOT/'nanochat-source'),
       '--base',str(BASE),'--base-manifest-sha',config['base_manifest_sha256'],
       '--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha',config['tokenizer_sha256'],
       '--manifest',str(PACKET/'diagnostic-manifest.json'),'--quality-contract',str(PACKET/'diagnostic-contract.json'),
       '--output',str(OUT/name),'--fit-diagnostic','--context-tokens','2048','--batch-tokens','8192',
       '--microbatch','1','--muon-kernel-mode','eager','--epochs','64','--max-updates',str(spec['max_updates']),'--lr-multiplier','.25',
       '--eval-every-updates',str(spec['eval_every_updates']),'--eval-rows','512',
       '--packing-buffer-size','1','--seed','103','--trace-updates','2','--capture-muon-step','1','--fit-eval-steps','0','16','32','64','--deterministic','--checkpoint-reserve-seconds','600','--deadline-utc',config['worker_deadline_utc'],
       '--backup-prefix',REMOTE+('/signal/checkpoints' if branch.startswith('signal') else '/split/checkpoints' if branch.startswith('split') else '/upload-fault/checkpoints' if branch=='upload_fault' else '/uninterrupted/checkpoints')]
 if resume is not None:argv+=['--resume',str(resume)]
 if signal_test:
  os.environ['FAULT_SIGNAL_MARKER']=str(OUT/'signal-marker.json')
  argv=[sys.executable,str(ROOT/'signal_inject.py'),*argv[3:]]
 code=run(argv,name+'.log',env=env,check=check)
 return OUT/name if check else code

try:
 # The original worker already downloaded and verified this exact GCS checkpoint.
 restored0=ROOT/'restored-step0';validate_bundle(restored0)
 signal_resume=sft('signal_resume',resume=restored0)
 first=ORIGINAL/'split_first'
 traces=compare_traces(first/'update-trace',signal_resume/'update-trace')
 (OUT/'signal-trace-comparison.json').write_text(json.dumps(traces,indent=2)+'\n')
 signal_comparison=compare_and_record(first/'step-00000001',signal_resume/'step-00000001',OUT/'signal-comparison.json')
 if traces['status']!='pass':raise ValueError('Signal recovery trace mismatch')
 result.update(signal=signal_comparison,rollback=rollback,traces=traces)
 # Reject a real payload upload while preserving production credentials and the failed journal.
 import shutil
 from cloud_training.nano_train import CloudJournal
 shim=ROOT/'shim';shim.mkdir();real=shutil.which('gcloud');token=ROOT/'invalid-test-token';token.write_text('invalid-qualification-fault-token\n')
 shutil.copy(ROOT/'upload_fault_shim.py',shim/'gcloud');(shim/'gcloud').chmod(0o700)
 env=dict(os.environ,PATH=str(shim)+os.pathsep+os.environ['PATH'],FAULT_REAL_GCLOUD=real,FAULT_TOKEN_FILE=str(token),FAULT_UPLOAD_MARKER=str(OUT/'upload-marker.json'),FAULT_ALLOWED_PREFIX=REMOTE+'/upload-fault/checkpoints')
 rc=sft('upload_fault',env=env,check=False)
 if rc==0 or not json.loads((OUT/'upload-marker.json').read_text())['payload_upload_intercepted']:raise ValueError('Upload fault not exercised')
 error=(OUT/'upload_fault.log').read_text().lower()
 if not any(x in error for x in ('401','invalid authentication credentials','invalid credentials')):raise ValueError('No actual authentication rejection')
 journal=json.loads((OUT/'upload_fault/retention-journal.json').read_text())
 if journal['lease_phase']!='checkpoint_upload_in_progress' or journal['entries']:raise ValueError('Failed upload falsely committed')
 validate_bundle(OUT/'upload_fault/step-00000000')
 copy(REMOTE+'/upload-fault/checkpoints/retention-journal.json',ROOT/'remote-fault-journal.json')
 remote_journal=json.loads((ROOT/'remote-fault-journal.json').read_text())
 if remote_journal['lease_phase']!='checkpoint_upload_in_progress' or remote_journal['entries']:raise ValueError('Remote failed journal unsafe')
 try:CloudJournal(ROOT/'rejected-resume.json',campaign_prefix=REMOTE+'/upload-fault/checkpoints',identity=journal['identity'],resume_step=0)
 except ValueError as e:
  if 'interrupted operation' not in str(e):raise
  result['upload_rejection']={'real_gcs_rejection':True,'no_committed_receipt':True,'local_bundle_preserved':True,'resume_refused':str(e)}
 else:raise ValueError('Incomplete upload accepted on resume')
 token.unlink()
 run([sys.executable,str(ROOT/'decode_benchmark.py')],'decode-benchmark.log')
 result['decode_benchmark']=json.loads((ORIGINAL/'decode-benchmark.json').read_text())
 if not result['decode_benchmark']['fits_predeclared_probe_timeouts']:raise ValueError('Measured decode does not fit bounded probes')
 result.update(status='qualification_pass_pending_provider_stop')


except BaseException as e:result.update(status='hold_completion_failure',error=repr(e))
finally:
 try:
  proofs=[]
  for bundle in sorted(OUT.glob('*/step-*')):
   validate_bundle(bundle)
   receipt=upload_bundle(bundle,remote_prefix=REMOTE+'/recovery-completion/salvage/checkpoints',timeout=min(600,remaining(180)))
   dst=ROOT/('completion-verify-'+str(len(proofs)));got=download_bundle(receipt['remote_prefix'],dst,reserve=120)
   assert got==receipt['manifest']
   proofs.append({'source':str(bundle),'remote_prefix':receipt['remote_prefix'],'manifest_sha256':hashlib.sha256((bundle/'manifest.json').read_bytes()).hexdigest(),'readback':True})
   import shutil;shutil.rmtree(dst)
  result['original_bundle_readbacks']=old['bundle_readbacks'];result['bundle_readbacks']=proofs;result['backup_verified']=True
 except BaseException as e:result.update(backup_verified=False,backup_error=repr(e))
 (OUT/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
 archive=ROOT/'completion-evidence.tar.gz'
 with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
  for p in OUT.rglob('*'):
   if p.is_file() and p.name!='payload.pt':tar.add(p,arcname='recovery-completion/'+str(p.relative_to(OUT)))
  for name in ('qualification.json','normal-comparison.json','capture-comparison.json','replay-comparison.json','signal-marker.json','rollback-comparison.json','signal_resume.log','decode-benchmark.json'):
   p=ORIGINAL/name
   if p.is_file():tar.add(p,arcname='original-results/'+name)
  tar.add(ROOT/'config.json',arcname='original-config.json')
 try:
  remote=REMOTE+'/recovery-completion';copy(archive,remote+'/evidence.tar.gz',reserve=60)
  readback=ROOT/'completion-readback.tar.gz';copy(remote+'/evidence.tar.gz',readback,reserve=30)
  assert hashlib.sha256(archive.read_bytes()).digest()==hashlib.sha256(readback.read_bytes()).digest()
  assert result['backup_verified']
  closeout=ROOT/'completion-closeout.json';closeout.write_text(json.dumps({'evidence_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'all_required_checkpoint_readbacks':True,'original_checkpoint_readbacks':old['backup_verified'],'evidence_readback':True,'utc':dt.datetime.now(dt.timezone.utc).isoformat()},indent=2)+'\n')
  copy(closeout,remote+'/closeout.json',reserve=20);copy(remote+'/closeout.json',ROOT/'completion-closeout-readback.json',reserve=10)
  assert closeout.read_bytes()==(ROOT/'completion-closeout-readback.json').read_bytes()
  (ROOT/'completion-normal-stop-ready').write_text('Original and completion evidence/readbacks verified\n')
 except BaseException as e:(ROOT/'completion-backup-failure.txt').write_text(repr(e))
print(json.dumps(result,indent=2))
