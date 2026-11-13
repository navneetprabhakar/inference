"""Prequalified bounded2K pilot after base. Never promotes weights automatically."""
import datetime,hashlib,json,os,signal,subprocess,sys,tarfile,time
from pathlib import Path
ROOT=Path('/opt/ownbase-nano');OUT=ROOT/'results/budget50-v1';HERE=OUT/'sft-stage';HERE.mkdir(exist_ok=False)
c=json.loads((ROOT/'launch-config.json').read_text());prefix=c['run_prefix'];boot=time.time()-float(Path('/proc/uptime').read_text().split()[0]);lease=json.loads((ROOT/'extension-budget.json').read_text());end=boot+lease['duration_seconds']-1200
sha=lambda p:hashlib.file_digest(Path(p).open('rb'),'sha256').hexdigest()
def cp(src,dst,timeout=180):subprocess.run(['gcloud','storage','cp',str(src),str(dst),'--quiet'],check=True,timeout=timeout)
def publish(phase,**kw):
 r={'phase':phase,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw};(HERE/'status.json').write_text(json.dumps(r,indent=2)+'\n');cp(HERE/'status.json',prefix+'/sft-status.json');print(json.dumps(r),flush=True)
def run(args,log,limit):
 with log.open('w') as out:
  p=subprocess.Popen(args,stdout=out,stderr=subprocess.STDOUT,start_new_session=True,env=env,cwd=code)
  try:return p.wait(timeout=max(1,min(limit,end-time.time())))
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGTERM)
   try:return p.wait(timeout=120)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait();return 124
CONFIG_SHA256 = '98aa00335f58a74d4d7c4e6082166a9e9d814728ac3eda8a7e014ef459b5b15c'  # Filled in the immutable dispatched copy by prepare_sft_packet.py.
cp(prefix+'/sft-packet-v2/config.json',HERE/'config.json');assert CONFIG_SHA256 and sha(HERE/'config.json')==CONFIG_SHA256
packet=json.loads((HERE/'config.json').read_text());assert packet['run_id']==c['run_id']
parent=json.loads((OUT/'base-parent.json').read_text());base=Path(parent['checkpoint']);assert sha(base/'manifest.json')==parent['manifest_sha256']
code=HERE/'code';code.mkdir();archive=HERE/'code.tar.gz';cp(packet['code_uri'],archive);assert sha(archive)==packet['code_sha256']
with tarfile.open(archive) as tar:
 for m in tar.getmembers():assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
 tar.extractall(code,filter='data')
for item in packet['files']:
 dest=HERE/item['path'];assert dest.resolve().is_relative_to(HERE.resolve());dest.parent.mkdir(parents=True,exist_ok=True);cp(item['uri'],dest);assert sha(dest)==item['sha256']
env=os.environ.copy();env['PYTHONPATH']=str(code)+':'+str(ROOT/'vendor')+':'+str(ROOT/'nanochat-source');env['NANOCHAT_DTYPE']='bfloat16'
sys.path.insert(0,str(code));from cloud_training.nano_checkpoint import validate_bundle
validate_bundle(base);candidates=[]
try:
 # User order: exact10B base -> matched assessment -> SFT -> same assessment.
 assert json.loads((base/'metadata.json').read_text())['step']==19074, '10B required before this SFT sequence'
 publish('pre_sft_assessment',base_manifest_sha256=sha(base/'manifest.json'))
 pre=HERE/'base10b-assessment.json'
 args=[sys.executable,str(code/'assessment.py'),'--checkpoint',str(base),'--tokenizer',str(ROOT/'tokenizer'),'--repo',str(ROOT/'nanochat-source'),'--suite',str(HERE/'assessment.json'),'--output',str(pre),'--device','cuda','--seconds','1800']
 rc=run(args,HERE/'base10b-assessment.log',1860)
 report=json.loads(pre.read_text())
 assert rc==0 and report['status']=='complete_requires_full_review' and len(report['records'])==180,'Pre-SFT check incomplete; do not silently skip order'
 args=[sys.executable,'-m','cloud_training.nano_quality','--repo',str(ROOT/'nanochat-source'),'--checkpoint',str(base),'--checkpoint-manifest-sha256',sha(base/'manifest.json'),'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha256',c['parent_receipt']['identity']['tokenizer_sha256'],'--suite',str(HERE/'protected.json'),'--output',str(HERE/'base10b-protected.json'),'--seconds','120','--reply-budget','128']
 rc=run(args,HERE/'base10b-protected-driver.log',150)
 assert rc==0,'Pre-SFT protected check incomplete'
 # The retained605 comparison arm is deferred; train the exact10B branch only.
 for recipe in packet['finite_recipes'][:1]:
  epochs=recipe['epochs']
  if time.time()>end-2400:publish('skipped_insufficient_reserved_time',epochs=epochs);break
  name=recipe['name'];dest=HERE/name;deadline=min(end-1920,time.time()+720)
  selected_base=base if recipe['stage']=='general' else ROOT/'retained-lineage/literal-state-repair-v1'
  selected_sha=sha(selected_base/'manifest.json')
  if recipe['stage']=='targeted':assert selected_sha==packet['retained_lineage']['items'][0]['manifest_sha256']
  ancestors=[] if recipe['stage']=='general' else [ROOT/'resume' if item['name']=='base6b' else ROOT/'retained-lineage'/item['name'] for item in packet['retained_lineage']['items'][1:]]
  if deadline-time.time()<420:break
  publish('training',recipe=name,base_manifest_sha256=selected_sha,finite_epochs=epochs,scope='Small fully reviewed2K corpus; diagnostic, not broadSFT or4K training')
  args=[sys.executable,'-m','cloud_training.nano_sft','--manifest',str(HERE/'data/manifest.json'),'--base',str(selected_base),'--base-manifest-sha',selected_sha,'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha',c['parent_receipt']['identity']['tokenizer_sha256'],'--repo',str(ROOT/'nanochat-source'),'--output',str(dest),'--stage',recipe['stage'],'--batch-tokens','8192','--microbatch','4','--epochs',str(epochs),'--lr-multiplier',str(recipe['lr_multiplier']),'--context-tokens','2048','--deterministic','--deterministic-attention','--kernel-path',str(ROOT/'kernel'),'--kernel-sha',c['kernel_sha256'],'--eval-rows','128','--eval-every-updates','50','--checkpoint-reserve-seconds','240','--backup-prefix',prefix+'/sft/'+name+'/checkpoints','--deadline-utc',datetime.datetime.fromtimestamp(deadline,datetime.timezone.utc).isoformat()]
  for ancestor in ancestors:args+=['--ancestor',str(ancestor)]
  rc=run(args,HERE/(name+'.log'),max(1,deadline-time.time()+30));resultfile=dest/'result.json'
  if rc or not resultfile.exists():publish('pilot_failed',recipe=name,exit_code=rc);break
  result=json.loads(resultfile.read_text());last=result.get('last_checkpoint');assert last
  checkpoint=Path(last['path']);validate_bundle(checkpoint);assert json.loads((checkpoint/'metadata.json').read_text())['step']>0
  # Verify GCS payload independently before evaluation or shutdown. All four files.
  readback=HERE/(name+'-readback');readback.mkdir()
  for file in ['payload.pt','metadata.json','manifest.json','COMMITTED']:cp(last['upload']['remote_prefix']+'/'+file,readback/file,timeout=300)
  assert validate_bundle(readback)==validate_bundle(checkpoint)
  candidates.append({'name':name,'checkpoint':str(checkpoint),'manifest_sha256':sha(checkpoint/'manifest.json'),'remote_prefix':last['upload']['remote_prefix'],'independent_readback':True,'training_status':result['status'],'trained_assistant_targets':result['assistant_targets'],'promotion':'pending_full_review'})
  (HERE/'candidates.json').write_text(json.dumps(candidates,indent=2)+'\n')
  # Readback is verified and can be discarded; primary local+GCS bundles remain.
  import shutil;shutil.rmtree(readback)
  if time.time()<end-240:
   args=[sys.executable,str(code/'assessment.py'),'--checkpoint',str(checkpoint),'--tokenizer',str(ROOT/'tokenizer'),'--repo',str(ROOT/'nanochat-source'),'--suite',str(HERE/'assessment.json'),'--output',str(HERE/(name+'-assessment.json')),'--device','cuda','--seconds',str(min(1800,int(end-time.time()-180)))]
   rc=run(args,HERE/(name+'-assessment.log'),min(1860,end-time.time()-120));candidates[-1]['assessment_exit_code']=rc
   post=json.loads((HERE/(name+'-assessment.json')).read_text())
   assert rc==0 and post['status']=='complete_requires_full_review' and len(post['records'])==180,'Post-SFT assessment incomplete'
  # Exposed18-tool regression, same raw decode settings as historical comparison.
  if time.time()<end-180:
   args=[sys.executable,'-m','cloud_training.nano_quality','--repo',str(ROOT/'nanochat-source'),'--checkpoint',str(checkpoint),'--checkpoint-manifest-sha256',sha(checkpoint/'manifest.json'),'--tokenizer',str(ROOT/'tokenizer'),'--tokenizer-sha256',c['parent_receipt']['identity']['tokenizer_sha256'],'--suite',str(HERE/'protected.json'),'--output',str(HERE/(name+'-protected.json')),'--seconds',str(min(120,int(end-time.time()-60))),'--reply-budget','128']
   rc=run(args,HERE/(name+'-protected-driver.log'),min(150,end-time.time()-30));candidates[-1]['protected_exit_code']=rc
   assert rc==0,'Post-SFT protected check incomplete'
  (HERE/'candidates.json').write_text(json.dumps(candidates,indent=2)+'\n')
 assert len(candidates)==1,'No SFT candidate completed'
 assert candidates[0].get('assessment_exit_code')==0 and candidates[0].get('protected_exit_code')==0,'Postchecks missing or incomplete'
except BaseException as e:
 (HERE/'failure.json').write_text(json.dumps({'type':type(e).__name__,'message':str(e)},indent=2)+'\n');raise
finally:
 (HERE/'candidates.json').write_text(json.dumps(candidates,indent=2)+'\n')
 # Base controller retries wholeOUT backup; this stage first backs up all new inputs/results.
 subprocess.run(['gcloud','storage','rsync','--recursive',str(HERE),prefix+'/sft-stage','--quiet'],check=True,timeout=600)
 publish('sft_finished_pending_review',candidates=candidates,automatically_promoted=False)
