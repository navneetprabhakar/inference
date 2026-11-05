"""Bounded, parallel GPU inference: 2500 total conversations, then stop for review."""
import collections,hashlib,importlib.metadata,json,os,signal,time,fcntl
from pathlib import Path
from author_conversations_local import SYSTEM,prompt_for,parse_dialogue,atomic,sha
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'data/author-only-v2';RUN=ROOT/'runs/local-author-v2';REPORT=ROOT/'reports/local-author-v2';STOP=False
SCHEMA=''' Output shape must be {"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}, extended with alternating role/content objects to the requested length. Never put bare strings in the messages list. Do not copy these ellipses.'''
def stop(*_):
 global STOP
 STOP=True

def normalize_envelope(text):
 """Lossless, logged transport normalization; never edits dialogue content."""
 try:o=json.loads(text)
 except ValueError:return text,None
 if isinstance(o,dict) and set(o)=={'messages'} and isinstance(o['messages'],list) and o['messages'] and all(isinstance(s,str) for s in o['messages']):
  o['messages']=[{'role':'user' if i%2==0 else 'assistant','content':s} for i,s in enumerate(o['messages'])]
  return json.dumps(o,ensure_ascii=False),'alternating_string_list_to_role_content'
 return text,None

def main():
 import mlx.core as mx
 from mlx_lm import load
 from mlx_lm.generate import BatchGenerator
 from mlx_lm.sample_utils import make_sampler
 from tokenizers import Tokenizer
 from train_local import health
 lock=(RUN/'.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
 cfg=json.loads((DATA/'config.json').read_text());tasks=json.loads((DATA/'scenario-plan.json').read_text());assert len(tasks)==2300 and cfg['target_total']==2500
 for n,h in cfg['input_hashes'].items():assert sha(DATA/n)==h
 assert sha(ROOT/'data/sft-v3/tokenizer.json')==cfg['tokenizer_sha256']
 modeldir=ROOT/cfg['teacher_local_path'];model_files={p.name:sha(p) for p in modeldir.iterdir() if p.is_file()}
 for w in json.loads((ROOT/'reports/local-author-v1/teacher-files.json').read_text())['weights']:assert model_files[w['name']]==w['sha256']
 assert 'chat_template.jinja' in model_files
 pins={'code':{n:sha(ROOT/'scripts'/n) for n in ['author_conversations_batched.py','author_conversations_local.py']},'config':sha(DATA/'config.json'),'model_files':model_files,'packages':{n:importlib.metadata.version(n) for n in ['mlx','mlx-lm','transformers','tokenizers']}}
 if (DATA/'pins.json').exists():assert json.loads((DATA/'pins.json').read_text())==pins
 else:atomic(DATA/'pins.json',pins)
 student=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'));seen=set();old=[json.loads(x) for x in (DATA/'existing-200.jsonl').read_text().splitlines()];assert len(old)==200
 for r in old:
  item,e=parse_dialogue(json.dumps({'messages':r['messages']}),len(r['messages']),student,seen);assert e is None;seen.add(item['content_sha256'])
 accepted={}
 for p in sorted((DATA/'accepted').glob('*.json')):
  r=json.loads(p.read_text());assert r['scenario']==tasks[r['slot']];item,e=parse_dialogue(json.dumps({'messages':r['messages']}),tasks[r['slot']]['turns'],student,seen);assert e is None;seen.add(item['content_sha256']);accepted[r['slot']]=r
 attempts=collections.Counter()
 for p in (DATA/'attempts').glob('*.json'):
  slot,att=map(int,p.stem.split('-'));attempts[slot]=max(attempts[slot],att+1)
 initial=health();mx.set_cache_limit(cfg['cache_limit_bytes']);start=time.time();startcount=len(accepted);lasthealth=0;lastbeat=0;batchtimes=[];rejections=collections.Counter()
 state={'pid':os.getpid(),'started_at':start,'target':2500,'existing_authored':200,'local_generated':len(accepted),'total_conversations':200+len(accepted),'training_started':False,'quality_review':'deferred','evaluation':'deferred','paid_api_calls':0,'cloud_spend_usd':0,'model':cfg['teacher_repo'],'phase':'batch_calibration'}
 calibration=json.loads((RUN/'calibration.json').read_text()) if (RUN/'calibration.json').exists() else []
 selected=json.loads((RUN/'selection.json').read_text())['batch_size'] if (RUN/'selection.json').exists() else None
 def snapshot(status,**kw):
  state.update(status=status,updated_at=time.time(),local_generated=len(accepted),total_conversations=200+len(accepted),rejections=dict(rejections),**kw)
  if batchtimes:
   seconds=sum(x[0] for x in batchtimes);count=sum(x[1] for x in batchtimes)
   if count:state['recent_seconds_per_saved_conversation']=seconds/count;state['remaining_active_seconds_estimate']=(2300-len(accepted))*seconds/count
  atomic(RUN/'status.json',state)
 def guards(force=False):
  nonlocal lasthealth
  if STOP or (RUN/'STOP').exists():raise InterruptedError('Stop requested')
  if not force and time.time()-lasthealth<10:return
  h=health();lasthealth=time.time();h['mlx_allocator_bytes']=mx.get_active_memory()+mx.get_cache_memory();state['health']=h
  if h['free_disk_bytes']<cfg['min_free_disk_bytes'] or h['mlx_allocator_bytes']>cfg['memory_limit_bytes'] or h['mlx_peak_bytes']>cfg['memory_limit_bytes'] or h['swap_used_mb']-initial['swap_used_mb']>cfg['swap_growth_limit_mb']:
   raise RuntimeError('resource_limit')
  while h['thermal_state']>=3:
   snapshot('paused_critical_thermal');time.sleep(10)
   if STOP or (RUN/'STOP').exists():raise InterruptedError('Stop requested')
   h=health();state['health']=h
 snapshot('loading_model');model,tok=load(str(modeldir),trust_remote_code=False);mx.set_cache_limit(cfg['cache_limit_bytes'])
 sampler=make_sampler(temp=.7,top_p=.8,top_k=20)
 while len(accepted)<2300:
  guards(True)
  # Test each requested batch size once using retained production candidates.
  if selected is None:
   tested={x['batch_size'] for x in calibration};pending=[b for b in cfg['calibration_batch_sizes'] if b not in tested]
   if pending:bs=pending[0]
   else:
    eligible=[x for x in calibration if x['memory_gib']<10 and x['saved']>0]
    assert eligible,'No safe batch size';best=min(eligible,key=lambda x:x['seconds_per_saved']);selected=best['batch_size'];atomic(RUN/'selection.json',{'batch_size':selected,'basis':'lowest measured seconds per mechanically admitted conversation; one production batch per size, not controlled quality evaluation','calibration':calibration});bs=selected
  else:bs=selected
  state['phase']='generation' if selected else 'batch_calibration'
  todo=[t for t in tasks if t['slot'] not in accepted and attempts[t['slot']]<20][:bs]
  if not todo:raise RuntimeError('Remaining slots exhausted attempts; no silent skips')
  seed=20261101+sum(attempts.values());mx.random.seed(seed);prompts=[];meta=[]
  for task in todo:
   att=attempts[task['slot']];p=prompt_for(task,att)+SCHEMA
   prompts.append(tok.apply_chat_template([{'role':'system','content':SYSTEM},{'role':'user','content':p}],tokenize=True,add_generation_prompt=True));meta.append((task,att,p))
  gen=BatchGenerator(model,stop_tokens=[[x] for x in tok.eos_token_ids],sampler=sampler,completion_batch_size=bs,prefill_batch_size=2,prefill_step_size=256)
  uids=gen.insert(prompts,max_tokens=[cfg['max_new_tokens']]*len(prompts));lookup=dict(zip(uids,meta));buffers={u:[] for u in uids};t0=time.time();saved=0;tokens=0
  snapshot('generating',batch_size=bs,batch_slots=[t['slot'] for t in todo],active_sequences=len(todo))
  try:
   while responses:=gen.next_generated():
    for resp in responses:
     if resp.finish_reason!='stop':buffers[resp.uid].append(resp.token);tokens+=1
     if resp.finish_reason is None:continue
     task,att,p=lookup[resp.uid];raw=tok.decode(buffers[resp.uid]);normalized,normalization=normalize_envelope(raw);item,reason=parse_dialogue(normalized,task['turns'],student,seen)
     if resp.finish_reason!='stop':reason='teacher_incomplete_length_stop'
     slot=task['slot'];attempts[slot]+=1
     atomic(DATA/'attempts'/f'{slot:05d}-{att:02d}.json',{'slot':slot,'attempt':att,'batch_seed':seed,'batch_slots':[t['slot'] for t in todo],'system_prompt':SYSTEM,'user_prompt':p,'raw_output':raw,'normalization':normalization,'finish_reason':resp.finish_reason,'mechanical_rejection':reason,'quality_review':'not_performed'})
     if reason:rejections[reason]+=1;continue
     r={'id':task['scenario_id'],'slot':slot,'scenario':task,**item,'provenance':{'method':'local_pretrained_model_generation','model':cfg['teacher_repo'],'revision':cfg['teacher_revision'],'runtime':'mlx-lm continuous batching','batch_size':bs,'batch_seed':seed,'batch_slots':[t['slot'] for t in todo],'attempt':att,'raw_attempt':f'attempts/{slot:05d}-{att:02d}.json','normalization':normalization,'synthetic':True,'paid_api':False,'not_directly_authored_by_chat_assistant':True},'review_status':'pending_after_generation','training_approved':False}
     atomic(DATA/'accepted'/f'{slot:05d}.json',r);accepted[slot]=r;seen.add(item['content_sha256']);saved+=1
    if time.time()-lastbeat>=5:guards();snapshot('generating',batch_generated_tokens=tokens);lastbeat=time.time()
  finally:gen.close()
  duration=time.time()-t0;memory=(mx.get_active_memory()+mx.get_cache_memory())/2**30
  entry={'batch_size':bs,'seconds':duration,'saved':saved,'seconds_per_saved':duration/saved if saved else None,'tokens':tokens,'memory_gib':memory,'peak_memory_gib':mx.get_peak_memory()/2**30}
  if selected is None:calibration.append(entry);atomic(RUN/'calibration.json',calibration)
  batchtimes.append((duration,saved));batchtimes=batchtimes[-20:];snapshot('generating');print(json.dumps({'total':200+len(accepted),**entry}),flush=True)
  mx.clear_cache()
 assert len(accepted)==2300
 final=[{**r,'review_status':'pending_after_generation','training_approved':False} for r in old]+[accepted[k] for k in sorted(accepted)]
 p=DATA/'conversations-2500.jsonl';temp=p.with_suffix('.tmp')
 with temp.open('w') as f:
  for r in final:f.write(json.dumps(r,ensure_ascii=False)+'\n')
  f.flush();os.fsync(f.fileno())
 os.replace(temp,p)
 assert {p.name:sha(p) for p in modeldir.iterdir() if p.is_file()}==model_files
 manifest={'status':'generation_complete_awaiting_review','conversations':2500,'chat_authored':200,'local_teacher_generated':2300,'curated_records':0,'corpus_sha256':sha(p),'training_allowed':False,'quality_review':'not_started','evaluation':'not_started','paid_api_calls':0,'teacher':cfg['teacher_repo'],'pins':pins}
 atomic(DATA/'manifest.json',manifest);atomic(REPORT/'completion.json',manifest);snapshot('generation_complete_awaiting_review');(RUN/'COMPLETE').write_text('2500 generated; stop for review. No training.\n')
if __name__=='__main__':
 try:main()
 except Exception as e:
  p=RUN/'status.json';s=json.loads(p.read_text()) if p.exists() else {};s.update(status='stopped' if isinstance(e,InterruptedError) else 'failed',error=type(e).__name__+': '+str(e),updated_at=time.time());atomic(p,s);raise
