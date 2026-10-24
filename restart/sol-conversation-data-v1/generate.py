"""Bounded GPT-6 Sol conversation generation and separate-call review; no student backend."""
import hashlib,json,os,re,signal,subprocess,sys,time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from slm.teacher.cli import OVERRIDES,clean_environment
from slm.teacher.sol import parse_sol_events
from jsonschema import Draft202012Validator
from sentencepiece import SentencePieceProcessor
EXE='/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex'
MODEL='gpt-6-sol'
FAMILIES=[
 ('clarification','Resolve ambiguous everyday requests through one useful question, then follow through.'),
 ('correction','Update a plan or answer when the user corrects an earlier fact; preserve unaffected details.'),
 ('grounded_extraction','Answer from a short fictional note included in the first user message; acknowledge missing facts.'),
 ('planning','Make practical schedules from explicit durations and constraints; adapt after a change.'),
 ('comparison','Compare fictional choices using supplied prices and preferences; update recommendations.'),
 ('rewriting','Rewrite supplied short text with constraints on tone, length or audience; preserve meaning.'),
 ('summarization','Summarize supplied original prose, then answer a precise question about it.'),
 ('simple_explanation','Explain basic stable everyday or elementary scientific concepts simply; respond to confusion.'),
 ('reading_comprehension','Discuss a short original story included in the user message; track characters and causes.'),
 ('arithmetic','Solve small everyday arithmetic from supplied numbers; handle a changed number correctly.'),
 ('preferences','Remember preferences across turns and honor a newly added constraint.'),
 ('uncertainty','Distinguish supplied evidence from unknowns, avoid inventing personal or current information.'),
 ('tool_honesty','No tools are available: help draft or plan actions, explicitly avoid claiming bookings, messages or file changes occurred.'),
 ('tool_result_grounding','The user supplies a clearly fictional internal or MCP tool result as text. Interpret it and report failures honestly; do not execute tools or pretend to do so.'),
 ('structured_output','Follow a simple requested JSON or list format, then revise one field without adding facts.'),
 ('casual_conversation','Natural short everyday chat that responds specifically and asks at most one relevant follow-up.'),
 ('troubleshooting','Diagnose harmless household or basic software issues using observations; revise a hypothesis after new evidence.'),
 ('instructions','Give simple ordered instructions for harmless everyday activities; adapt to a missing item.'),
 ('misconception','Politely correct an elementary misconception with a concrete example and handle a follow-up.'),
 ('constraint_conflict','Recognize incompatible fictional requirements, explain the conflict and ask which constraint can change.')]
# Entire task families are reserved. These are new synthetic development/test sets, not independent benchmarks.
SPLITS={i:('development' if i in (6,16) else 'test' if i in (9,19) else 'train') for i in range(20)}
def save(p,obj):
 p=Path(p);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n');tmp.replace(p)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def call(name,prompt,schema,deadline):
 folder=ROOT/'private'/name;folder.mkdir(parents=True,exist_ok=False)
 save(folder/'schema.json',schema);(folder/'prompt.txt').write_text(prompt)
 argv=[EXE,'exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','--cd',str(folder),'--model',MODEL,'--json','--color','never','--output-schema',str(folder/'schema.json'),'--output-last-message',str(folder/'answer.json')]
 controls={k:v for k,v in OVERRIDES.items() if k!='tools.view_image'};controls['model_reasoning_effort']='medium'
 for k,v in controls.items():argv+=['-c',k+'='+json.dumps(v)]
 argv+=['-'];save(folder/'started.json',dict(requested_model=MODEL,prompt_sha256=sha(folder/'prompt.txt'),epoch=time.time(),argv=argv))
 start=time.monotonic()
 with (folder/'events.jsonl').open('xb') as out,(folder/'stderr.txt').open('x') as err,(folder/'prompt.txt').open('rb') as inp:
  proc=subprocess.Popen(argv,env=clean_environment(),stdin=inp,stdout=out,stderr=err,start_new_session=True)
  try:
   while proc.poll() is None:
    if time.time()>min(deadline,start_epoch+1800) or time.monotonic()-start>180:raise TimeoutError('Bounded teacher deadline')
    if (folder/'events.jsonl').stat().st_size>2*1024**2 or (folder/'stderr.txt').stat().st_size>131072:raise ValueError('Log byte cap')
    if (folder/'answer.json').exists() and (folder/'answer.json').stat().st_size>131072:raise ValueError('Answer byte cap')
    time.sleep(.2)
  finally:
   if proc.poll() is None:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
   save(folder/'terminal.json',dict(returncode=proc.returncode,reaped=True,seconds=time.monotonic()-start))
 if proc.returncode:raise RuntimeError('Teacher failed, no retry or fallback')
 raw=parse_sol_events((folder/'events.jsonl').read_text(),(folder/'answer.json').read_text(),SimpleNamespace(model_id=MODEL,max_response_bytes=131072,observed_output_token_limit=14000))
 answer=read(folder/'answer.json');Draft202012Validator(schema).validate(answer)
 usage.update(raw['usage'])
 save(folder/'receipt.json',dict(requested_model=MODEL,resolved_model=None,usage=raw['usage'],tools_used=False,answer_sha256=sha(folder/'answer.json')))
 if usage['output_tokens']+usage['reasoning_output_tokens']>200000:raise ValueError('Aggregate observed output cap')
 save(ROOT/'progress.json',dict(completed_requests=len(list((ROOT/'private').glob('*/receipt.json'))),usage=dict(usage),elapsed_seconds=time.time()-start_epoch))
 print(json.dumps(dict(event='teacher_complete',name=name,elapsed_seconds=round(time.time()-start_epoch))),flush=True)
 return answer

def main():
 global start_epoch,usage
 signal.signal(signal.SIGTERM,lambda *_:(_ for _ in ()).throw(KeyboardInterrupt('Terminated')))
 if (ROOT/'started.json').exists():raise RuntimeError('No automatic rerun')
 version=subprocess.run([EXE,'--version'],capture_output=True,text=True,check=True,timeout=10).stdout.strip()
 assert version=='codex-cli 0.163.0-alpha.11.2'
 login=subprocess.run([EXE,'login','status'],env=clean_environment(),capture_output=True,text=True,check=True,timeout=10)
 assert (login.stdout+login.stderr).strip()=='Logged in using ChatGPT'
 start_epoch=time.time();usage=Counter();deadline=start_epoch+1800
 save(ROOT/'plan.json',dict(owner_instruction='use gpt 6 sol to generate conversation training data',requested_model=MODEL,conversations=100,train=80,development=10,test=10,task_family_disjoint=True,requests_max=20,automatic_retries=0,wall_seconds_max=1800,per_request_seconds_max=180,observed_output_plus_reasoning_max=200000,student_training=False,review='All records separate-call Sol review; direct primary review fixed one record per family',sample_ids=[f'sol-{i:02d}-0' for i in range(20)],limits='Same-teacher review is not independent truth verification. New holdouts are not sealed historical benchmarks. No MCP execution traces are generated.',tokenizer='native 32000 SentencePiece',source_sha256=sha(__file__)))
 save(ROOT/'started.json',dict(epoch=start_epoch,client=version,pid=os.getpid()))
 records=[]
 message=dict(type='object',properties=dict(role=dict(type='string',enum=['user','assistant']),content=dict(type='string',minLength=1,maxLength=1600)),required=['role','content'],additionalProperties=False)
 conv=dict(type='array',items=message,minItems=4,maxItems=6)
 for batch in range(10):
  specs=[]
  for family in range(batch*2,batch*2+2):
   for k in range(5):specs.append(dict(id=f'sol-{family:02d}-{k}',family=FAMILIES[family][0],brief=FAMILIES[family][1],variant=k))
  schema=dict(type='object',properties={r['id']:conv for r in specs},required=[r['id'] for r in specs],additionalProperties=False)
  prompt=('Create original English conversation demonstrations for a small student language model. Return exactly the assigned IDs as JSON. Each conversation has 2 or 3 user/assistant turn pairs, starts with user and ends with assistant. Use natural, concise English: usually 10-35 words per assistant reply; whole conversation ideally 80-150 words. Five variants per family must have substantially different situations, wording and reasoning, not just swapped names. Include all necessary fictional facts or original source text in user messages; do not refer to absent documents. Keep arithmetic correct. No copyrighted quotations, personal data, current facts, medical/legal/financial advice, hidden reasoning or generic AI disclaimers. Follow constraints, retain entities, handle corrections, uncertainty and negation. The assistant has no tools: never claim an external action occurred. User-supplied tool results are fictional quoted data only. Do not emit tool calls, system messages or tool role messages. Generate content only: no tools, files, shell, browsing, MCP or agents.\nASSIGNMENTS:\n'+json.dumps(specs))
  answers=call(f'generate-{batch:02d}',prompt,schema,deadline)
  for s in specs:records.append(dict(id=s['id'],family=s['family'],split=SPLITS[int(s['id'].split('-')[1])],messages=answers[s['id']],requested_model=MODEL,provenance='new synthetic Sol generation',training_admitted=False))
  save(ROOT/'private'/'records.json',records)
 review_schema_item=dict(type='object',properties=dict(id=dict(type='string'),pass_quality=dict(type='boolean'),critical_error=dict(type='boolean'),reason=dict(type='string',maxLength=240)),required=['id','pass_quality','critical_error','reason'],additionalProperties=False)
 reviews=[]
 for batch in range(10):
  rows=records[batch*10:batch*10+10]
  schema=dict(type='object',properties=dict(reviews=dict(type='array',items=review_schema_item,minItems=10,maxItems=10)),required=['reviews'],additionalProperties=False)
  prompt=('Critically review each independent conversation as training data. Reject any wrong arithmetic, unsupported facts, contradiction, ignored constraint, unnatural repetition, fabricated action/tool success, unclear context, or incoherent English. Check turn-to-turn consistency. Mark serious factual/action/contradiction mistakes critical. Be strict; do not rewrite. This is a separate review call of same-teacher synthetic data, not independent factual verification. No tools, shell, files, browsing, MCP or agents. Return only JSON, one review per exact ID.\nCONVERSATIONS:\n'+json.dumps([dict(id=r['id'],messages=r['messages']) for r in rows],ensure_ascii=False))
  out=call(f'review-{batch:02d}',prompt,schema,deadline)['reviews']
  assert sorted(r['id'] for r in out)==sorted(r['id'] for r in rows)
  reviews+=out
 save(ROOT/'private'/'teacher-reviews.json',reviews)
 analyze(records,reviews)

def analyze(records,reviews):
 sp=SentencePieceProcessor(model_file=str(PROJECT/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'))
 seen={};issues={r['id']:[] for r in records};ngrams={}
 for r in records:
  msgs=r['messages'];rid=r['id']
  if [m['role'] for m in msgs]!=['user','assistant']*(len(msgs)//2):issues[rid].append('roles_not_alternating')
  text='\n'.join(m['content'] for m in msgs);norm=' '.join(re.findall(r'\w+',text.lower()))
  h=hashlib.sha256(norm.encode()).hexdigest()
  if h in seen:issues[rid].append('exact_duplicate');issues[seen[h]].append('exact_duplicate')
  seen[h]=rid;words=norm.split();ngrams[rid]=set(tuple(words[i:i+5]) for i in range(len(words)-4))
  r['counts']=dict(content_tokens=sum(len(sp.encode(m['content'])) for m in msgs),assistant_content_tokens=sum(len(sp.encode(m['content'])) for m in msgs if m['role']=='assistant'),messages=len(msgs))
  r['counts']['plain_role_serialization_tokens']=len(sp.encode(''.join(m['role']+': '+m['content']+'\n' for m in msgs)))+1
  r['fits_current_context256']=r['counts']['plain_role_serialization_tokens']<=256
 cross=[]
 for i,a in enumerate(records):
  for b in records[i+1:]:
   if a['split']==b['split']:continue
   x,y=ngrams[a['id']],ngrams[b['id']];j=len(x&y)/len(x|y) if x|y else 1
   if j>=.5:
    cross.append(dict(a=a['id'],b=b['id'],jaccard=j));issues[a['id']].append('cross_split_near_duplicate');issues[b['id']].append('cross_split_near_duplicate')
 review={r['id']:r for r in reviews};totals={}
 for r in records:
  r['automated_issues']=issues[r['id']];r['teacher_review']=review[r['id']]
  r['quality_clear_candidate']=not issues[r['id']] and review[r['id']]['pass_quality'] and not review[r['id']]['critical_error']
  c=totals.setdefault(r['split'],Counter());c.update(documents=1);c.update(r['counts'])
  if r['quality_clear_candidate']:
   c.update(quality_clear_documents=1,quality_clear_content_tokens=r['counts']['content_tokens'],quality_clear_assistant_content_tokens=r['counts']['assistant_content_tokens'])
  if r['quality_clear_candidate'] and r['fits_current_context256']:c.update(quality_clear_context256_documents=1)
 with (ROOT/'private'/'candidates.jsonl').open('w') as f:
  for r in records:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 sample=[r for r in records if r['id'].endswith('-0')];save(ROOT/'private'/'primary-sample.json',sample)
 save(ROOT/'report.json',dict(status='GENERATED_REVIEWED_PENDING_PRIMARY',requested_model=MODEL,resolved_model=None,generated=len(records),splits={s:dict(c) for s,c in totals.items()},cross_split_near_duplicates=cross,teacher_rejections=[r['id'] for r in records if not r['teacher_review']['pass_quality'] or r['teacher_review']['critical_error']],usage=dict(usage),elapsed_seconds=time.time()-start_epoch,student_updates=0,training_admitted=0,token_counts='Native SentencePiece content only; assistant content excludes end-turn/format markers. Final supervised targets require a frozen serialization. Plain role serialization is a diagnostic, not an approved chat format.',leakage_scope='Exhaustive exact and 5-word-shingle cross-split pair comparison within this batch. Historical sealed evaluation not accessed; global source-history overlap not certified.'))
if __name__=='__main__':
 try:main()
 except BaseException as e:
  save(ROOT/'STOP.json',dict(error=type(e).__name__,detail=str(e),student_updates=0,epoch=time.time()));raise
