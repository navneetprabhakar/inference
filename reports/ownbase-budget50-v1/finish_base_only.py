"""User-directed base-only closeout; no SFT, no overlapping GPU writers."""
import datetime,fcntl,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path('/opt/ownbase-nano');OUT=ROOT/'results/budget50-v1';os.chdir(ROOT)
sys.path[:0]=[str(ROOT),str(ROOT/'vendor'),str(ROOT/'nanochat-source')]
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_launch import worker_argv
lock=(ROOT/'base-only-closeout.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
c=json.loads((ROOT/'launch-config.json').read_text());prefix=c['run_prefix']
boot=time.time()-float(Path('/proc/uptime').read_text().split()[0]);train_end=boot+48000;backup_end=boot+49200
sha=lambda p:hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def cp(a,b,timeout=120):subprocess.run(['gcloud','storage','cp',str(a),str(b),'--quiet'],check=True,timeout=timeout)
def publish(phase,**extra):
 row={'phase':phase,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'policy':'base_only_no_sft','authorized_cap_usd':55,**extra}
 (OUT/'controller.json').write_text(json.dumps(row,indent=2)+'\n');cp(OUT/'controller.json',prefix+'/controller.json');print(json.dumps(row),flush=True)
def cmd(pid):return Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode()
def live(pid):
 try:return Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()[0]!='Z'
 except FileNotFoundError:return False
parent=None;failure=None
try:
 assert 'run-budget50.py' in cmd(1791)
 assert 'cloud_training.nano_train' in cmd(166131) and 'base-19074' in cmd(166131)
 assert time.time()<train_end-3600
 # Suspend only controller, never the checkpoint-writing worker.
 os.kill(1791,signal.SIGSTOP)
 (OUT/'base-only-transition.json').write_text(json.dumps({'old_controller_pid':1791,'old_worker_pid':166131,'new_controller_pid':os.getpid(),'provider_stop_unchanged':50400,'training_deadline_from_boot':48000,'training_checkpoint_reserve':600,'backup_deadline_from_boot':49200,'sft_cancelled_by_user':True},indent=2)+'\n')
 publish('base_checkpointing_for_longer_window')
 os.kill(166131,signal.SIGTERM)
 until=min(time.time()+900,train_end-1800)
 while live(166131) and time.time()<until:time.sleep(5)
 assert not live(166131),'Old worker did not stop; do not start second writer'
 result=json.loads((OUT/'base-19074/result.json').read_text());parent=Path(result['last_checkpoint']['path']);validate_bundle(parent)
 meta=json.loads((parent/'metadata.json').read_text());assert meta['identity']==c['parent_receipt']['identity'];step=meta['step'];assert 17167<=step<=19074
 if step<19074:
  dest=OUT/'base-19074-closeout';dest.mkdir(exist_ok=False)
  args=worker_argv(dict(c,max_updates=19074-step),ROOT,ROOT/'data/campaign.json',parent,dest,train_end)+['--checkpoint-reserve-seconds','600']
  publish('base_training',start_step=step,goal_step=19074,progress_path='base-19074-closeout',deadline_utc=datetime.datetime.fromtimestamp(train_end,datetime.timezone.utc).isoformat())
  with (dest/'worker.log').open('w') as log:
   child=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:rc=child.wait(timeout=max(1,train_end-time.time()))
   except subprocess.TimeoutExpired:
    os.killpg(child.pid,signal.SIGTERM)
    try:rc=child.wait(timeout=120)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait();raise RuntimeError('Worker exceeded final checkpoint deadline')
  assert rc==0,f'Worker exited{rc}'
  result=json.loads((dest/'result.json').read_text());parent=Path(result['last_checkpoint']['path']);validate_bundle(parent)
 finalstep=json.loads((parent/'metadata.json').read_text())['step']
 (OUT/'base-parent.json').write_text(json.dumps({'checkpoint':str(parent),'manifest_sha256':sha(parent/'manifest.json'),'base_tokens':finalstep*524288,'goal_reached':finalstep==19074,'sft_trained':False},indent=2)+'\n')
 publish('base_complete_no_sft',step=finalstep,base_tokens=finalstep*524288,goal_reached=finalstep==19074)
except BaseException as e:
 failure={'type':type(e).__name__,'message':str(e)};(OUT/'base-only-failure.json').write_text(json.dumps(failure,indent=2)+'\n');print(failure,flush=True)
finally:
 ok=False
 while time.time()<backup_end-120:
  try:
   publish('final_backup',failure=failure)
   # Include operative config/source and bounded log snapshots in the inventory.
   evidence=OUT/'closeout-source';evidence.mkdir(exist_ok=True)
   for name in ['launch-config.json','run-budget50.py','finish-base-only.py','server.log','seed-journal.json']:
    source=ROOT/name
    if source.exists(): (evidence/name).write_bytes(source.read_bytes())
   inventory=[{'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in OUT.rglob('*') if p.is_file()]
   subprocess.run(['gcloud','storage','rsync','--recursive',str(OUT),prefix+'/results','--quiet'],check=True,timeout=max(1,min(1200,backup_end-time.time()-90)))
   inv=ROOT/'final-inventory.json';inv.write_text(json.dumps(inventory,indent=2)+'\n');cp(inv,prefix+'/final-inventory.json')
   cp(prefix+'/final-inventory.json',ROOT/'final-inventory-readback.json');assert sha(inv)==sha(ROOT/'final-inventory-readback.json')
   assert parent is not None,'No final parent verified; preserve disk'
   readback=ROOT/'base-only-final-readback';readback.mkdir(exist_ok=True);rel=str(parent.relative_to(OUT))
   for name in ['payload.pt','metadata.json','manifest.json','COMMITTED']:
    cp(prefix+'/results/'+rel+'/'+name,readback/name,timeout=max(1,min(600,backup_end-time.time()-30)))
    assert sha(readback/name)==sha(parent/name)
   validate_bundle(readback)
   receipt={'status':'backup_verified','all_new_result_files':len(inventory),'inventory_sha256':sha(inv),'base_readback_verified':True,'final_base_manifest_sha256':sha(parent/'manifest.json'),'base_tokens':json.loads((parent/'metadata.json').read_text())['step']*524288,'sft_trained':False,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'failure':failure}
   out=ROOT/'backup-complete.json';out.write_text(json.dumps(receipt,indent=2)+'\n');cp(out,prefix+'/backup-complete.json');ok=True;break
  except Exception as e:print('Backup retry',repr(e),flush=True);time.sleep(20)
 if ok:
  print('Backup verified; shutting down VM',flush=True);subprocess.run(['shutdown','-h','now'],check=True)
 else:print('Backup incomplete. Persistent disk retained; provider/guest guards remain authoritative.',flush=True)
