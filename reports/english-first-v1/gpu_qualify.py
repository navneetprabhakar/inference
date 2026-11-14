"""One bounded L4 qualification worker; never runs the64-update fit pilot."""
import datetime as dt,hashlib,json,os,signal,subprocess,sys,time,tarfile
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_restart_compare import compare_bundles
from cloud_training.nano_qualification_schedule import restart_branches,validate_restart_branches
ROOT=Path('/opt/english');OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
config=json.loads((ROOT/'config.json').read_text())
DEADLINE=dt.datetime.fromisoformat(config['deadline_utc'].replace('Z','+00:00')).timestamp()
REMOTE=config['backup_prefix'];BASE=ROOT/'base';PACKET=ROOT/'packet'
def remaining(reserve=0):
 value=DEADLINE-time.time()-reserve
 if value<=0:raise TimeoutError('Fixed lease exhausted')
 return value
def run(argv,log=None,reserve=900):
 with (OUT/(log or 'commands.log')).open('a') as f:
  p=subprocess.Popen(argv,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
  try:code=p.wait(timeout=remaining(reserve))
  except BaseException:
   os.killpg(p.pid,signal.SIGTERM)
   try:p.wait(timeout=20)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
   raise
  if code:raise RuntimeError('Command failed with exit'+str(code)+': '+str(argv[:4]))
def copy(src,dst,reserve=900):run(['gcloud','storage','cp',str(src),str(dst),'--quiet'],reserve=reserve)
def download_bundle(remote,destination,reserve=900):
 destination.mkdir()
 for name in ('payload.pt','metadata.json','manifest.json','COMMITTED'):copy(remote+'/'+name,destination/name,reserve)
 return validate_bundle(destination)
def sft(branch,*,resume=None):
 spec=restart_branches()[branch];name=branch
 argv=[sys.executable,'-m','cloud_training.nano_sft','--repo',str(ROOT/'nanochat-source'),
       '--base',str(BASE),'--base-manifest-sha',config['base_manifest_sha256'],
       '--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha',config['tokenizer_sha256'],
       '--manifest',str(PACKET/'diagnostic-manifest.json'),'--quality-contract',str(PACKET/'diagnostic-contract.json'),
       '--output',str(OUT/name),'--fit-diagnostic','--context-tokens','2048','--batch-tokens','8192',
       '--microbatch','1','--epochs','64','--max-updates',str(spec['max_updates']),'--lr-multiplier','.25',
       '--eval-every-updates',str(spec['eval_every_updates']),'--eval-rows','512',
       '--deterministic','--checkpoint-reserve-seconds','600','--deadline-utc',config['worker_deadline_utc'],
       '--backup-prefix',REMOTE+('/split' if branch.startswith('split') else '/uninterrupted')]
 if resume is not None:argv+=['--resume',str(resume)]
 run(argv,name+'.log')
 return OUT/name
result={'status':'running','quality_accepted':False,'pilot_started':False,'backup_verified':False}
try:
 import torch
 assert torch.__version__.startswith('2.9.1') and torch.version.cuda=='12.9'
 assert torch.cuda.device_count()==1 and 'L4' in torch.cuda.get_device_name(0)
 assert torch.cuda.is_bf16_supported()
 import nanochat.flash_attention as attention
 assert not attention.USE_FA3, 'This L4 qualification explicitly requires native SDPA'
 result['runtime']={'torch':torch.__version__,'cuda':torch.version.cuda,'gpu':torch.cuda.get_device_name(0),'attention':'sdpa'}
 validate_restart_branches(restart_branches())
 download_bundle(config['base_uri'],BASE)
 assert hashlib.sha256((BASE/'manifest.json').read_bytes()).hexdigest()==config['base_manifest_sha256']
 ref=sft('uninterrupted');first=sft('split_first')
 progress=json.loads((first/'progress.json').read_text());remote=progress['last_checkpoint']['upload']['remote_prefix']
 restored=ROOT/'restored-step1';download_bundle(remote,restored)
 resumed=sft('split_resume',resume=restored)
 comparison=compare_bundles(ref/'step-00000002',resumed/'step-00000002')
 result.update(status='restart_pass_pending_fault_drills' if comparison['status']=='pass' else 'hold_restart_mismatch',comparison=comparison,fresh_process_gcs_restore=True)
except BaseException as e:
 result.update(status='hold_worker_failure',error=repr(e))
finally:
 # Required surviving bundles are already uploaded by each SFT worker. Independently
 # read back every live receipt; never substitute a successful cp for hash validation.
 try:
  proofs=[]
  for journal in sorted(OUT.glob('*/retention-journal.json')):
   journal_data=json.loads(journal.read_text())
   if journal_data.get('lease_phase')!='ready':raise ValueError('Unfinished checkpoint operation; retain recovery disk')
   for entry in journal_data['entries']:
    if entry['state']!='committed':continue
    remote=entry['receipt']['remote_prefix'];dst=ROOT/('verify-'+str(len(proofs)))
    got=download_bundle(remote,dst,reserve=120)
    assert got==entry['receipt']['manifest']
    proofs.append({'remote_prefix':remote,'manifest_sha256':hashlib.sha256((dst/'manifest.json').read_bytes()).hexdigest(),'readback':True})
    import shutil;shutil.rmtree(dst)
  result['bundle_readbacks']=proofs;result['backup_verified']=True
 except BaseException as e:result.update(backup_verified=False,backup_error=repr(e))
 (OUT/'qualification.json').write_text(json.dumps(result,indent=2)+'\n')
 archive=ROOT/'evidence.tar.gz'
 with tarfile.open(archive,'w:gz') as tar:
  for p in OUT.rglob('*'):
   if p.is_file() and p.name!='payload.pt':tar.add(p,arcname='results/'+str(p.relative_to(OUT)))
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
