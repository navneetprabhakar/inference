"""Owner-requested 1000 additional GPT-6 Sol conversations. Four bounded CLI workers; no student backend."""
import concurrent.futures,hashlib,importlib.util,json,os,random,re,signal,subprocess,sys,threading,time
from collections import Counter,defaultdict
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from slm.teacher.cli import OVERRIDES,clean_environment
from slm.teacher.sol import parse_sol_events
from jsonschema import Draft202012Validator
from sentencepiece import SentencePieceProcessor
spec=importlib.util.spec_from_file_location('previous_generation',PROJECT/'restart/sol-conversation-data-v1/generate.py');prev=importlib.util.module_from_spec(spec);spec.loader.exec_module(prev)
EXE=prev.EXE;MODEL='gpt-6-sol';WORKERS=4
SCENES={
 'train':['shared apartment','cycling club','small fictional bakery','animal-shelter supplies','home office','local sports club','amateur theatre','music practice','fictional weekend rail trip','repair cafe'],
 'development':['community museum','textile archive','stargazing group','fictional ferry terminal','pottery inventory','costume store','school newspaper','walking map','shared allotment','exhibition reception'],
 'test':['toy warehouse','board-game collection','fictional mountain lodge','school-play costumes','camp equipment store','model railway exhibit','community orchard','fictional island timetable','postcard collection','aquarium visitor desk']}
LENSES=['simple initial request followed by a meaningful clarification','revision after an explicit correction or changed constraint','two relevant constraints and a follow-up that tests retention','an unusual but ordinary practical situation, not a stock template','a natural conversational misunderstanding that is resolved using supplied evidence']
lock=threading.RLock();stop=threading.Event();usage=Counter();start_epoch=None;attempts=0;completed=0

def save(path,obj):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n');tmp.replace(path)
def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def guard():
 if stop.is_set():raise RuntimeError('Peer failure or termination: stop all workers')
 if time.time()-start_epoch>=3600:raise TimeoutError('Aggregate 60-minute cap')
 if __import__('shutil').disk_usage(ROOT).free<60*1024**3:raise RuntimeError('60 GiB disk floor')
def call(name,prompt,schema):
 global attempts,completed
 guard()
 with lock:
  assert attempts<100,'Request cap';attempts+=1
 folder=ROOT/'private'/name;folder.mkdir(parents=True,exist_ok=False)
 save(folder/'schema.json',schema);(folder/'prompt.txt').write_text(prompt)
 argv=[EXE,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--cd',str(folder),'--model',MODEL,'--json','--color','never','--output-schema',str(folder/'schema.json'),'--output-last-message',str(folder/'answer.json')]
 controls={k:v for k,v in OVERRIDES.items() if k!='tools.view_image'};controls['model_reasoning_effort']='medium'
 for k,v in controls.items():argv+=['-c',k+'='+json.dumps(v)]
 argv+=['-'];save(folder/'started.json',dict(requested_model=MODEL,prompt_sha256=sha(folder/'prompt.txt'),epoch=time.time(),argv=argv))
 started=time.monotonic()
 with (folder/'events.jsonl').open('xb') as out,(folder/'stderr.txt').open('x') as err,(folder/'prompt.txt').open('rb') as inp:
  proc=subprocess.Popen(argv,env=clean_environment(),stdin=inp,stdout=out,stderr=err,start_new_session=True)
  try:
   while proc.poll() is None:
    guard()
    if time.monotonic()-started>=240:raise TimeoutError('Per-request 240-second cap')
    if (folder/'events.jsonl').stat().st_size>4*1024**2 or (folder/'stderr.txt').stat().st_size>131072:raise ValueError('Log byte cap')
    if (folder/'answer.json').exists() and (folder/'answer.json').stat().st_size>262144:raise ValueError('Answer byte cap')
    time.sleep(.25)
  finally:
   if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   save(folder/'terminal.json',dict(returncode=proc.returncode,reaped=True,seconds=time.monotonic()-started))
 if proc.returncode:raise RuntimeError('Teacher failed; no retry/model fallback')
 raw=parse_sol_events((folder/'events.jsonl').read_text(),(folder/'answer.json').read_text(),SimpleNamespace(model_id=MODEL,max_response_bytes=262144,observed_output_token_limit=20000))
 answer=read(folder/'answer.json');Draft202012Validator(schema).validate(answer)
 save(folder/'receipt.json',dict(requested_model=MODEL,resolved_model=None,usage=raw['usage'],tools_used=False,answer_sha256=sha(folder/'answer.json')))
 with lock:
  usage.update(raw['usage']);completed+=1
  assert usage['output_tokens']+usage['reasoning_output_tokens']<=750000,'Aggregate observed output cap'
  assert usage['input_tokens']<=3000000,'Aggregate observed input cap'
  save(ROOT/'progress.json',dict(requests_started=attempts,requests_completed=completed,generated_conversations=20*sum(1 for p in (ROOT/'private').glob('generate-*/receipt.json')),reviewed_conversations=20*sum(1 for p in (ROOT/'private').glob('review-*/receipt.json')),elapsed_seconds=time.time()-start_epoch,usage=dict(usage),student_updates=0))
  print(json.dumps(dict(event='complete',name=name,requests=completed,elapsed_seconds=round(time.time()-start_epoch))),flush=True)
 return answer

def parallel(jobs,fn):
 results={}
 with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as pool:
  futures={pool.submit(fn,j):j for j in jobs}
  try:
   for future in concurrent.futures.as_completed(futures):
    results[futures[future]]=future.result()
  except BaseException:
   stop.set()
   for f in futures:f.cancel()
   raise
 return results

def prepare():
 assignments=[]
 for family,(name,brief) in enumerate(prev.FAMILIES):
  split=prev.SPLITS[family]
  for scene_index,scene in enumerate(SCENES[split]):
   for variant,lens in enumerate(LENSES):
    assignments.append(dict(id=f'sol1000-{family:02d}-{scene_index:02d}-{variant}',family=name,split=split,scene=scene,lens=lens,brief=brief))
 # Keep review/generation packets within a split. Split-family convention matches the previous batch.
 ordered=[r for split in ['train','development','test'] for r in assignments if r['split']==split]
 assert len(ordered)==1000 and Counter(r['split'] for r in ordered)==dict(train=800,development=100,test=100)
 save(ROOT/'private/assignments.json',ordered)
 rng=random.Random(24100061);sample=[]
 for family in [f[0] for f in prev.FAMILIES]:sample+=rng.sample([r['id'] for r in ordered if r['family']==family],2)
 sample+=rng.sample([r['id'] for r in ordered if r['id'] not in sample],10)
 save(ROOT/'plan.json',dict(owner_instruction='generate 1000',requested_model=MODEL,new_conversations=1000,train=800,development=100,test=100,parallel_cli_workers=4,generation_requests=50,review_requests=50,automatic_retries=0,wall_seconds_max=3600,per_request_seconds_max=240,observed_output_plus_reasoning_cap=750000,observed_input_cap=3000000,provider_side_generation_limit=False,student_training=False,primary_sample_ids=sample,split_policy='Same task families reserved as previous 100; scene lists also disjoint between splits. New synthetic holdouts, not independent benchmarks.',review_policy='All 1000 separately reviewed by same requested Sol model; primary directly reviews frozen 50-example sample. No guarantee 1000 survive quality checks.',tool_scope='Tool honesty and interpretation of user-supplied fictional tool results only; no actual tool-call traces.',source_sha256=sha(__file__),inherited_curriculum_sha256=sha(PROJECT/'restart/sol-conversation-data-v1/generate.py'),assignments_sha256=sha(ROOT/'private/assignments.json')))
 return ordered

def main():
 global start_epoch
 signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('Terminated')))
 if (ROOT/'started.json').exists():raise RuntimeError('No rerun or allowance reset')
 version=subprocess.run([EXE,'--version'],capture_output=True,text=True,check=True,timeout=10).stdout.strip();assert version=='codex-cli 0.163.0-alpha.11.2'
 login=subprocess.run([EXE,'login','status'],env=clean_environment(),capture_output=True,text=True,check=True,timeout=10);assert (login.stdout+login.stderr).strip()=='Logged in using ChatGPT'
 assignments=prepare();start_epoch=time.time();save(ROOT/'started.json',dict(epoch=start_epoch,client=version,pid=os.getpid()))
 msg=dict(type='object',properties=dict(role=dict(type='string',enum=['user','assistant']),content=dict(type='string',minLength=1,maxLength=1600)),required=['role','content'],additionalProperties=False)
 conv=dict(type='array',items=msg,minItems=4,maxItems=6)
 def generate(batch):
  rows=assignments[batch*20:batch*20+20]
  schema=dict(type='object',properties={r['id']:conv for r in rows},required=[r['id'] for r in rows],additionalProperties=False)
  prompt=('Generate 20 original English conversation demonstrations for a small student. Return exact assigned IDs. Each conversation has 2 or 3 alternating user/assistant pairs. Each assistant reply normally 8-30 words; target whole conversation 70-130 words, concise enough for a small context window. Give substantive answers, not empty acknowledgements. Each assignment supplies a scene, skill and variation lens; make genuinely different problems, not name/number swaps. All needed fictional notes, numbers, rules and quoted source text must appear in USER messages. Never refer to missing documents. Keep arithmetic, spelling, entities, causal order and requested exact formats correct. Do not introduce unsupported details such as p.m. when only 4 is supplied, or infer unspecified checklist status. For physical instructions include every necessary step, or choose a simpler activity. Basic explanations may use stable elementary facts. No copyrighted quotations, personal data, current factual claims, medical/legal/financial advice, hidden chain of thought or generic AI disclaimers. Assistant has NO tools: no bookings/messages/file changes can actually occur. Tool results are only fictional text supplied by the user; never claim execution. No system/tool role messages or actual tool-call traces. Do not repeatedly default to libraries, seed swaps or craft workshops; follow the assigned scene. Generate content only. Do not use shell, files, browsing, MCP, agents or tools.\nASSIGNMENTS:\n'+json.dumps([{k:v for k,v in r.items() if k!='split'} for r in rows]))
  answers=call(f'generate-{batch:02d}',prompt,schema)
  records=[dict(**r,messages=answers[r['id']],requested_model=MODEL,training_admitted=False) for r in rows]
  save(ROOT/f'private/generate-{batch:02d}/records.json',records)
  return records
 generated=parallel(range(50),generate);records=[r for b in range(50) for r in generated[b]];save(ROOT/'private/records.json',records)
 review_item=dict(type='object',properties=dict(id=dict(type='string'),pass_quality=dict(type='boolean'),critical_error=dict(type='boolean'),reason=dict(type='string',maxLength=220)),required=['id','pass_quality','critical_error','reason'],additionalProperties=False)
 def review(batch):
  rows=records[batch*20:batch*20+20]
  schema=dict(type='object',properties=dict(reviews=dict(type='array',items=review_item,minItems=20,maxItems=20)),required=['reviews'],additionalProperties=False)
  prompt=('Critically review these 20 independent English conversation demonstrations. Return one review for each exact ID. Reject wrong arithmetic, unsupported facts, contradictions, overlooked constraints, format deviations when exact format is requested, incomplete physical instructions, fabricated actions/tool success, incoherent English, stale answers after correction, or needless repeated disclaimers. Inspect ALL assistant turns, not just the final answer; a later correction does not excuse an earlier bad supervised turn. Distinguish useful grounded inference from invented facts. Reject critical safety/factual/action errors and mark critical_error. Do not rewrite. Same-teacher review is not independent truth verification. Use no tools, shell, files, browsing, MCP or agents. Return only JSON.\nCONVERSATIONS:\n'+json.dumps([dict(id=r['id'],messages=r['messages']) for r in rows],ensure_ascii=False))
  out=call(f'review-{batch:02d}',prompt,schema)['reviews'];assert sorted(r['id'] for r in out)==sorted(r['id'] for r in rows)
  return out
 reviewed=parallel(range(50),review);reviews=[r for b in range(50) for r in reviewed[b]];save(ROOT/'private/teacher-reviews.json',reviews)
 analyze(records,reviews)

def analyze(records,reviews):
 sp=SentencePieceProcessor(model_file=str(PROJECT/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
 review={r['id']:r for r in reviews};issues={r['id']:[] for r in records};seen={}
 def grams(messages):
  words=re.findall(r'\w+',' '.join(m['content'] for m in messages).lower());return set(tuple(words[i:i+5]) for i in range(len(words)-4))
 for r in records:
  msgs=r['messages'];rid=r['id'];roles=[m['role'] for m in msgs]
  if len(msgs)%2 or roles!=['user','assistant']*(len(msgs)//2):issues[rid].append('roles_not_alternating')
  norm=' '.join(re.findall(r'\w+',' '.join(m['content'] for m in msgs).lower()));h=hashlib.sha256(norm.encode()).hexdigest()
  if h in seen:issues[rid].append('exact_duplicate');issues[seen[h]].append('exact_duplicate')
  seen[h]=rid
  r['counts']=dict(content_tokens=sum(len(sp.encode(m['content'])) for m in msgs),assistant_content_tokens=sum(len(sp.encode(m['content'])) for m in msgs if m['role']=='assistant'),messages=len(msgs),plain_role_serialization_tokens=len(sp.encode(''.join(m['role']+': '+m['content']+'\n' for m in msgs)))+1)
  r['fits_current_context256']=r['counts']['plain_role_serialization_tokens']<=256
 # Older training data and the previous 100 are already exposed; no historical sealed fixtures are read.
 prior_paths=[PROJECT/'restart/teacher-pilot500-v3/train-candidates.jsonl',PROJECT/'restart/sol-conversation-data-v1/private/candidates.jsonl']
 priors=[];prior_meta=[]
 for path in prior_paths:
  rows=[json.loads(s) for s in path.read_text().splitlines()]
  priors.extend(dict(id=f'prior:{path.parent.name}:{r["id"]}',messages=r['messages'],split=r.get('split','train')) for r in rows)
  prior_meta.append(dict(path=str(path.relative_to(PROJECT)),sha256=sha(path),records=len(rows)))
 # Inverted index retrieves every pair sharing at least one 5-shingle; Jaccard >=.5 necessarily shares one.
 allrows=records+priors;allgrams=[grams(r['messages']) for r in allrows];index=defaultdict(list);matches=[]
 for i,a in enumerate(allrows):
  candidates=set()
  for g in allgrams[i]:candidates.update(index[g])
  for j in candidates:
   if j>=len(records):continue
   b=allrows[j];x,y=allgrams[i],allgrams[j];score=len(x&y)/len(x|y) if x|y else 1
   if score>=.5:
    matches.append(dict(a=a['id'],b=b['id'],jaccard=score,scope='within_new_batch' if i<len(records) else 'prior_exposed_data'))
    if i<len(records):issues[a['id']].append('near_duplicate')
    issues[b['id']].append('near_duplicate')
  for g in allgrams[i]:index[g].append(i)
 totals={}
 for r in records:
  rid=r['id'];r['automated_issues']=sorted(set(issues[rid]));r['teacher_review']=review[rid]
  r['quality_clear_candidate']=not issues[rid] and review[rid]['pass_quality'] and not review[rid]['critical_error']
  c=totals.setdefault(r['split'],Counter());c.update(generated_documents=1)
  if r['quality_clear_candidate']:
   c.update(quality_clear_documents=1);c.update(r['counts'])
   if r['fits_current_context256']:c.update(context256_diagnostic_documents=1,context256_content_tokens=r['counts']['content_tokens'],context256_assistant_content_tokens=r['counts']['assistant_content_tokens'])
 with (ROOT/'private/candidates.jsonl').open('w') as f:
  for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 sample=set(read(ROOT/'plan.json')['primary_sample_ids']);save(ROOT/'private/primary-sample.json',[r for r in records if r['id'] in sample])
 save(ROOT/'dedup-report.json',dict(metric='Normalized exact text; exact 5-word-shingle Jaccard >=0.5 for all new/new and new/prior pairs with shared shingles',prior_sources=prior_meta,matches=matches,limits='Not an embedding-based semantic deduplication or global contamination guarantee. Historical sealed evaluation not read.'))
 save(ROOT/'report.json',dict(status='GENERATED_REVIEWED_PENDING_PRIMARY',requested_model=MODEL,resolved_model=None,generated=len(records),quality_clear=sum(r['quality_clear_candidate'] for r in records),splits={s:dict(c) for s,c in totals.items()},teacher_rejections=[r['id'] for r in records if not r['teacher_review']['pass_quality'] or r['teacher_review']['critical_error']],duplicate_matches=len(matches),usage=dict(usage),requests_started=attempts,requests_completed=completed,elapsed_seconds=time.time()-start_epoch,student_updates=0,training_admitted=0,training_paused=True,token_counts='Native SentencePiece content; assistant content excludes role/end-turn markers. Current-context fit uses diagnostic plain role serialization, not an approved training format.',limitations=['Same-model review is not independent factual verification.','New synthetic family/scene-separated holdouts are not sealed independent benchmarks.','No actual internal or MCP tool-call traces.','Chat serialization, assistant masking and end-turn boundaries must be frozen before training.','Foundation admission failure remains unresolved.']))
if __name__=='__main__':
 try:main()
 except BaseException as e:
  stop.set();save(ROOT/'STOP.json',dict(error=type(e).__name__,detail=str(e),epoch=time.time(),student_updates=0));raise
