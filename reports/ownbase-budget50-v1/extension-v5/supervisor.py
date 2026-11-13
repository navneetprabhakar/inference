"""User-directed base-only closeout; no SFT, no overlapping GPU writers."""
import datetime,fcntl,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path('/opt/ownbase-nano');OUT=ROOT/'results/budget50-v1';os.chdir(ROOT)
sys.path[:0]=[str(ROOT),str(ROOT/'vendor'),str(ROOT/'nanochat-source')]
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_launch import worker_argv
lock=(ROOT/'extension-v5.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
c=json.loads((ROOT/'launch-config.json').read_text());prefix=c['run_prefix']
boot=time.time()-float(Path('/proc/uptime').read_text().split()[0]);lease=json.loads((ROOT/'extension-budget.json').read_text());backup_end=boot+lease['duration_seconds']-180
sha=lambda p:hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def cp(a,b,timeout=120):subprocess.run(['gcloud','storage','cp',str(a),str(b),'--quiet'],check=True,timeout=timeout)
def publish(phase,**extra):
 row={'phase':phase,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'policy':'10B_then_check_then_SFT_then_check','authorized_cap_usd':55,'active_vm':'forge-ownbase-extension-v5',**extra}
 (OUT/'controller.json').write_text(json.dumps(row,indent=2)+'\n');cp(OUT/'controller.json',prefix+'/controller.json');print(json.dumps(row),flush=True)
def cmd(pid):return Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0',b' ').decode()
def live(pid):
 try:return Path(f'/proc/{pid}/stat').read_text().split(') ',1)[1].split()[0]!='Z'
 except FileNotFoundError:return False
SFT_SHA='b325bd8f4e1384498fa953119862224595614c30d193bb15563ce96b910f2893'
parent=None;failure=None
try:
 assert lease['prior_compute_hours']+lease['duration_seconds']/3600<=16
 assert lease['total_cap_usd']==55 and lease['duration_seconds']<=7200
 parent_info=json.loads((OUT/'base-parent.json').read_text());parent=Path(parent_info['checkpoint'])
 assert sha(parent/'manifest.json')==lease['base_manifest_sha256']==parent_info['manifest_sha256']
 validate_bundle(parent)
 base_step=json.loads((parent/'metadata.json').read_text())['step']
 assert 18834<=base_step<=19074,'Remainder too large for this bounded recovery lease'
 if base_step<19074:
  publish('base_training',start_step=base_step,goal_step=19074,progress_path='extension-base-final')
  dest=OUT/'extension-base-final';dest.mkdir(exist_ok=False)
  args=worker_argv(dict(c,max_updates=19074-base_step),ROOT,ROOT/'data/campaign.json',parent,dest,boot+1500)+['--checkpoint-reserve-seconds','300']
  with (dest/'worker.log').open('w') as log:
   child=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:rc=child.wait(timeout=max(1,boot+1560-time.time()))
   except subprocess.TimeoutExpired:
    os.killpg(child.pid,signal.SIGTERM)
    try:rc=child.wait(timeout=60)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait();raise RuntimeError('Base remainder exceeded reserved time')
  assert rc==0
  result=json.loads((dest/'result.json').read_text());parent=Path(result['last_checkpoint']['path']);validate_bundle(parent)
  assert json.loads((parent/'metadata.json').read_text())['step']==19074,'10B not completed; no misleading SFT comparison'
  (OUT/'base-parent.json').write_text(json.dumps({'checkpoint':str(parent),'manifest_sha256':sha(parent/'manifest.json'),'base_tokens':19074*524288,'goal_reached':True},indent=2)+'\n')
 assert not (OUT/'sft-stage').exists(),'Refuse duplicate SFT or evaluation overwrite'
 publish('precheck_sft_postcheck_starting',base_tokens=19074*524288,base_manifest_sha256=sha(parent/'manifest.json'))
 script=ROOT/'run-extension-sequence.py';assert sha(script)==SFT_SHA
 with (OUT/'next-stage.log').open('w') as log:
  child=subprocess.Popen([sys.executable,'-u',str(script)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  try:rc=child.wait(timeout=max(1,boot+lease['duration_seconds']-900-time.time()))
  except subprocess.TimeoutExpired:
   os.killpg(child.pid,signal.SIGTERM)
   try:rc=child.wait(timeout=60)
   except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait();raise RuntimeError('Sequence reached backup reserve')
 assert rc==0,f'Sequence exited{rc}'
 candidates=json.loads((OUT/'sft-stage/candidates.json').read_text())
 assert len(candidates)==1 and candidates[0]['independent_readback']
 assert candidates[0].get('assessment_exit_code')==0 and candidates[0].get('protected_exit_code')==0
 publish('checks_collected_pending_semantic_review',candidates=candidates,automatically_promoted=False)
except BaseException as e:
 failure={'type':type(e).__name__,'message':str(e)};(OUT/'extension-v5-failure.json').write_text(json.dumps(failure,indent=2)+'\n');print(failure,flush=True)
finally:
 ok=False
 while time.time()<backup_end-120:
  try:
   publish('final_backup',failure=failure)
   # Include operative config/source and bounded log snapshots in the inventory.
   evidence=OUT/'closeout-source';evidence.mkdir(exist_ok=True)
   for name in ['launch-config.json','run-budget50.py','finish-base-only.py','run-extension-supervisor.py','run-extension-sequence.py','extension-budget.json','server.log','seed-journal.json']:
    source=ROOT/name
    if source.exists(): (evidence/name).write_bytes(source.read_bytes())
   inventory=[{'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in OUT.rglob('*') if p.is_file()]
   subprocess.run(['gcloud','storage','rsync','--recursive',str(OUT),prefix+'/results','--quiet'],check=True,timeout=max(1,min(1200,backup_end-time.time()-90)))
   inv=ROOT/'final-inventory.json';inv.write_text(json.dumps(inventory,indent=2)+'\n');cp(inv,prefix+'/final-inventory.json')
   cp(prefix+'/final-inventory.json',ROOT/'final-inventory-readback.json');assert sha(inv)==sha(ROOT/'final-inventory-readback.json')
   assert parent is not None,'No final parent verified; preserve disk'
   readback=ROOT/'extension-final-readback';readback.mkdir(exist_ok=True);rel=str(parent.relative_to(OUT))
   for name in ['payload.pt','metadata.json','manifest.json','COMMITTED']:
    cp(prefix+'/results/'+rel+'/'+name,readback/name,timeout=max(1,min(600,backup_end-time.time()-30)))
    assert sha(readback/name)==sha(parent/name)
   validate_bundle(readback)
   receipt={'status':'backup_verified','all_new_result_files':len(inventory),'inventory_sha256':sha(inv),'base_readback_verified':True,'final_base_manifest_sha256':sha(parent/'manifest.json'),'base_tokens':json.loads((parent/'metadata.json').read_text())['step']*524288,'sft_candidates':json.loads((OUT/'sft-stage/candidates.json').read_text()) if (OUT/'sft-stage/candidates.json').exists() else [],'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'failure':failure}
   out=ROOT/'backup-complete.json';out.write_text(json.dumps(receipt,indent=2)+'\n');cp(out,prefix+'/backup-complete.json');ok=True;break
  except Exception as e:print('Backup retry',repr(e),flush=True);time.sleep(20)
 if ok:
  print('Backup verified; shutting down VM',flush=True);subprocess.run(['shutdown','-h','now'],check=True)
 else:print('Backup incomplete. Persistent disk retained; provider/guest guards remain authoritative.',flush=True)
