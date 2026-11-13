"""Bounded base controller; original hash-pinned trainer stays unchanged."""
import datetime,hashlib,json,math,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path('/opt/ownbase-nano');OUT=ROOT/'results/budget50-v1';OUT.mkdir(parents=True,exist_ok=True)
c=json.loads((ROOT/'launch-config.json').read_text());budget=c['budget'];boot=time.time()-float(Path('/proc/uptime').read_text().split()[0]);prefix=c['run_prefix']
base_end=boot+budget['base_deadline_seconds_from_boot'];finish_end=boot+budget['backup_deadline_seconds_from_boot']
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def publish(phase,**extra):
 row=dict(phase=phase,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),elapsed_hours=(time.time()-boot)/3600,**extra);(OUT/'controller.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row),flush=True)
 subprocess.run(['gcloud','storage','cp',str(OUT/'controller.json'),prefix+'/controller.json','--quiet'],check=True,timeout=90)
def execute(argv,deadline,log):
 with log.open('w') as out:
  process=subprocess.Popen(argv,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
  while process.poll() is None:
   if time.time()>=deadline:
    os.killpg(process.pid,signal.SIGTERM)
    try:return process.wait(timeout=900)
    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait();raise TimeoutError('Child exceeded checkpoint reserve')
   time.sleep(10)
  return process.returncode
try:
 from cloud_training.nano_launch import stage,worker_argv
 from cloud_training.nano_checkpoint import validate_bundle
 from cloud_training.nano_retention import _read
 publish('staging_verified_inputs')
 campaign,parent=stage(c,ROOT,min(time.time()+2400,base_end-1800));validate_bundle(parent)
 assert json.loads((parent/'metadata.json').read_text())['step']==11445
 for name,expected in c['parent_receipt']['identity']['adapter_hashes'].items():assert sha(ROOT/'cloud_training'/name)==expected, name
 _read(ROOT/'seed-journal.json',c['backup_prefix'])
 initial=11445;previous_ce=2.6664920300245285;flat=0
 for milestone in [7_000_000_000,8_000_000_000,9_000_000_000,10_000_000_000]:
  if time.time()>base_end-1800:break
  step=json.loads((parent/'metadata.json').read_text())['step'];goal=math.ceil(milestone/524288)
  if goal<=step:continue
  run=OUT/f'base-{goal}';run.mkdir(exist_ok=False)
  cfg=dict(c,max_updates=goal-step)
  stage_end=min(base_end,time.time()+18000)
  args=worker_argv(cfg,ROOT,campaign,parent,run,stage_end)
  args+=['--checkpoint-reserve-seconds','900']
  publish('base_training',start_step=step,goal_step=goal,deadline_utc=datetime.datetime.fromtimestamp(base_end,datetime.timezone.utc).isoformat())
  rc=execute(args,stage_end-900,run/'worker.log')
  result=json.loads((run/'result.json').read_text()) if (run/'result.json').exists() else json.loads((run/'progress.json').read_text())
  if rc or not result.get('last_checkpoint'):raise RuntimeError(f'Base worker failed rc={rc}; inspect preserved logs')
  parent=Path(result['last_checkpoint']['path']);validate_bundle(parent)
  completed=json.loads((parent/'metadata.json').read_text())['step']
  publish('base_milestone_saved',step=completed,base_tokens=completed*524288,checkpoint=str(parent),result_file=str(run/'result.json'))
  # Manual review is also performed by the active root; scalar gate is conservative fallback.
  validation=result.get('validation',{})
  shards=validation.get('shards',[])
  if validation.get('complete') and shards:
   count=sum(v['target_tokens'] for v in shards)
   ce=sum(v['cross_entropy_nats']*v['target_tokens'] for v in shards)/count
   flat=flat+1 if previous_ce-ce<.002 else 0;previous_ce=ce
   publish('base_learning_gate',ce=ce,consecutive_flat_milestones=flat,step=completed)
   if flat>=2:publish('base_stopped_no_meaningful_loss_gain',ce=ce);break
  else:raise RuntimeError('Incomplete milestone validation; no automatic continuation')
  if completed<goal:break
 (OUT/'base-parent.json').write_text(json.dumps({'checkpoint':str(parent),'manifest_sha256':sha(parent/'manifest.json'),'base_tokens':json.loads((parent/'metadata.json').read_text())['step']*524288},indent=2)+'\n')
 publish('base_complete_awaiting_reviewed_sft_packet',parent=str(parent))
 # Only a hash-bound, run-specific packet can dispatch subsequent training; no old commands.
 request_uri=prefix+'/approved-next-stage.json';wait_end=min(time.time()+300,boot+budget['final_training_deadline_seconds_from_boot']-1200)
 while time.time()<wait_end:
  probe=subprocess.run(['gcloud','storage','cp',request_uri,str(OUT/'next-stage.json'),'--quiet'],capture_output=True,text=True,timeout=30)
  if probe.returncode==0:
   packet=json.loads((OUT/'next-stage.json').read_text());assert packet['run_id']==c['run_id'] and packet['base_manifest_sha256']==sha(parent/'manifest.json')
   script=OUT/'next-stage.py';subprocess.run(['gcloud','storage','cp',packet['script_uri'],str(script),'--quiet'],check=True,timeout=60);assert sha(script)==packet['script_sha256']
   publish('reviewed_sft_stage_starting');rc=execute([sys.executable,'-u',str(script)],boot+budget['final_training_deadline_seconds_from_boot']-900,OUT/'next-stage.log');assert rc==0;break
  time.sleep(20)
except BaseException as e:
 (OUT/'failure.json').write_text(json.dumps({'type':type(e).__name__,'message':str(e),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n');print('Controller failure:',str(e),flush=True)
finally:
 # Immutable inputs are already in GCS; preserve ALL new results, logs and source evidence.
 backup_ok=False
 while time.time()<finish_end-120:
  try:
   publish('final_backup')
   subprocess.run(['gcloud','storage','rsync','--recursive',str(OUT),prefix+'/results','--quiet'],check=True,timeout=min(1200,finish_end-time.time()-60))
   inventory=[]
   for file in OUT.rglob('*'):
    if file.is_file():inventory.append({'path':str(file.relative_to(OUT)),'bytes':file.stat().st_size,'sha256':sha(file)})
   (ROOT/'final-inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
   subprocess.run(['gcloud','storage','cp',str(ROOT/'final-inventory.json'),prefix+'/final-inventory.json','--quiet'],check=True,timeout=60)
   # Independent SHA readback of the last retained base bundle, not merely an upload receipt.
   if 'parent' in globals():
    dest=ROOT/'final-readback';dest.mkdir(exist_ok=True)
    remote=json.loads((OUT/'base-parent.json').read_text()) if (OUT/'base-parent.json').exists() else None
    if remote:
     rel=str(parent.relative_to(OUT))
     for name in ['payload.pt','metadata.json','manifest.json','COMMITTED']:
      subprocess.run(['gcloud','storage','cp',prefix+'/results/'+rel+'/'+name,str(dest/name),'--quiet'],check=True,timeout=min(600,finish_end-time.time()-30))
     assert validate_bundle(dest)==validate_bundle(parent)
   receipt={'status':'backup_verified','all_new_result_files':len(inventory),'inventory_sha256':sha(ROOT/'final-inventory.json'),'base_readback_verified':bool('remote' in globals() and remote),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
   (ROOT/'backup-complete.json').write_text(json.dumps(receipt,indent=2)+'\n');subprocess.run(['gcloud','storage','cp',str(ROOT/'backup-complete.json'),prefix+'/backup-complete.json','--quiet'],check=True,timeout=60);backup_ok=True;break
  except Exception as e:print('Backup retry:',str(e),flush=True);time.sleep(20)
 if not backup_ok:print('BACKUP INCOMPLETE: preserve persistent disk; provider cap remains authoritative.',flush=True)
 sys.exit(0 if backup_ok and not (OUT/'failure.json').exists() else 2)
