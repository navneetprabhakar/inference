"""Approved cap40 A100 qualification: actual capture/replay; no English fit launch."""
import datetime as dt,hashlib,json,os,signal,subprocess,sys,time,tarfile
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_restart_compare import compare_bundles,compare_and_record
from cloud_training.nano_update_trace import compare_traces
from cloud_training.l4_recovery_check import upload_bundle
from cloud_training.nano_qualification_schedule import restart_branches,validate_restart_branches
ROOT=Path('/opt/english');OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
config=json.loads((ROOT/'config.json').read_text())
with (ROOT/'qualification-started').open('x') as marker:marker.write(config['run_id']+'\n')
DEADLINE=dt.datetime.fromisoformat(config['qualification_deadline_utc'].replace('Z','+00:00')).timestamp()
REMOTE=config['backup_prefix'];BASE=ROOT/'base';PACKET=ROOT/'reports/english-first-v1'
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
       '--microbatch','1','--epochs','64','--max-updates',str(spec['max_updates']),'--lr-multiplier','.25',
       '--eval-every-updates',str(spec['eval_every_updates']),'--eval-rows','512',
       '--packing-buffer-size','1','--seed','103','--trace-updates','2','--capture-muon-step','1','--fit-eval-steps','0','16','32','64','--deterministic','--checkpoint-reserve-seconds','600','--deadline-utc',config['worker_deadline_utc'],
       '--backup-prefix',REMOTE+('/signal/checkpoints' if branch.startswith('signal') else '/split/checkpoints' if branch.startswith('split') else '/upload-fault/checkpoints' if branch=='upload_fault' else '/uninterrupted/checkpoints')]
 if resume is not None:argv+=['--resume',str(resume)]
 if signal_test:
  os.environ['FAULT_SIGNAL_MARKER']=str(OUT/'signal-marker.json')
  argv=[sys.executable,str(ROOT/'signal_inject.py'),*argv[3:]]
 code=run(argv,name+'.log',env=env,check=check)
 return OUT/name if check else code
result={'status':'running','quality_accepted':False,'pilot_started':False,'backup_verified':False}
try:
 import torch
 assert torch.__version__.startswith('2.9.1') and torch.version.cuda=='12.9'
 assert torch.cuda.device_count()==1 and 'A100' in torch.cuda.get_device_name(0)
 assert torch.cuda.is_bf16_supported()
 assert 39*1024**3 < torch.cuda.get_device_properties(0).total_memory < 42*1024**3
 import nanochat.flash_attention as attention
 assert not attention.USE_FA3, 'This A100 qualification explicitly requires native SDPA'
 result['runtime']={'torch':torch.__version__,'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0),'attention':'sdpa'}
 validate_restart_branches(restart_branches())
 download_bundle(config['base_uri'],BASE)
 assert hashlib.sha256((BASE/'manifest.json').read_bytes()).hexdigest()==config['base_manifest_sha256']
 ref=sft('uninterrupted');first=sft('split_first')
 progress=json.loads((first/'progress.json').read_text());remote=progress['last_checkpoint']['upload']['remote_prefix']
 restored=ROOT/'restored-step1';download_bundle(remote,restored)
 resumed=sft('split_resume',resume=restored)
 # Preserve the discriminating raw kernel experiment even when restart comparison fails.
 run([sys.executable,str(ROOT/'capture_compare.py'),str(ref/'optimizer-capture/step-00000001'),str(resumed/'optimizer-capture/step-00000001'),str(OUT/'capture-comparison.json')],'capture-compare.log')
 captures=json.loads((OUT/'capture-comparison.json').read_text())
 if not all(captures[k] for k in ('input_values_layout_equal','output_values_layout_equal','context_equal')):raise ValueError('Actual optimizer captures differ')
 for mode in ('eager','compiled'):
  for repeat in (1,2):
   run([sys.executable,'-m','cloud_training.nano_optimizer_capture','--capture',str(ref/'optimizer-capture/step-00000001'),'--repo',str(ROOT/'nanochat-source'),'--mode',mode,'--output',str(OUT/f'replay-{mode}-{repeat}')],f'replay-{mode}-{repeat}.log')
 run([sys.executable,str(ROOT/'capture_compare.py'),'--replays',str(OUT)],'replay-comparison.log')
 replay=json.loads((OUT/'replay-comparison.json').read_text())
 if not all(replay[m]['fresh_process_equal'] and replay[m][r]['repeatable_exact'] for m in ('eager','compiled') for r in ('first','second')):raise ValueError('GPU kernel replay not repeatable')
 if not all(c['matches_captured_output_exact'] for r in ('first','second') for c in replay['compiled'][r]['calls']):raise ValueError('Compiled replay differs from captured output')
 result['replay']=replay
 comparison=compare_and_record(ref/'step-00000002',resumed/'step-00000002',OUT/'normal-comparison.json')
 result.update(comparison=comparison,fresh_process_gcs_restore=True)
 signal_branch=sft('signal',signal_test=True)
 marker=json.loads((OUT/'signal-marker.json').read_text())
 if not marker['partial_gradients_present'] or not marker['live_post_rollback_saved']:raise ValueError('Signal injection not verified')
 initial=compare_and_record(signal_branch/'step-00000000',signal_branch/'interrupted-live',OUT/'rollback-comparison.json')
 progress=json.loads((signal_branch/'progress.json').read_text())
 restored0=ROOT/'restored-step0';download_bundle(progress['last_checkpoint']['upload']['remote_prefix'],restored0)
 signal_resume=sft('signal_resume',resume=restored0)
 traces=compare_traces(first/'update-trace',signal_resume/'update-trace')
 (OUT/'signal-trace-comparison.json').write_text(json.dumps(traces,indent=2)+'\n')
 signal_comparison=compare_and_record(first/'step-00000001',signal_resume/'step-00000001',OUT/'signal-comparison.json')
 if traces['status']!='pass':raise ValueError('Trace boundaries differ; diagnose before proceeding')
 result.update(signal=signal_comparison,rollback=initial,traces=traces)
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
 result['decode_benchmark']=json.loads((OUT/'decode-benchmark.json').read_text())
 if not result['decode_benchmark']['fits_predeclared_probe_timeouts']:raise ValueError('Measured decode does not fit bounded probes')
 result.update(status='qualification_pass_pending_provider_stop')

except BaseException as e:
 result.update(status='hold_worker_failure',error=repr(e))
finally:
 # Required surviving bundles are already uploaded by each SFT worker. Independently
 # read back every live receipt; never substitute a successful cp for hash validation.
 try:
  proofs=[]
  # Separate salvage namespace: preserve valid local sole copies even after a failed
  # authoritative journal operation. Never turn a failed journal into a resume pass.
  seen=set()
  for bundle in sorted([*OUT.glob('*/step-*'),*OUT.glob('*/interrupted-live')]):
   if not bundle.is_dir():continue
   validate_bundle(bundle)
   h=hashlib.sha256((bundle/'manifest.json').read_bytes()).hexdigest()
   if h in seen:continue
   seen.add(h)
   receipt=upload_bundle(bundle,remote_prefix=REMOTE+'/salvage/checkpoints',timeout=min(600,remaining(180)))
   dst=ROOT/('verify-'+str(len(proofs)))
   got=download_bundle(receipt['remote_prefix'],dst,reserve=120)
   if got!=receipt['manifest']:raise ValueError('Salvage readback mismatch')
   proofs.append({'source':str(bundle),'remote_prefix':receipt['remote_prefix'],'manifest_sha256':h,'readback':True})
   import shutil;shutil.rmtree(dst)
  result['bundle_readbacks']=proofs;result['backup_verified']=True
 except BaseException as e:result.update(backup_verified=False,backup_error=repr(e))
 (OUT/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
 archive=ROOT/'evidence.tar.gz'
 with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
  for p in OUT.rglob('*'):
   if p.is_file() and p.name!='payload.pt' and not any('compiler-cache' in x for x in p.parts):tar.add(p,arcname='results/'+str(p.relative_to(OUT)))
  tar.add(ROOT/'config.json',arcname='config.json')
  if (ROOT/'bootstrap.log').exists():tar.add(ROOT/'bootstrap.log',arcname='bootstrap.log')
 try:
  copy(archive,REMOTE+'/evidence.tar.gz',reserve=60)
  readback=ROOT/'evidence-readback.tar.gz';copy(REMOTE+'/evidence.tar.gz',readback,reserve=30)
  assert hashlib.sha256(archive.read_bytes()).digest()==hashlib.sha256(readback.read_bytes()).digest()
  if result['backup_verified']:
   closeout=ROOT/'closeout.json'
   closeout.write_text(json.dumps({'evidence_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'all_required_checkpoint_readbacks':True,'evidence_readback':True,'utc':dt.datetime.now(dt.timezone.utc).isoformat()},indent=2)+'\n')
   copy(closeout,REMOTE+'/closeout.json',reserve=20)
   closeout_copy=ROOT/'closeout-readback.json';copy(REMOTE+'/closeout.json',closeout_copy,reserve=10)
   assert closeout.read_bytes()==closeout_copy.read_bytes()
   (ROOT/'normal-stop-ready').write_text('Evidence and required checkpoint readbacks verified\n')
  else:(ROOT/'backup-failure.txt').write_text('Checkpoint verification incomplete; preserve recovery disk')
 except BaseException as e:(ROOT/'backup-failure.txt').write_text(repr(e))
print(json.dumps(result,indent=2))
