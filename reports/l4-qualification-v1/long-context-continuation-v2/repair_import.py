"""Local-only interactive qualification. No training or automatic admission."""
import sys,json,time,datetime,subprocess,fcntl,hashlib
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
from tools import FixtureSession
ROOT=Path('runs/long-context-import-final-v2').resolve();ROOT.mkdir(exist_ok=True)
lock=Path('runs/concise-teacher-generation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
state={'status':'generating','generated':0,'admitted':0,'trained':0,'model':'gpt-6.1-terra'}
def save():
 state['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(ROOT/'progress.json').write_text(json.dumps(state,indent=2)+'\n')
def obj(p):return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
S={'type':'string'};B={'type':'boolean'}
def cli(name,prompt,schema):
 d=ROOT/name;d.mkdir(exist_ok=False);(d/'prompt.txt').write_text(prompt);(d/'schema.json').write_text(json.dumps(schema))
 args=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d),'-m','gpt-6.1-terra','-c','model_reasoning_effort="high"','--output-schema',str(d/'schema.json'),'--output-last-message',str(d/'output.json'),'--json','-']
 with (d/'events.jsonl').open('w') as out,(d/'stderr.log').open('w') as err:
  p=subprocess.run(args,input='Do not invoke Codex tools, files, network, or agents. Structured tool proposals in the requested JSON are allowed; the local host executes them. No real-world actions. '+prompt,text=True,stdout=out,stderr=err,timeout=600)
 if p.returncode:raise RuntimeError('CLI failed; inspect logs, no automatic retry')
 events=[json.loads(x) for x in (d/'events.jsonl').read_text().splitlines()]
 if not any(e.get('type')=='turn.completed' for e in events):raise RuntimeError('Incomplete CLI response')
 return json.loads((d/'output.json').read_text())
def keyed(rows,ids):
 assert len(rows)==len(ids) and {r['id'] for r in rows}==set(ids)
 return {r['id']:r for r in rows}

try:
 save()
 source=Path('runs/long-context-continuation-cohort-b-revised-v2/candidates.jsonl')
 original=next(s for s in map(json.loads,source.read_text().splitlines()) if s['id']=='continuation-import')
 s=json.loads(json.dumps(original));s['source_file']=str(source);s['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest();s['revision']='repair-false-tool-limitation-and-new-workload-ratio'
 broker=FixtureSession()
 # Keep the actual first user and answer and the pending calculator request.
 s['messages']=s['messages'][:4];s['policies']=s['policies'][:2]
 call_schema=obj({'name':{'type':'string','enum':['calculate']},'arguments':obj({'op':{'type':'string','enum':['add','subtract','multiply','divide']},'a':{'type':'number'},'b':{'type':'number'}})})
 def respond_with_calculator(tag):
  broker.start_turn(permit_calls=True,allowed_names=['calculate','convert'])
  call=cli(tag+'-proposal','Choose the supported calculator operation and operands needed for the last user request. All four enumerated arithmetic operations are available. Use ONLY visible history; output the complete proposal matching the schema. HISTORY:'+json.dumps(s['messages']),call_schema)
  record=broker.propose(json.dumps(call),assistant_call_boundary=True);record.pop('timestamp',None);assert record['ok']
  s['messages'] += [{'role':'assistant','tool_call':call,'call_id':record['call_id']},{'role':'tool','call_id':record['call_id'],'record':record}]
  result=cli(tag+'-answer','Answer the pending user request using the actual observed tool result and earlier facts. State what the ratio measures and does not measure. No fabricated tool restrictions or actions. HISTORY:'+json.dumps(s['messages']),obj({'message':S}))
  s['messages'].append({'role':'assistant','content':result['message']})
 respond_with_calculator('repair')
 # Later requests and answers are semantically independent of the removed limitation claim.
 # Preserve them exactly; primary agent must re-review the complete revised history.
 s['messages']+=original['messages'][5:];s['policies']+=original['policies'][2:]
 user=cli('new-user','Write a natural next USER request for this new decision: the archive team wants to calculate total attempts divided by the latest count of documents with success evidence, and know whether this ratio really measures how many attempts each successful document needed. Do not restate operands; request calculator use. This is a different denominator and interpretation from attempts per manifest document. HISTORY:'+json.dumps(s['messages']),obj({'message':S}))
 s['messages'].append({'role':'user','content':user['message']});s['policies'].append({'permit_calls':True,'allowed_names':['calculate','convert']})
 respond_with_calculator('workload-ratio')
 e=encode_conversation(tok,s['messages'],policies=s['policies'],context=4096);s['context_tokens']=len(e['ids']);s['assistant_targets']=sum(e['mask'][1:]);s['done']=True
 (ROOT/'candidates.jsonl').write_text(json.dumps(s)+'\n');state.update(generated=1,status='awaiting_root_review');save()
 review=cli('review','Review EVERY assistant turn in this revised history. Check chronology, arithmetic and ratios, requested tool use and actual observed records, unknown versus failed states, and unsupported capability/action claims. No automatic admission. DATA:'+json.dumps(s['messages']),obj({'pass':B,'reason':S,'turn_evidence':S}))
 (ROOT/'cli-review.json').write_text(json.dumps(review,indent=2));state['status']='cli_review_complete_pending_root';save()
except Exception as exc:
 state.update(status='blocked',error=str(exc));save();raise
