"""Actual signal and GCS rejection tests; qualification only, no fit pilot."""
import ast,datetime as dt,hashlib,json,os,shutil,subprocess,sys,tarfile,time
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_restart_compare import compare_bundles
from cloud_training.nano_train import CloudJournal
from cloud_training.l4_recovery_check import upload_bundle
from cloud_training.nano_qualification_schedule import restart_branches
ROOT=Path('/opt/english-faults');PREV=Path('/opt/english-repair');OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
config=json.loads((ROOT/'config.json').read_text());DEADLINE=dt.datetime.fromisoformat(config['deadline_utc'].replace('Z','+00:00')).timestamp();REMOTE=config['backup_prefix']
def require(ok,msg):
 if not ok:raise ValueError(msg)
def remaining(reserve):
 n=DEADLINE-time.time()-reserve
 if n<=0:raise TimeoutError('Original lease exhausted')
 return n
def command(argv,log,*,env=None,check=True,reserve=900):
 with (OUT/log).open('a') as f:
  p=subprocess.Popen(argv,stdout=f,stderr=subprocess.STDOUT,start_new_session=True,env=env)
  try:rc=p.wait(timeout=remaining(reserve))
  except BaseException:
   import signal
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=20)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   raise
 if check and rc:raise RuntimeError('Command failed '+log+' rc='+str(rc))
 return rc
def cp(src,dst,reserve=900):command(['gcloud','storage','cp',str(src),str(dst),'--quiet'],'io.log',reserve=reserve)
def download(remote,dst,reserve=900):
 dst.mkdir()
 for n in ('payload.pt','metadata.json','manifest.json','COMMITTED'):cp(remote+'/'+n,dst/n,reserve)
 return validate_bundle(dst)
def argv(name,resume=None):
 tree=ast.parse((PREV/'gpu_qualify.py').read_text());fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sft');calls=[]
 class Captured(Exception):pass
 def capture(a,*args):calls.append(a);raise Captured()
 scope={'sys':sys,'restart_branches':restart_branches,'ROOT':PREV,'BASE':PREV/'base','PACKET':PREV/'packet','OUT':OUT,'REMOTE':REMOTE,'config':config,'run':capture}
 exec(compile(ast.Module(body=[fn],type_ignores=[]),'qualified_sft_arguments','exec'),scope)
 try:scope['sft']('split_first',resume=resume)
 except Captured:pass
 a=calls[0];a[a.index('--output')+1]=str(OUT/name);a[a.index('--backup-prefix')+1]=REMOTE+('/signal/checkpoints' if name.startswith('signal') else '/upload-fault/checkpoints')
 return a
result={'status':'running','pilot_started':False,'quality_accepted':False,'backup_verified':False}
try:
 import torch
 import nanochat.flash_attention as attention
 require(torch.__version__.startswith('2.9.1') and torch.version.cuda=='12.9' and torch.cuda.device_count()==1 and 'A100' in torch.cuda.get_device_name(0) and torch.cuda.is_bf16_supported() and not attention.USE_FA3,'Qualified runtime changed')
 result['runtime']={'torch':torch.__version__,'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0),'attention':'sdpa'}
 prev=json.loads((PREV/'results/qualification.json').read_text())
 require(prev['status']=='restart_pass_pending_fault_drills' and prev['comparison']['status']=='pass','Exact restart prerequisite failed')
 require((PREV/'normal-stop-ready').exists(),'Prior normal closeout absent')
 require(shutil.disk_usage(ROOT).free>26*1024**3,'Insufficient disk for fault bundles and readbacks')
 # Production runner receives real SIGTERM after one accumulated microbatch.
 a=argv('signal');env=dict(os.environ,FAULT_SIGNAL_MARKER=str(OUT/'signal-marker.json'))
 a=[sys.executable,str(ROOT/'signal_inject.py'),*a[3:]]
 command(a,'signal.log',env=env)
 marker=json.loads((OUT/'signal-marker.json').read_text());stopped=json.loads((OUT/'signal/result.json').read_text())
 require(marker['partial_gradients_present'] and marker['live_post_rollback_saved'] and stopped['step']==0 and stopped['reason']=='lease_or_signal','Signal rollback failed')
 initial=compare_bundles(OUT/'signal/step-00000000',OUT/'signal/interrupted-live')
 require(initial['status']=='pass','Initial signal branch differs')
 progress=json.loads((OUT/'signal/progress.json').read_text());remote=progress['last_checkpoint']['upload']['remote_prefix'];restored=ROOT/'restored-signal';download(remote,restored)
 command(argv('signal_resume',restored),'signal-resume.log')
 resumed=compare_bundles(PREV/'results/split_first/step-00000001',OUT/'signal_resume/step-00000001')
 require(resumed['status']=='pass','Signal rollback/resume differs')
 result['signal']={'injection':marker,'initial':initial,'resumed':resumed,'fresh_gcs_restore':True}
 # Real GCS authentication rejection on payload upload only. Journal writes still
 # use normal credentials; no IAM change, production credential edit or false receipt.
 shim=ROOT/'shim';shim.mkdir();real=shutil.which('gcloud');token=ROOT/'invalid-test-token';token.write_text('invalid-qualification-fault-token\n')
 shutil.copy(ROOT/'upload_fault_shim.py',shim/'gcloud');(shim/'gcloud').chmod(0o700)
 env=dict(os.environ,PATH=str(shim)+os.pathsep+os.environ['PATH'],FAULT_REAL_GCLOUD=real,FAULT_TOKEN_FILE=str(token),FAULT_UPLOAD_MARKER=str(OUT/'upload-marker.json'),FAULT_ALLOWED_PREFIX=REMOTE+'/upload-fault/checkpoints')
 rc=command(argv('upload_fault'),'upload-fault.log',env=env,check=False)
 require(rc!=0,'Injected upload unexpectedly succeeded')
 require(json.loads((OUT/'upload-marker.json').read_text())['payload_upload_intercepted'],'Upload injection not reached')
 error_text=(OUT/'upload-fault.log').read_text().lower()
 require('401' in error_text or 'invalid authentication credentials' in error_text or 'invalid credentials' in error_text,'No genuine GCS authentication rejection observed')
 journal=json.loads((OUT/'upload_fault/retention-journal.json').read_text())
 require(journal['lease_phase']=='checkpoint_upload_in_progress' and not journal['entries'],'Upload fault falsely committed')
 validate_bundle(OUT/'upload_fault/step-00000000')
 cp(REMOTE+'/upload-fault/checkpoints/retention-journal.json',ROOT/'remote-fault-journal.json')
 remote_journal=json.loads((ROOT/'remote-fault-journal.json').read_text())
 require(remote_journal['lease_phase']=='checkpoint_upload_in_progress' and not remote_journal['entries'],'Remote failure journal unsafe')
 try:CloudJournal(ROOT/'rejected-resume.json',campaign_prefix=REMOTE+'/upload-fault/checkpoints',identity=journal['identity'],resume_step=0)
 except ValueError as e:
  require('interrupted operation' in str(e),'Unexpected resume refusal');result['upload_fault']={'real_gcs_rejection':True,'no_committed_receipt':True,'local_bundle_preserved':True,'resume_refused':str(e)}
 else:raise ValueError('Unfinished upload accepted on resume')
 token.unlink();result['status']='signal_upload_pass_pending_provider_stop'
except BaseException as e:result.update(status='hold_fault_qualification',error=repr(e))
finally:
 # Preserve every required local test bundle, including intentionally failed upload.
 # The failed journal stays failed; verified salvage is separate and never promotes it.
 try:
  proofs=[]
  for index,bundle in enumerate(sorted([*OUT.glob('*/step-*'),*OUT.glob('*/interrupted-live')])):
   if not bundle.is_dir():continue
   validate_bundle(bundle)
   receipt=upload_bundle(bundle,remote_prefix=REMOTE+'/salvage/checkpoints',timeout=min(600,remaining(180)))
   copy=ROOT/('verify-'+str(index));got=download(receipt['remote_prefix'],copy,reserve=120)
   require(got==receipt['manifest'],'Salvage readback mismatch')
   proofs.append({'source':str(bundle),'receipt':receipt,'readback':True});shutil.rmtree(copy)
  result['bundle_readbacks']=proofs;result['backup_verified']=True
 except BaseException as e:result.update(backup_verified=False,backup_error=repr(e))
 (OUT/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
 archive=ROOT/'evidence.tar.gz'
 with tarfile.open(archive,'w:gz') as tar:
  for p in OUT.rglob('*'):
   if p.is_file() and p.name!='payload.pt':tar.add(p,arcname='results/'+str(p.relative_to(OUT)))
  for name in ('config.json','bootstrap.log'):
   if (ROOT/name).exists():tar.add(ROOT/name,arcname=name)
 try:
  cp(archive,REMOTE+'/evidence.tar.gz',reserve=60);copy=ROOT/'evidence-readback.tar.gz';cp(REMOTE+'/evidence.tar.gz',copy,reserve=30)
  require(hashlib.sha256(archive.read_bytes()).digest()==hashlib.sha256(copy.read_bytes()).digest(),'Evidence mismatch')
  if result['backup_verified']:
   close=ROOT/'closeout.json';close.write_text(json.dumps({'evidence_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'all_required_checkpoint_readbacks':True,'evidence_readback':True,'status':result['status']})+'\n')
   cp(close,REMOTE+'/closeout.json',reserve=20);cp(REMOTE+'/closeout.json',ROOT/'closeout-readback.json',reserve=10)
   require(close.read_bytes()==(ROOT/'closeout-readback.json').read_bytes(),'Closeout mismatch')
   (ROOT/'backup-ready').write_text('Verified; external controller must complete provider STOP drill\n')
 except BaseException as e:(ROOT/'backup-failure.txt').write_text(repr(e))
print(json.dumps(result,indent=2))
