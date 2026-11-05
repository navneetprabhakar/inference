"""Generate an author-only 10,000-dialogue corpus locally; never train or evaluate.

200 existing assistant-authored + 9,800 pretrained-teacher generations. Only
mechanical admission checks run before completion. Raw attempts are preserved.
Resume uses atomic per-slot records and pinned configuration, inputs and model.
"""
import argparse, collections, fcntl, hashlib, importlib.metadata, json, os, signal, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONFIG=ROOT/'configs/local_author_v1.json'
DATA=ROOT/'data/author-only-v1'
RUN=ROOT/'runs/local-author-v1'
REPORT=ROOT/'reports/local-author-v1'
STOP=False
SYSTEM='''You write original synthetic English conversations for an ordinary text assistant.
Return only one JSON object with exactly one key, "messages", containing a list of
objects with exactly "role" and "content". Alternate user and assistant, beginning
with user and ending with assistant. Follow the requested number of messages.
Write a fresh, natural exchange, not an instruction about creating a dataset.
User turns should sound like real requests, with concrete details where useful.
Later user turns should meaningfully follow up, correct, or refine the earlier turn.
Assistant answers should be useful, direct, and usually 1-3 short sentences.
Keep the whole conversation under 180 English words. Do not pad with greetings,
repeated thanks, praise, filler, or repeated offers to help. Vary phrasing naturally.
Do not invent assistant personal experiences, live information, access to files,
completed actions, or tool results. There are no tools in these conversations.
Keep factual explanations elementary and stable. Avoid medical, financial, legal,
sexual or dangerous advice. Do not use private real people, URLs or product pitches.
For an editing request preserve the supplied meaning. For missing information ask
briefly, and have the user supply it later if the dialogue length allows. Do not
force clarification when the request is already answerable. Do not use code fences,
role tags, analysis, or commentary outside the JSON. A scenario is guidance, not
text to copy verbatim. Never include the scenario ID or variation seed in dialogue.'''

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def atomic(path,obj):
 path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(tmp,path)
def stop(*_):
 global STOP
 STOP=True

def prompt_for(task,attempt):
 return (f'Author one new conversation with exactly {task["turns"]} messages.\n'
         f'Category: {task["category"]}. Topic: {task["topic"]}.\n'
         f'Optional setting: {task["setting"]}. Style: {task["style"]}.\n'
         f'Dialogue direction: {task["angle"] if task["turns"]>2 else "Use a self-contained user request and a direct useful answer."}\n'
         f'Use distinct concrete details and wording for variation seed {task["variation_seed"]+attempt}. '
         'The setting is optional: keep it coherent with the topic. '
         'Write JSON now; no introductory explanation.')

def parse_dialogue(text,turns,tokenizer,seen):
 try:obj=json.loads(text)
 except (ValueError,TypeError):return None,'invalid_json'
 if not isinstance(obj,dict) or set(obj)!={'messages'}:return None,'invalid_top_level'
 ms=obj['messages']
 if not isinstance(ms,list) or len(ms)!=turns:return None,'wrong_turn_count'
 parts=[]
 for i,m in enumerate(ms):
  if not isinstance(m,dict) or set(m)!={'role','content'}:return None,'invalid_message_fields'
  role='user' if i%2==0 else 'assistant'
  if m['role']!=role or not isinstance(m['content'],str) or not m['content'].strip():return None,'invalid_roles_or_empty'
  if any(x in m['content'] for x in ['<|user|>','<|assistant|>','<|system|>','<|tool_call|>','<|endoftext|>']):return None,'embedded_protocol_token'
  parts.append('<|'+role+'|>'+m['content']+('<|endoftext|>' if role=='assistant' else '\n'))
 n=len(tokenizer.encode(''.join(parts)).ids)
 if n>513:return None,'student_context_overflow'
 canonical=json.dumps([{'role':m['role'],'content':' '.join(m['content'].casefold().split())} for m in ms],sort_keys=True,ensure_ascii=False)
 key=hashlib.sha256(canonical.encode()).hexdigest()
 if key in seen:return None,'exact_duplicate'
 return {'messages':ms,'student_tokens':n,'content_sha256':key},None

def main(args):
 import mlx.core as mx
 from mlx_lm import load,stream_generate
 from mlx_lm.sample_utils import make_sampler
 from tokenizers import Tokenizer
 from train_local import health
 RUN.mkdir(exist_ok=True);DATA.mkdir(exist_ok=True);REPORT.mkdir(exist_ok=True)
 lock=(RUN/'.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 cfg=json.loads(CONFIG.read_text());tasks=json.loads((DATA/'scenario-plan.json').read_text())
 assert cfg['training_allowed'] is False and cfg['paid_apis_allowed'] is False
 for name,h in cfg['input_hashes'].items():assert sha(DATA/name)==h,name
 tokfile=ROOT/'data/sft-v3/tokenizer.json';assert sha(tokfile)==cfg['tokenizer_sha256']
 student=Tokenizer.from_file(str(tokfile));modeldir=ROOT/cfg['teacher_local_path']
 download=json.loads((RUN/'download.json').read_text());assert download['status']=='downloaded' and download['revision']==cfg['teacher_revision']
 model_files={p.name:sha(p) for p in sorted(modeldir.iterdir()) if p.is_file()}
 assert any(n.endswith('.safetensors') for n in model_files)
 expected=json.loads((REPORT/'teacher-files.json').read_text())
 for w in expected['weights']:assert model_files[w['name']]==w['sha256'], 'Teacher hash differs from publisher'
 pins={'script_sha256':sha(__file__),'config_sha256':sha(CONFIG),'model_files':model_files,'input_hashes':cfg['input_hashes'],'packages':{x:importlib.metadata.version(x) for x in ['mlx','mlx-lm','transformers','tokenizers']}}
 if (DATA/'pins.json').exists():assert json.loads((DATA/'pins.json').read_text())==pins,'Pinned generation environment changed'
 else:atomic(DATA/'pins.json',pins)
 for name in ['accepted','attempts']:(DATA/name).mkdir(exist_ok=True)
 old=[json.loads(x) for x in (DATA/'existing-200.jsonl').read_text().splitlines()];assert len(old)==200
 seen=set()
 for r in old:
  item,reason=parse_dialogue(json.dumps({'messages':r['messages']}),len(r['messages']),student,seen);assert reason is None,(r['id'],reason);seen.add(item['content_sha256'])
 accepted={}
 for f in sorted((DATA/'accepted').glob('*.json')):
  r=json.loads(f.read_text());slot=r['slot'];assert slot not in accepted and r['scenario']==tasks[slot]
  item,reason=parse_dialogue(json.dumps({'messages':r['messages']}),tasks[slot]['turns'],student,seen);assert reason is None,(f,reason)
  assert item['content_sha256']==r['content_sha256'];seen.add(item['content_sha256']);accepted[slot]=r
 if (RUN/'status.json').exists():
  prior=json.loads((RUN/'status.json').read_text())
  if not args.resume:raise RuntimeError('Existing job: use --resume after inspection')
 else:prior={}
 initial=health();mx.set_cache_limit(cfg['cache_limit_bytes']);start=time.time();session_count=len(accepted);recent=[];rejects=collections.Counter();last_health=0
 state={'pid':os.getpid(),'status':'loading_model','started_at':prior.get('started_at',start),'session_started_at':start,'existing_authored':200,'local_generated':len(accepted),'total_conversations':200+len(accepted),'target':10000,'teacher':cfg['teacher_repo'],'revision':cfg['teacher_revision'],'training_started':False,'quality_review':'deferred','evaluation':'deferred','paid_api_calls':0,'cloud_spend_usd':0,'battery_policy':'continue_on_battery'}
 def snapshot(status,**kwargs):
  state.update(status=status,updated_at=time.time(),local_generated=len(accepted),total_conversations=200+len(accepted),session_rejections=dict(rejects),**kwargs)
  if recent:state['recent_seconds_per_conversation']=sum(recent)/len(recent);state['estimated_remaining_active_seconds']=(9800-len(accepted))*sum(recent)/len(recent)
  atomic(RUN/'status.json',state)
 def guards(force=False):
  nonlocal last_health
  if STOP or (RUN/'STOP').exists():snapshot('stopped');raise InterruptedError('Stop requested')
  if not force and time.time()-last_health<15:return
  h=health();last_health=time.time();h.update(mlx_active_bytes=mx.get_active_memory(),mlx_cache_bytes=mx.get_cache_memory());state['health']=h
  if h['free_disk_bytes']<cfg['min_free_disk_bytes'] or h['mlx_peak_bytes']>cfg['memory_limit_bytes'] or h['mlx_active_bytes']+h['mlx_cache_bytes']>cfg['memory_limit_bytes'] or h['swap_used_mb']-initial['swap_used_mb']>cfg['swap_growth_limit_mb']:
   snapshot('stopped_resource_limit');raise RuntimeError('Resource guard reached; inspect before resuming')
  while h['thermal_state']>=3:
   snapshot('paused_critical_thermal');time.sleep(10)
   if STOP or (RUN/'STOP').exists():raise InterruptedError('Stop requested')
   h=health();state['health']=h
 snapshot('loading_model')
 model,teacher=load(str(modeldir),tokenizer_config={'trust_remote_code':False},trust_remote_code=False)
 mx.set_cache_limit(cfg['cache_limit_bytes'])
 sampler=make_sampler(temp=cfg['sampling']['temperature'],top_p=cfg['sampling']['top_p'],top_k=cfg['sampling']['top_k'])
 snapshot('generating')
 for task in tasks:
  slot=task['slot']
  if slot in accepted:continue
  guards(True);taskstart=time.time()
  files=sorted((DATA/'attempts').glob(f'{slot:05d}-*.json'));attempt_start=max([int(f.stem.split('-')[1]) for f in files],default=-1)+1
  for attempt in range(attempt_start,cfg['attempts_per_slot']):
   guards();seed=(task['variation_seed']+attempt)%2**32;mx.random.seed(seed)
   prompt=prompt_for(task,attempt);chat=[{'role':'system','content':SYSTEM},{'role':'user','content':prompt}]
   rendered=teacher.apply_chat_template(chat,tokenize=False,add_generation_prompt=True)
   snapshot('generating',slot=slot,attempt=attempt,current_category=task['category'],current_generated_tokens=0)
   text='';last=None;t0=time.time()
   for response in stream_generate(model,teacher,rendered,max_tokens=cfg['max_new_tokens'],sampler=sampler):
    last=response;text+=response.text
    if response.generation_tokens%32==0:
     guards();snapshot('generating',current_generated_tokens=response.generation_tokens,current_generation_tps=response.generation_tps)
   assert last is not None
   item,reason=parse_dialogue(text,task['turns'],student,seen)
   if last.finish_reason!='stop':reason='teacher_incomplete_length_stop'
   raw={'slot':slot,'attempt':attempt,'seed':seed,'system_prompt':SYSTEM,'user_prompt':prompt,'raw_output':text,'mechanical_rejection':reason,'finish_reason':last.finish_reason,'teacher_generated_tokens':last.generation_tokens,'teacher_generation_tps':last.generation_tps,'elapsed_seconds':time.time()-t0,'quality_review':'not_performed'}
   atomic(DATA/'attempts'/f'{slot:05d}-{attempt:02d}.json',raw)
   if reason:rejects[reason]+=1;snapshot('generating');continue
   record={'id':task['scenario_id'],'slot':slot,'scenario':task,**item,'provenance':{'method':'local_pretrained_model_generation','model':cfg['teacher_repo'],'revision':cfg['teacher_revision'],'quantization':'4bit community MLX conversion','runtime':'mlx-lm','seed':seed,'attempt':attempt,'raw_attempt':f'attempts/{slot:05d}-{attempt:02d}.json','paid_api':False,'synthetic':True,'not_directly_authored_by_chat_assistant':True},'review_status':'pending_after_generation','training_approved':False}
   atomic(DATA/'accepted'/f'{slot:05d}.json',record);accepted[slot]=record;seen.add(item['content_sha256']);recent.append(time.time()-taskstart);recent=recent[-30:]
   snapshot('generating');print(json.dumps({'total':200+len(accepted),'local':len(accepted),'slot':slot,'tokens':last.generation_tokens,'tps':round(last.generation_tps,2),'seconds':round(recent[-1],2),'memory_gib':round((mx.get_active_memory()+mx.get_cache_memory())/2**30,2)}),flush=True)
   break
  else:
   snapshot('stopped_attempt_limit',failed_slot=slot);raise RuntimeError(f'Slot {slot} exhausted mechanical retries; no silent skip')
  if args.session_limit and len(accepted)-session_count>=args.session_limit:
   snapshot('session_limit_reached');return
 assert len(accepted)==9800
 final=[]
 for r in old:final.append({**r,'provenance':{**r['provenance'],'origin':'assistant_authored_in_chat_before_local_generation'},'review_status':'pending_after_generation','training_approved':False})
 final.extend(accepted[k] for k in sorted(accepted));assert len(final)==10000
 temp=DATA/'conversations-10000.jsonl.tmp'
 with temp.open('w') as f:
  for r in final:f.write(json.dumps(r,ensure_ascii=False)+'\n')
  f.flush();os.fsync(f.fileno())
 os.replace(temp,DATA/'conversations-10000.jsonl')
 assert {p.name:sha(p) for p in modeldir.iterdir() if p.is_file()}==model_files,'Teacher files changed'
 manifest={'status':'generation_complete_awaiting_review','conversations':10000,'chat_assistant_authored':200,'local_teacher_generated':9800,'curated_source_records':0,'teacher':cfg['teacher_repo'],'revision':cfg['teacher_revision'],'corpus_sha256':sha(DATA/'conversations-10000.jsonl'),'pins':pins,'quality_review':'not_started','evaluation':'not_started','training_allowed':False,'paid_api_calls':0,'cloud_spend_usd':0,'limitations':['Mechanical validation is not quality review.','Generated facts, diversity, repetition and semantic contamination remain unassessed.','Scenario plans vary automatically; final message texts are generated by the local teacher.']}
 atomic(DATA/'manifest.json',manifest);atomic(REPORT/'completion.json',manifest);snapshot('generation_complete_awaiting_review',corpus_sha256=manifest['corpus_sha256']);(RUN/'COMPLETE').write_text('Generation complete. Review/evaluation may now be planned; no training.\n')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--resume',action='store_true');p.add_argument('--session-limit',type=int,default=0);args=p.parse_args()
 try:main(args)
 except Exception as e:
  path=RUN/'status.json'
  if path.exists():
   s=json.loads(path.read_text());s.update(error=type(e).__name__+': '+str(e),updated_at=time.time())
   if s.get('status') not in ['stopped','stopped_resource_limit','stopped_attempt_limit']:s['status']='stopped' if isinstance(e,InterruptedError) else 'failed'
   atomic(path,s)
  raise
