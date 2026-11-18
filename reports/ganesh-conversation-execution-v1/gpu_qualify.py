"""Changed block path qualification only. Never dispatches a learning pilot."""
import datetime as dt,hashlib,json,os,shutil,signal,subprocess,sys,time
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_restart_compare import compare_and_record
from cloud_training.nano_data import sha256_file
ROOT=Path('/opt/ganesh-conversation');P=ROOT/'reports/ganesh-conversation-execution-v1';OUT=ROOT/'qualification-v2';OUT.mkdir(exist_ok=True)
cfg=json.loads((ROOT/'config-v2.json').read_text());start=time.time();deadline=min(start+900,dt.datetime.fromisoformat(cfg['provider_stop_utc'].replace('Z','+00:00')).timestamp()-1500)
with (ROOT/'qualification-v2-started').open('x') as f:f.write(cfg['instance'])
end=dt.datetime.fromtimestamp(deadline,dt.timezone.utc).isoformat()
def run(cmd,name,env=None,check=True):
 with (OUT/(name+'.log')).open('x') as log:
  child=subprocess.Popen(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
  try:rc=child.wait(timeout=max(1,deadline-time.time()))
  except BaseException:
   os.killpg(child.pid,signal.SIGTERM)
   try:child.wait(timeout=20)
   except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
   raise
  if check and rc:raise RuntimeError(name+' failed '+str(rc))
  return rc

def sft(name,n,*,resume=None,signal_test=False,env=None,check=True):
 prefix=cfg['backup_prefix']+'/qualification-v2/'+('split' if name.startswith('split') else 'signal' if name.startswith('signal') else name)+'/checkpoints'
 cmd=[sys.executable,'-m','cloud_training.nano_sft','--manifest',str(P/'broad-manifest.json'),'--quality-contract',str(P/'broad-contract.json'),
      '--block-plan',str(ROOT/'reports/ganesh-conversation-pilot-v1/exposure-plan.json'),'--block-arm','broad','--stage','targeted',
      '--base',str(ROOT/'parent'),'--base-manifest-sha',cfg['parent_manifest_sha256'],'--ancestor',str(ROOT/'ancestor'),
      '--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha',cfg['tokenizer_sha256'],'--repo',str(ROOT/'nanochat-source'),
      '--output',str(OUT/name),'--batch-tokens','8192','--microbatch','1','--epochs','1','--seed','103','--lr-multiplier','.25',
      '--muon-kernel-mode','eager','--packing-buffer-size','1','--eval-every-updates','1','--eval-rows','128','--max-updates',str(n),
      '--deterministic','--checkpoint-reserve-seconds','120','--deadline-utc',end,'--backup-prefix',prefix]
 if resume:cmd+=['--resume',str(resume)]
 if signal_test:
  env=dict(os.environ,FAULT_SIGNAL_MARKER=str(OUT/'signal-marker.json'))
  cmd=[sys.executable,str(P/'signal_inject.py'),*cmd[3:]]
 return run(cmd,name,env,check)

def download(remote,destination):
 destination.mkdir()
 for name in ('payload.pt','metadata.json','manifest.json','COMMITTED'):
  run(['gcloud','storage','cp',remote+'/'+name,str(destination/name),'--quiet'],'readback-'+destination.name+'-'+name)
 validate_bundle(destination)

result={'status':'hold','check':'cuda_changed_path','runtime_sha256':cfg['runtime_sha256'],'instance':cfg['instance'],'pilot_started':False}
try:
 import torch
 import nanochat.flash_attention as attention
 if not torch.__version__.startswith('2.9.1') or torch.version.cuda!='12.9' or torch.cuda.device_count()!=1 or 'A100' not in torch.cuda.get_device_name(0) or attention.USE_FA3:raise ValueError('Wrong qualified runtime')
 if not 39*1024**3<torch.cuda.get_device_properties(0).total_memory<42*1024**3:raise ValueError('Wrong A100 class')
 for name,key in [('parent','parent_manifest_sha256'),('ancestor','ancestor_manifest_sha256')]:
  validate_bundle(ROOT/name)
  if sha256_file(ROOT/name/'manifest.json')!=cfg[key]:raise ValueError('Wrong parent ancestry')
 sft('continuous',2);sft('split_first',1)
 remote=json.loads((OUT/'split_first/progress.json').read_text())['last_checkpoint']['upload']['remote_prefix']
 download(remote,ROOT/'restored-step1');sft('split_resume',1,resume=ROOT/'restored-step1')
 result['restart']=compare_and_record(OUT/'continuous/step-00000002',OUT/'split_resume/step-00000002',OUT/'exact-restart.json')
 sft('signal_first',1,signal_test=True)
 marker=json.loads((OUT/'signal-marker.json').read_text())
 if not marker.get('partial_gradients_present') or not marker.get('live_post_rollback_saved'):raise ValueError('Signal did not exercise rollback')
 result['rollback']=compare_and_record(OUT/'signal_first/step-00000000',OUT/'signal_first/interrupted-live',OUT/'exact-rollback.json')
 remote=json.loads((OUT/'signal_first/progress.json').read_text())['last_checkpoint']['upload']['remote_prefix']
 download(remote,ROOT/'restored-step0');sft('signal_resume',1,resume=ROOT/'restored-step0')
 result['signal_resume']=compare_and_record(OUT/'split_first/step-00000001',OUT/'signal_resume/step-00000001',OUT/'exact-signal-resume.json')
 shim=ROOT/'fault-shim';shim.mkdir();shutil.copy(P/'upload_fault_shim.py',shim/'gcloud');(shim/'gcloud').chmod(0o700)
 token=shim/'invalid-token';token.write_text('invalid-qualification-test-token\n')
 env=dict(os.environ,PATH=str(shim)+os.pathsep+os.environ['PATH'],FAULT_REAL_GCLOUD=shutil.which('gcloud'),FAULT_TOKEN_FILE=str(token),FAULT_UPLOAD_MARKER=str(OUT/'upload-marker.json'),FAULT_ALLOWED_PREFIX=cfg['backup_prefix']+'/qualification-v2/upload_fault/checkpoints')
 if sft('upload_fault',1,env=env,check=False)==0:raise ValueError('Injected upload incorrectly succeeded')
 if not json.loads((OUT/'upload-marker.json').read_text()).get('payload_upload_intercepted'):raise ValueError('Upload fault not exercised')
 journal=json.loads((OUT/'upload_fault/retention-journal.json').read_text())
 if any(e['state']=='committed' for e in journal['entries']):raise ValueError('Failed upload committed')
 # Refuse restart from an uncommitted journal; do not overwrite or retry it.
 from cloud_training.nano_train import CloudJournal
 ident=json.loads((OUT/'upload_fault/step-00000000/metadata.json').read_text())['identity']
 try:CloudJournal(OUT/'upload_fault/retention-journal.json',campaign_prefix=cfg['backup_prefix']+'/qualification-v2/upload_fault/checkpoints',identity=ident,resume_step=0)
 except (ValueError,RuntimeError):pass
 else:raise ValueError('Failed upload journal permitted resume')
 result.update(status='pass',seconds=time.time()-start,upload_rejection=True)
except BaseException as e:result.update(error=repr(e),seconds=time.time()-start)
(OUT/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));raise SystemExit(0 if result['status']=='pass' else 2)
