import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import collections,hashlib,json,pathlib,resource,shutil,sqlite3,sys,time
R=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(R));D=R/'data/own-base-tool-session-extension-v1';HERE=pathlib.Path(__file__).parent
# All authored wording and plans frozen in this file before any generated lesson.
TRAIN=[
('length','Convert {a} centimetres to metres, then multiply that reading by {b} for the batch. Use both tools in that order.','Add {d} metres to the previous batch result, then convert the updated length to centimetres. Use the recorded batch reading.','convert','cm','m','multiply','add','convert','m','cm'),
('volume','Convert {a} litres to millilitres, then multiply the returned volume by {b} containers. Execute both steps.','Subtract {d} millilitres from that recorded total, then convert the remaining volume to litres.','convert','l','ml','multiply','subtract','convert','ml','l'),
('mass','Convert {a} kilograms to grams, then divide that result among {b} equal packages. Execute both steps.','Multiply the previous package reading by {d}, then convert the resulting grams back to kilograms.','convert','kg','g','divide','multiply','convert','g','kg'),
('time','Convert {a} hours to minutes, then multiply the returned duration by {b} shifts. Use both tools.','Add {d} minutes to that recorded duration, then convert the new duration from minutes to hours.','convert','h','min','multiply','add','convert','min','h'),
('area','Multiply {a} by {b} to get a panel area, then multiply that observed result by {c} panels. Use the calculator twice.','Subtract {d} from that recorded total area, then divide the remaining area into {b} equal sections using the calculator.','calculate','multiply',None,'multiply','subtract','calculate','divide',None),
('stock','Multiply a rate of {a} items by {b} intervals, then add {c} initial items to that result. Use the calculator twice.','Subtract {d} used items from the previous recorded stock, then divide the remainder among {b} boxes.','calculate','multiply',None,'add','subtract','calculate','divide',None),
('budget','Add the costs {a} and {b}, then multiply the recorded subtotal by {c} batches. Use two calculator calls.','Subtract a credit of {d} from the previous recorded total, then divide the balance among {b} people.','calculate','add',None,'multiply','subtract','calculate','divide',None),
('offset','Convert an offset of {a} centimetres to metres, then add {b} metres to that recorded offset.','Subtract a bias of {d} metres from the previous recorded offset, then convert the adjusted result to millimetres.','convert','cm','m','add','subtract','convert','m','mm')]
DEV=[
('dev_distance','My ledger begins with {a} metres. Express that in centimetres and scale the returned reading by {b}; execute both steps.','Increase the preceding ledger reading by {d} centimetres, then express the updated reading in metres.','convert','m','cm','multiply','add','convert','cm','m'),
('dev_capacity','A tank record gives {a} millilitres. Change to litres, then multiply the reported quantity by {b}.','Deduct {d} litres from the last reported quantity and express what remains in millilitres.','convert','ml','l','multiply','subtract','convert','l','ml'),
('dev_allocation','The worksheet requires the product of {a} and {b}, followed by adding {c} to the observed product. Run each operation.','Take {d} off the previous worksheet answer and calculate one of {b} equal shares of the remainder.','calculate','multiply',None,'add','subtract','calculate','divide',None),
('dev_invoice','First combine {a} and {b}; then scale that observed sum by {c}. Record both calculator operations.','Apply a deduction of {d} to the last invoice result; then divide the updated value by {b} using another call.','calculate','add',None,'multiply','subtract','calculate','divide',None)]
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def write(p,x):
 with p.open('x') as f:json.dump(x,f,indent=2);f.write('\n')
def show(x):return str(int(x)) if int(x)==x else f'{x:.9g}'
def callcalc(op,a,b):return dict(name='calculate',arguments=dict(op=op,a=a,b=b))
def callconv(v,s,t):return dict(name='convert',arguments={'value':v,'from':s,'to':t})
def main():
 os.nice(10);D.mkdir();start=time.time()
 def check():
  assert time.time()-start<300 and not any(p.exists() for p in (R/'runs/STOP',R/'runs/own-base-foundation-01/STOP',D/'STOP'))
  assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<=200*1024**2
  assert shutil.disk_usage(R).free>=20*1024**3 and sum(p.stat().st_size for p in D.iterdir() if p.is_file())<=50*1024**2
 check();paths=[pathlib.Path(__file__),HERE/'PROTOCOL.md']+[R/p for p in ('own_base_tool_adapter.py','own_base_chat.py','own_base_sft_rows.py','dialogue.py','tools/__init__.py','tokenizer.py','data/tokenizer/encoder.json','data/tokenizer/vocab.bpe')];pins={str(p.relative_to(R)):sha(p) for p in paths};write(D/'policy.json',dict(seed=20261106,pins=pins,train_forms=TRAIN,development_forms=DEV,parameter_domain={'train_a':[20,31],'development_a':[71,78],'b':[2,4],'c':[2,3],'d':[1,4]},state='frozen_before_generation'))
 from tools import FixtureSession
 from tokenizer import load
 from own_base_tool_adapter import adapt_lesson
 tok=load();con=sqlite3.connect(D/'candidates.sqlite');con.execute('pragma cache_size=-1024');con.execute('create table documents(doc_id TEXT PRIMARY KEY,text TEXT NOT NULL,family TEXT NOT NULL,split TEXT NOT NULL,original_lesson_json TEXT NOT NULL,adapted_json TEXT NOT NULL,audit_json TEXT NOT NULL,row_metadata_json TEXT NOT NULL,first_call_signature TEXT,rows INTEGER NOT NULL,input_tokens INTEGER NOT NULL,target_tokens INTEGER NOT NULL,no_call_rows INTEGER NOT NULL,actual_observations INTEGER NOT NULL,replay_observations INTEGER NOT NULL,error_observations INTEGER NOT NULL)');counts=collections.defaultdict(collections.Counter);refused=[];exposure=collections.Counter();paramsets={};familysets={};source_records=[]
 units={'mm':.001,'cm':.01,'m':1,'g':1,'kg':1000,'ml':1,'l':1000,'min':60,'h':3600}
 def independent(call):
  x=call['arguments']
  if call['name']=='convert':return x['value']*units[x['from']]/units[x['to']]
  a,b=x['a'],x['b'];op=x['op'];return a+b if op=='add' else a-b if op=='subtract' else a*b if op=='multiply' else a/b
 for split,forms,n,base in [('train',TRAIN,12,20),('exposed-development',DEV,8,71)]:
  paramsets[split]=set();familysets[split]=set()
  for form in forms:
   name,u1,u2,kind,x,y,op2,op3,kind4,x4,y4=form;family='session4/'+name;familysets[split].add(family)
   for i in range(n):
    check();p=dict(a=base+i,b=2+i%3,c=2+i%2,d=1+i%4);paramsets[split].add(tuple(p.values()));counts[split]['attempted']+=1;history=[];observations=[];policy=[];s=FixtureSession();values=[];calls=[]
    def user(text,permit=True):
     po=dict(permit_calls=permit,fixture_for=None,fixture=None);policy.append(po);s.start_turn(**po);history.append(dict(role='user',text=text))
    def execute(call):
     rec=s.propose(canonical(call),assistant_call_boundary=True);assert rec['ok'] and rec['source']=='offline fixture' and rec['data']['result']==independent(call);observations.append({k:v for k,v in rec.items() if k!='timestamp'});history.extend([dict(role='assistant',call=call),dict(role='tool',result=dict(name=rec['name'],id=rec['call_id'],result=rec['data']['result']))]);calls.append(call);values.append(rec['data']['result']);return rec['data']['result']
    user(u1.format(**p));v1=execute(callconv(p['a'],x,y) if kind=='convert' else callcalc(x,p['a'],p['b']));v2=execute(callcalc(op2,v1,p['b'] if kind=='convert' else p['c']));history.append(dict(role='assistant',text=f'After the two requested steps, the tool returned {show(v2)}. I will retain that observed result for your next instruction.'))
    user(u2.format(**p));v3=execute(callcalc(op3,v2,p['d']));v4=execute(callconv(v3,x4,y4) if kind4=='convert' else callcalc(x4,v3,p['b']));history.append(dict(role='assistant',text=f'The next two steps returned {show(v3)} and then {show(v4)}. The final observed result is {show(v4)}.'))
    mode=i%3
    if mode==0:
     user('Give an audit recap of the four observations in their original order. Distinguish the intermediate readings from the final value, using only the observations already in this conversation.')
     answer=f'The first tool observation was {show(v1)}. The second operation used that observation and returned {show(v2)}, completing the first user turn. In the next turn, the third operation used the earlier result and returned {show(v3)}. The fourth operation then used that reading and returned {show(v4)}. These are the four recorded observations in order; {show(v4)} is the final value. This recap reports the existing trace and does not represent a new calculation.'
    elif mode==1:
     user('Recall my original starting amount and the final observed result. Make clear which belongs to the initial request and which was produced after the four operations. Use the existing conversation record.')
     answer=f'Your original starting amount was {show(p["a"])}. That is the value supplied in the first request, before any of the four operations. The final observed result was {show(v4)}, returned by the fourth tool call. The original amount and final result have different roles in the calculation; this answer recalls both from the conversation rather than making another call.'
    else:
     user(f'Correction for my notes: the original starting amount should be {p["a"]+1}. Do not recalculate or call any tools. Acknowledge the correction and state whether the existing final observation has been updated.',False)
     answer=f'I have noted the corrected starting amount of {p["a"]+1} in this conversation. The recorded final observation is still {show(v4)}; it has not been recalculated or updated. No new tool call was made.'
    history.append(dict(role='assistant',text=answer));assert s.session_calls==4 and len(policy)==3;assert calls[1]['arguments']['a']==v1 and calls[2]['arguments']['a']==v2 and (calls[3]['arguments'].get('value',calls[3]['arguments'].get('a')))==v3
    lesson=dict(family=family,history=history,observations=observations,policy=policy);did=hashlib.sha256(canonical(lesson).encode()).hexdigest();source_records.append(dict(doc_id=did,family=family,split=split,parameters=p,third_turn_mode=mode))
    try:adapt=adapt_lesson(lesson,tok)
    except ValueError as e:refused.append(dict(doc_id=did,family=family,split=split,reason=str(e)));counts[split]['refused']+=1;continue
    rows=[];meta=[]
    for turn in adapt['turns']:
     row=turn['row'];h=turn['history'];last=max(j for j,msg in enumerate(h) if msg['role']=='user');nc=sum('call' in msg for msg in h[last:]);meta.append(dict(turn_index=turn['turn_index'],input_tokens=len(row.inputs),assistant_targets=row.target_count,current_turn_calls=nc));rows.append({k:turn[k] for k in ('turn_index','history','policy')})
     for j,label in enumerate(row.labels):
      if label!=-100:lo=((j+1)//256)*256;exposure[f'{lo}..{lo+255}']+=1
    assert [x['current_turn_calls'] for x in meta]==[2,2,0];targets=sum(x['assistant_targets'] for x in meta);con.execute('insert into documents values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(did,canonical(history),family,split,canonical(lesson),canonical(rows),canonical(adapt['audit']),canonical(meta),canonical(calls[0]),3,sum(x['input_tokens'] for x in meta),targets,1,4,0,0));con.commit();counts[split]['retained']+=1;counts[split]['targets']+=targets;counts[split]['actual_calls']+=4
 assert not familysets['train']&familysets['exposed-development'] and not paramsets['train']&paramsets['exposed-development'];assert con.execute('pragma quick_check').fetchone()[0]=='ok';con.close();check();assert all(sha(R/p)==h for p,h in pins.items());write(D/'source-records.json',source_records);write(D/'refused.json',refused);write(D/'candidate-manifest.json',dict(state='candidate_only_not_admitted',training_admitted=False,database=dict(path=str(D/'candidates.sqlite'),sha256=sha(D/'candidates.sqlite'),bytes=(D/'candidates.sqlite').stat().st_size),policy_sha256=sha(D/'policy.json'),source_records_sha256=sha(D/'source-records.json'),refused_sha256=sha(D/'refused.json'),counts=dict(counts),position_exposure=dict(exposure),symbolic_checks='Every ordinary broker observation independently recomputed from frozen numeric plan; all dependent arguments checked',family_overlap=0,parameter_tuple_overlap=0,seconds=time.time()-start));print(json.dumps(dict(counts)));print('positions',dict(exposure))
if __name__=='__main__':main()
