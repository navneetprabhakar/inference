"""Finish a reviewed practical task with real host broker calls; no truncation."""
import argparse,datetime,fcntl,hashlib,json,subprocess,sys
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation
from tools import FixtureSession
parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--id',required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--need',required=True);args=parser.parse_args();root=args.output.resolve();root.mkdir(exist_ok=False)
lock=Path('runs/concise-teacher-generation.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
def obj(p):return {'type':'object','properties':p,'required':list(p),'additionalProperties':False}
S={'type':'string'};N={'type':'number'}
call={'anyOf':[{'type':'null'},obj({'name':{'type':'string','enum':['calculate']},'arguments':obj({'op':{'type':'string','enum':['add','subtract','multiply','divide']},'a':N,'b':N})})]}
def cli(name,prompt,schema):
 d=root/name;d.mkdir();(d/'schema.json').write_text(json.dumps(schema));(d/'prompt.txt').write_text(prompt)
 with (d/'events.jsonl').open('w') as out,(d/'stderr.log').open('w') as err:
  r=subprocess.run(['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','--sandbox','read-only','-C',str(d),'-m','gpt-6.1-terra','-c','model_reasoning_effort="high"','--output-schema',str(d/'schema.json'),'--output-last-message',str(d/'output.json'),'--json','-'],input='Do not use Codex tools, files, network or agents. Structured proposals only, executed by host. '+prompt,text=True,stdout=out,stderr=err,timeout=600)
 assert r.returncode==0 and any(json.loads(l).get('type')=='turn.completed' for l in (d/'events.jsonl').read_text().splitlines())
 return json.loads((d/'output.json').read_text())
s=next(x for x in map(json.loads,args.source.read_text().splitlines()) if x['id']==args.id);s.update(source_file=str(args.source),source_sha256=hashlib.sha256(args.source.read_bytes()).hexdigest(),revision=root.name)
b=FixtureSession();pol=iter(s['policies']);record=None
for m in s['messages']:
 if m['role']=='user':b.start_turn(**next(pol))
 elif 'tool_call' in m:record=b.propose(json.dumps(m['tool_call']),assistant_call_boundary=True);record.pop('timestamp',None)
 elif m['role']=='tool':assert record==m['record'];record=None
assert record is None and next(pol,None) is None
user=cli('user','Write the next natural USER request for this concrete remaining need. Do not restate the earlier operands needed to answer. No arbitrary length request or assistant coaching. NEED:'+args.need+' HISTORY:'+json.dumps(s['messages']),obj({'message':S}))
s['messages'].append({'role':'user','content':user['message']});policy={'permit_calls':True,'allowed_names':['calculate','convert']};s['policies'].append(policy);b.start_turn(**policy)
for i in range(3):
 answer=cli('assistant-'+str(i),'Answer the visible user with one message OR one calculator proposal. Only calculate add/subtract/multiply/divide supported here. Do not invent tool results. Wait for observed results before the next call. At most2 calls in this turn,4 total; remaining='+str(min(2-b.turn_calls,4-b.session_calls))+'. Give a concise complete answer to this arithmetic decision, no restatement of earlier artifacts. HISTORY:'+json.dumps(s['messages']),obj({'response':{'anyOf':[obj({'message':{'type':'string','enum':['']},'tool_call':call['anyOf'][1]}),obj({'message':S,'tool_call':{'type':'null'}})]}}))['response']
 if answer['tool_call'] is None:
  assert answer['message'].strip();s['messages'].append({'role':'assistant','content':answer['message']});break
 assert not answer['message'];record=b.propose(json.dumps(answer['tool_call']),assistant_call_boundary=True);record.pop('timestamp',None);assert record['ok']
 s['messages']+=[{'role':'assistant','tool_call':answer['tool_call'],'call_id':record['call_id']},{'role':'tool','call_id':record['call_id'],'record':record}]
else:raise RuntimeError('No final answer within tool cap')
s['done']=True;s['termination']='practical_task_completed';tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
try:
 e=encode_conversation(tok,s['messages'],policies=s['policies'],context=4096);s['context_tokens']=len(e['ids']);s['assistant_targets']=sum(e['mask'][1:])
except ValueError as ex:
 if 'Context overflow' not in str(ex):raise
 s['excluded']='context_overflow_no_truncation'
(root/'candidates.jsonl').write_text(json.dumps(s)+'\n');(root/'progress.json').write_text(json.dumps({'status':'awaiting_full_root_review','generated':1,'admitted':0,'trained':0,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
