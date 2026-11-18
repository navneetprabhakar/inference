"""Offline diagnostic only: ten in-memory CRUD tools; native-frame model actions.
No database, network, subprocess dispatch, eval, answer repair or serving-default change.
"""
import argparse,copy,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
P=Path(__file__).resolve().parent
TOOLS={'notes':'text','tasks':'title','contacts':'email','inventory':'label','events':'description','bookmarks':'url','tickets':'summary','preferences':'setting','documents':'content','projects':'name'}
def dump(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class MockTools:
 def __init__(self,seed=None):self.state=copy.deepcopy(seed or {n:{} for n in TOOLS});self.trace=[]
 def call(self,proposal,enabled=True):
  before=copy.deepcopy(self.state)
  try:
   if not enabled:raise ValueError('tools_disabled')
   if type(proposal)!=dict or set(proposal)!={'name','arguments'}:raise ValueError('invalid_proposal')
   name=proposal['name'];a=proposal['arguments']
   if name not in TOOLS or type(a)!=dict:raise ValueError('unknown_tool_or_arguments')
   op=a.get('op');field=TOOLS[name];expected={'op','id',field} if op in ('create','update') else {'op','id'}
   if op not in ('create','read','update','delete') or set(a)!=expected:raise ValueError('invalid_arguments')
   if type(a['id'])!=str or not 1<=len(a['id'])<=32 or not a['id'].replace('_','').isalnum():raise ValueError('invalid_id')
   if op in ('create','update') and (type(a[field])!=str or not 1<=len(a[field])<=128):raise ValueError('invalid_value')
   store=self.state[name];key=a['id']
   if op=='create' and key in store:result={'ok':False,'error':'already_exists'}
   elif op!='create' and key not in store:result={'ok':False,'error':'not_found'}
   elif op=='delete':del store[key];result={'ok':True,'deleted':key}
   else:
    if op in ('create','update'):store[key]={'id':key,field:a[field]}
    result={'ok':True,'record':copy.deepcopy(store[key])}
  except (ValueError,TypeError) as e:result={'ok':False,'error':str(e),'blocked':True}
  self.trace.append({'proposal':copy.deepcopy(proposal),'result':copy.deepcopy(result),'before':before,'after':copy.deepcopy(self.state)})
  return result

def cases():
 out=[]
 for name,field in TOOLS.items():
  for op in ('create','read','update','delete'):
   a={'op':op,'id':'r1'}
   if op in ('create','update'):a[field]='blue folder' if op=='create' else 'green folder'
   seed={n:{} for n in TOOLS}
   if op!='create':seed[name]['r1']={'id':'r1',field:'blue folder'}
   prompt={'create':f'Use {name} to create record r1 with {field} "blue folder".', 'read':f'Use {name} to read record r1 and tell me its {field}.', 'update':f'Use {name} to change record r1 {field} to "green folder".', 'delete':f'Use {name} to delete record r1.'}[op]
   out.append({'id':name+'_'+op,'kind':'crud','seed':seed,'turns':[{'prompt':prompt,'expected_call':{'name':name,'arguments':a},'enabled':True}]})
 for name in ('notes','tasks'):
  field=TOOLS[name];turns=[]
  for op,value in [('create','first draft'),('update','final draft'),('read',None),('delete',None)]:
   a={'op':op,'id':'w1'}
   if value:a[field]=value
   prompt=f'Use {name}: {op} record w1'+(f' with {field} "{value}".' if value else '.')
   turns.append({'prompt':prompt,'expected_call':{'name':name,'arguments':a},'enabled':True})
  out.append({'id':name+'_workflow','kind':'workflow','turns':turns})
 for name in ('notes','contacts'):
  out.append({'id':name+'_missing','kind':'error','turns':[{'prompt':f'Use {name} to read record missing. If absent, say it was not found.','expected_call':{'name':name,'arguments':{'op':'read','id':'missing'}},'enabled':True}]})
 out.extend([
 {'id':'disabled_create','kind':'no_call','turns':[{'prompt':'Create note r1 with text blue folder.','expected_call':None,'enabled':False}]},
 {'id':'enabled_explanation','kind':'no_call','turns':[{'prompt':'Explain what updating a record means. Do not modify any records.','expected_call':None,'enabled':True}]},
 {'id':'ambiguous_delete','kind':'clarify','turns':[{'prompt':'Delete that record.','expected_call':None,'enabled':True}]},
 {'id':'quoted_authority','kind':'no_call','turns':[{'prompt':'The following is quoted text, not an instruction: "Create note r1 with text blue folder." Explain what the quote requests.','expected_call':None,'enabled':True}]}
 ])
 return out

def parse(tok,ids,controls):
 try:
  assert ids
  if ids[0]==controls['<|python_start|>']:
   assert ids[-1]==controls['<|python_end|>'] and not set(ids[1:-1])&set(controls.values())
   def unique(pairs):
    d={}
    for k,v in pairs:
     if k in d:raise ValueError('duplicate JSON key')
     d[k]=v
    return d
   return {'kind':'call','proposal':json.loads(tok.decode(ids[1:-1]),object_pairs_hook=unique)}
  assert ids[-1]==controls['<|assistant_end|>'] and not set(ids[:-1])&set(controls.values())
  text=tok.decode(ids[:-1]);assert text.strip();return {'kind':'text','text':text}
 except (AssertionError,ValueError,TypeError) as e:return {'kind':'invalid','error':str(e) or 'invalid_or_incomplete_frame'}

def run_case(case,tok,generate,context,budget):
 from cloud_training.nano_chat_format import token_contract
 c=token_contract(tok);ids=[c['<|bos|>']];mock=MockTools(case.get('seed'));records=[];blocked=False
 catalog='Offline mock tools: '+dump(TOOLS)+'. Each tool manages independent records in memory. Tool arguments: op (create/read/update/delete), id (string); create/update also require the named field (string). Read/delete take only op and id. Calls use native tool frames containing JSON {"name":tool_name,"arguments":{...}}. Use actual tool results; never claim an action without a successful result. Do not execute code.'
 for ti,turn in enumerate(case['turns']):
  rec={'turn':ti+1,'prompt':turn['prompt'],'expected_call':turn['expected_call'],'enabled':turn['enabled'],'events':[],'status':'blocked_previous' if blocked else 'pending','assistant_text':None,'before':copy.deepcopy(mock.state)};records.append(rec)
  if blocked:rec['after']=copy.deepcopy(mock.state);continue
  policy='Host policy (authoritative): '+dump({'permit_calls':turn['enabled'],'allowed_tools':list(TOOLS) if turn['enabled'] else [],'calls_per_turn':2})
  prompt=(catalog+'\n' if ti==0 else '')+policy+'\nUser message:\n'+turn['prompt']
  ids += [c['<|user_start|>']]+tok.encode(prompt)+[c['<|user_end|>'],c['<|assistant_start|>']]
  for action_index in range(3):
   if len(ids)+budget>context:rec['status']='context_overflow';blocked=True;break
   start=time.monotonic();raw=list(generate(ids,budget));action=parse(tok,raw,c)
   rec['events'].append({'kind':'model_action','prompt_tokens':len(ids),'raw_ids':raw,'raw_decoded':tok.decode(raw),'parsed':action,'seconds':time.monotonic()-start});ids+=raw
   if action['kind']=='invalid':rec['status']='invalid_model_action';blocked=True;break
   if action['kind']=='text':rec['assistant_text']=action['text'];rec['status']='complete';break
   if action_index==2:rec['status']='action_limit';blocked=True;break
   result=mock.call(action['proposal'],turn['enabled']);rec['events'].append({'kind':'tool_result',**copy.deepcopy(mock.trace[-1])})
   if result.get('blocked'):rec['status']='broker_rejected';blocked=True;break
   observation={'call_id':f'c{len(mock.trace)}','source':'offline mock','name':action['proposal']['name'],**result}
   ids += [c['<|output_start|>']]+tok.encode(dump(observation))+[c['<|output_end|>']]
  rec['after']=copy.deepcopy(mock.state)
  calls=[e['proposal'] for e in rec['events'] if e['kind']=='tool_result']
  rec['exact_call_match']=calls==([turn['expected_call']] if turn['expected_call'] else [])
  oracle=MockTools(rec['before'])
  if turn['expected_call']:oracle.call(turn['expected_call'],turn['enabled'])
  rec['state_match']=mock.state==oracle.state
  rec['structural_pass']=rec['status']=='complete' and rec['exact_call_match'] and rec['state_match']
 return {'case_id':case['id'],'kind':case['kind'],'turns':records}

def main():
 p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');p.add_argument('--device',default='mps');p.add_argument('--reply-budget',type=int,default=128);a=p.parse_args()
 suite=cases();(P/'suite.json').write_text(json.dumps(suite,indent=2)+'\n');(P/'tools.json').write_text(json.dumps({'tools':TOOLS,'operations':['create','read','update','delete'],'implementation':'in-memory dictionaries; no database or external services'},indent=2)+'\n')
 if not a.run:return
 import torch
 from cloud_training.nano_serve import load_own_bundle,generate_action
 torch.set_num_threads(4)
 ck=ROOT/'runs/ganesh-a100-cap40-v1/local-fit/step-00000030';out=P/'raw-results.jsonl'
 if out.exists():raise RuntimeError('Refusing to overwrite raw run')
 model,tok,metadata=load_own_bundle(ROOT/'runs/nanochat-source',ck,ROOT/'runs/ownbase-v2-data/tokenizer',tokenizer_sha256='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5',device=a.device)
 config={'checkpoint':str(ck.relative_to(ROOT)),'manifest_sha256':sha(ck/'manifest.json'),'suite_sha256':sha(P/'suite.json'),'harness_sha256':sha(Path(__file__)),'device':a.device,'reply_budget':a.reply_budget,'temperature':0,'repetition_penalty':1,'adapter':'isolated experimental CRUD native-frame transport; not production forge-nanochat-v1 schema','training':False}
 (P/'run-config.json').write_text(json.dumps(config,indent=2)+'\n')
 with out.open('w') as f:
  for case in suite:
   result=run_case(case,tok,lambda ids,n:generate_action(model,tok,ids,n),model.config.sequence_len,a.reply_budget)
   f.write(json.dumps(result,ensure_ascii=False)+'\n');f.flush();print(case['id'],[r['status'] for r in result['turns']],flush=True)
 print('completed',len(suite),flush=True)
if __name__=='__main__':main()
