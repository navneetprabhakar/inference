import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import collections,hashlib,json,pathlib,re,sqlite3,sys,time,resource
R=pathlib.Path(__file__).resolve().parents[2];D=R/'data/own-base-tool-review-v1';V=R/'data/own-base-tool-candidates';sys.path.insert(0,str(R));os.nice(10);start=time.monotonic()
def check():
 assert time.monotonic()-start<600 and not(R/'runs/STOP').exists() and not(D/'STOP').exists()
 assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<3*1024**3

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def display(v):return str(int(v)) if int(v)==v else f'{v:.9g}'
def stable(r):return {k:v for k,v in r.items() if k!='timestamp'}
m=json.load(open(V/'candidate-manifest.json'));assert sha(V/'candidates.sqlite')==m['database']['sha256'];assert sha(V/'policy.json')==m['policy_sha256']
for p,d in m['code_and_protocol'].items():assert sha(R/p)==d
for p,d in m['tokenizer'].items():assert sha(R/'data/tokenizer'/p)==d
from tools import FixtureSession
from tokenizer import load
from own_base_sft_rows import last_turn_row
from own_base_chat import policy_text
con=sqlite3.connect(f'file:{V}/candidates.sqlite?mode=ro',uri=True);con.row_factory=sqlite3.Row;allrows=[dict(x) for x in con.execute('select * from documents')];selected={}
for d in allrows:
 k=(d['split'],d['family']);rank=hashlib.sha256(('tool-review-v1|'+d['doc_id']).encode()).hexdigest()
 if k not in selected or rank<selected[k][0]:selected[k]=(rank,d)
samples=[d for _,d in sorted(selected.values(),key=lambda x:(x[1]['split'],x[1]['family']))];(D/'family-samples.jsonl').write_text(''.join(json.dumps({k:d[k] for k in ('doc_id','split','family','original_lesson_json')})+'\n' for d in samples));(D/'selection.json').write_text(json.dumps({'state':'frozen_before_review','samples':len(samples),'sample_sha256':sha(D/'family-samples.jsonl'),'ids':[d['doc_id'] for d in samples]},indent=2)+'\n')
tok=load();counts=collections.Counter();failures=[];unit={'mm':.001,'cm':.01,'m':1,'km':1000,'g':1,'kg':1000,'ml':1,'l':1000,'s':1,'min':60,'h':3600,'day':86400}
for d in allrows:
 check()
 try:
  original=json.loads(d['original_lesson_json']);assert hashlib.sha256(canon(original).encode()).hexdigest()==d['doc_id'];assert original['family']==d['family'];assert canon(original['history'])==d['text']
  audit=json.loads(d['audit_json']);assert audit['original']==original;adapted=json.loads(d['adapted_json']);meta=json.loads(d['row_metadata_json']);session=FixtureSession();history=[];turn=-1;obsidx=0;last_obs=None;last_call=None;user='';currentcalls=[];turntargets=[]
  for msg in original['history']:
   role=msg['role']
   if role=='user':
    turn+=1;policy=original['policy'][turn];session.start_turn(**policy);history.append(msg);user=msg['text'];currentcalls=[]
   elif role=='assistant' and 'call' in msg:
    call=msg['call'];assert policy['permit_calls'];observ=session.propose(canon(call),assistant_call_boundary=True);assert session.decisions[-1]['dispatched'];assert stable(observ)==stable(original['observations'][obsidx])==stable(audit['replay_records'][obsidx]);obsidx+=1
    fixture=policy['fixture'] if call==policy['fixture_for'] else None;args=call['arguments'];counts['synthetic' if fixture is not None else 'actual']+=1
    if fixture is not None:
     if 'error' in fixture:assert not observ['ok'] and observ['error']==fixture['error']
     else:assert observ['ok'] and observ['data']['result']==fixture['result']
     assert observ['source']=='synthetic recorded fixture'
    else:
     assert observ['source']=='offline fixture'
     if call['name']=='calculate':
      a,b=args['a'],args['b'];op=args['op']
      if op=='divide' and b==0:assert not observ['ok'] and observ['error']=='division by zero'
      else:
       expected=a+b if op=='add' else a-b if op=='subtract' else a*b if op=='multiply' else a/b;assert observ['ok'] and observ['data']['result']==expected
     else:assert observ['ok'] and observ['data']['result']==args['value']*unit[args['from']]/unit[args['to']]
    if currentcalls:assert args['a']==last_obs['data']['result'];counts['within_turn_chains']+=1
    if ('returned number' in user or 'returned reading' in user) and last_obs is not None and not currentcalls:assert args['a']==last_obs['data']['result'];counts['cross_turn_chains']+=1
    if user.startswith('Correction:'):assert args['a']==int(re.search(r'amount was (\d+)',user)[1]) and args['b']==last_call['arguments']['b'];counts['corrections']+=1
    history.append(dict(role='assistant',call=call,call_id=observ['call_id']));last_obs=observ;last_call=call;currentcalls.append(call)
   elif role=='tool':
    projection={'name':last_obs.get('name'),'id':last_obs['call_id'],'result':last_obs['data']['result']} if last_obs['ok'] else {'id':last_obs['call_id'],'error':last_obs['error']};assert msg['result']==projection;history.append(dict(role='tool',record=stable(last_obs)))
   else:
    answer=msg['text'];mode=d['family'].split('/')[1]
    if currentcalls:
     if last_obs['ok']:
      val=display(last_obs['data']['result']);allowed={val,val+' '+last_call['arguments'].get('to',''),f'The fixture reported {val}.',f'The fixture reported {val} '+last_call['arguments'].get('to','')+'.'};allowed.add(val+' '+currentcalls[0]['arguments'].get('to',''));assert answer in allowed
     else:assert answer==f"The fixture returned an error: {last_obs['error']}. No number was returned.";counts['error_answers']+=1
    elif last_obs is not None:
     if 'first operand' in user:assert answer==display(last_call['arguments']['a']);counts['original_recalls']+=1
     elif 'unit' in user:assert answer==last_call['arguments']['from'];counts['original_recalls']+=1
     elif 'numeric result' in user:assert not last_obs['ok'] and answer=='No numeric result was returned.'
     else:assert last_obs['ok'] and answer==display(last_obs['data']['result']);counts['value_recalls']+=1
    elif mode=='permission_change':assert answer=='Addition.'
    elif mode=='no_call_expression':assert re.fullmatch(r'\d+ × \d+',answer)
    else:assert mode in {'missing_divisor','missing_start','missing_target','missing_source'} and answer in {'What number should I divide by?','What was the starting quantity?','Which unit should I convert to?','What is the original unit?'}
    if not policy['permit_calls']:assert not currentcalls;counts['prohibited_turn_without_call']+=1
    history.append(msg);expectedhist=[{'role':'system','text':policy_text(policy['permit_calls'],policy.get('allowed_names'))}]+history;got=adapted[turn];assert got['history']==expectedhist and got['policy']==policy and got['turn_index']==turn
    row=last_turn_row(tok,expectedhist);md=meta[turn];assert md==dict(turn_index=turn,input_tokens=len(row.inputs),assistant_targets=row.target_count,current_turn_calls=len(currentcalls));turntargets.append(row.target_count);counts['rows']+=1
  assert len(adapted)==len(meta)==len(original['policy'])==d['rows'];assert sum(turntargets)==d['target_tokens'];assert obsidx==len(original['observations']);counts['lessons']+=1
 except Exception as e:failures.append({'doc_id':d['doc_id'],'family':d['family'],'error_type':type(e).__name__});break
out=dict(state='passed_checked_semantics_not_admitted' if not failures else 'failed_not_admitted',training_admitted=False,failures=failures,counts=dict(counts),families_sampled=len(samples),manifest_sha256=sha(V/'candidate-manifest.json'),database_sha256=m['database']['sha256'],verifier_sha256=sha(__file__),seconds=time.monotonic()-start);(D/'verification.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
