"""Prospective v2 CPU candidate builder; blocked until root approves plan state."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import collections,hashlib,json,pathlib,random,resource,shutil,sqlite3,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));HERE=pathlib.Path(__file__).resolve().parent
from tools import FixtureSession
from own_base_tool_adapter import adapt_lesson,legacy_projection,canonical
from own_base_chat import stable_tool_record
from tokenizer import load,ASSETS
OPS=['add','subtract','multiply','divide'];SYMBOLS={'add':'+','subtract':'-','multiply':'*','divide':'/'};VERBS={'add':'add','subtract':'subtract','multiply':'multiply by','divide':'divide by'};OP_NAMES={'add':'Addition.','subtract':'Subtraction.','multiply':'Multiplication.','divide':'Division.'}
PAIRS=[('mm','cm'),('cm','m'),('m','km'),('g','kg'),('ml','l'),('s','min'),('min','h'),('h','day')]
PAIRS=[x for pair in PAIRS for x in (pair,tuple(reversed(pair)))]

def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def write(p,value):
 with p.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
def show(x):return str(int(x)) if int(x)==x else str(x)
def calc(op,a,b):return dict(name='calculate',arguments=dict(a=a,b=b,op=op))
def conv(value,src,dst):return dict(name='convert',arguments={'value':value,'from':src,'to':dst})
def seeded(seed,*parts):return int(hashlib.sha256(canonical([seed,*parts]).encode()).hexdigest(),16)

def parameters(plan,form,index):
 block=index//4;variant=index%4;r=random.Random(seeded(plan['seed'],form['family'],block));split=form['split'];lo,hi=plan['parameter_domains']['train_absolute_a' if split=='train' else 'development_absolute_a'];fr=plan['parameter_domains']['fractions']
 p=dict(a=r.choice([-1,1])*(r.randint(lo,hi)+r.choice(fr)),b=r.choice([-1,1])*(r.randint(13,41)+r.choice([0,.5])),c=r.randint(3,9),d=r.choice([-1,1])*(r.randint(43,97)+r.choice(fr)))
 if form.get('kind')=='conversion' or form.get('kind') in ('clarify_unit','chain_convert') or form.get('kind')=='convert':p['a']=abs(p['a'])
 if variant==2 and form.get('kind')!='observation':p['a']+=.25
 if variant==3 and form.get('kind')!='observation':p['b']+=.25
 op=OPS[(block+(variant==1 and form.get('kind')!='observation'))%4];op2=OPS[(block+2)%4];src,dst=PAIRS[block%len(PAIRS)]
 return dict(parameters=p,contrast_group=block,variant=variant,op=op,op2=op2,src=src,dst=dst,form_index=block%len(form['forms']))

class Teacher:
 def __init__(self,family):self.lesson=dict(family=family,history=[],observations=[],policy=[]);self.s=FixtureSession();self.turns=[]
 def user(self,text,permit=True,fixture_for=None,fixture=None):
  po=dict(permit_calls=permit,fixture_for=fixture_for,fixture=fixture);self.s.start_turn(**po);self.lesson['policy'].append(po);self.lesson['history'].append(dict(role='user',text=text));self.turns.append(dict(user=text,policy=po,calls=[],answer_rule=None))
 def execute(self,call):
  rec=self.s.propose(canonical(call),assistant_call_boundary=True);assert self.s.decisions[-1]['dispatched'];stable=stable_tool_record(rec);self.lesson['observations'].append(stable);self.lesson['history'].extend([dict(role='assistant',call=call),dict(role='tool',result=legacy_projection(stable))]);self.turns[-1]['calls'].append(dict(proposal=call,observation=stable));return rec
 def answer(self,text,rule):self.lesson['history'].append(dict(role='assistant',text=text));self.turns[-1]['answer_rule']=rule
 def read(self,rec,unit=None,wrapper=False):
  if not rec['ok']:
   answer='The calculator failed: '+rec['error']+'.' if rec['error']=='division by zero' else 'The tool failed; no numeric result was returned.'
   self.answer(answer,dict(kind='error',error=rec['error']));return
  value=show(rec['data']['result']);value+=(' '+unit) if unit else '';text=('The tool returned '+value+'.') if wrapper else value;self.answer(text,dict(kind='last_observation',unit=unit,wrapper=wrapper))

def primary(plan,templates,form,index):
 v=parameters(plan,form,index);p=v['parameters'];kind=form['kind'];op=v['op'];op2=v['op2'];src,dst=v['src'],v['dst'];fmt={k:show(n) for k,n in p.items()};fmt.update(op=op,op2=op2,symbol=SYMBOLS[op],symbol2=SYMBOLS[op2],verb=VERBS[op],verb2=VERBS[op2],src=src,dst=dst)
 text=form['forms'][v['form_index']].format(**fmt);t=Teacher(form['family']);common=templates['common_templates'];wrap=index%2==0
 if kind=='arithmetic':t.user(text);t.read(t.execute(calc(op,p['a'],p['b'])),wrapper=wrap)
 elif kind=='conversion':t.user(text);t.read(t.execute(conv(p['a'],src,dst)),unit=dst,wrapper=wrap)
 elif kind in ('chain_calc','chain_convert'):
  t.user(text);r1=t.execute(calc(op,p['a'],p['b']) if kind=='chain_calc' else conv(p['a'],src,dst));assert r1['ok'];r2=t.execute(calc(op2,r1['data']['result'],p['c']));t.read(r2,wrapper=wrap)
 elif kind=='observation':
  call=calc(op,p['a'],p['b']);mode=v['variant'];fixture=None if mode==0 else ({'error':'fixture timeout'} if mode==3 else {'result':p['a']+p['d']+(17 if mode==1 else -23)})
  t.user(text,fixture_for=call if fixture else None,fixture=fixture);r=t.execute(call);t.read(r,wrapper=wrap)
  t.user(common['followup_observation'][v['contrast_group']%2],False);t.read(r,wrapper=False)
  v['fixture_mode']='ordinary' if fixture is None else 'synthetic_recorded';v['fixture']=fixture
 elif kind=='correction':
  t.user(text);t.read(t.execute(calc(op,p['a'],p['b'])),wrapper=wrap)
  t.user(common['correction'][v['contrast_group']%2].format(**fmt));t.read(t.execute(calc(op,p['d'],p['b'])),wrapper=not wrap)
 elif kind=='retry':
  call=calc(op,p['a'],p['b']);t.user(text,fixture_for=call,fixture={'error':'fixture timeout'});t.read(t.execute(call));t.user(common['retry'][v['contrast_group']%2]);t.read(t.execute(call),wrapper=wrap)
 elif kind=='clarify':
  t.user(text,False);t.answer('What is the second operand?',dict(kind='missing_operand'))
  t.user('The second operand is '+show(p['b'])+'. Execute the original operation.');t.read(t.execute(calc(op,p['a'],p['b'])),wrapper=wrap)
 elif kind=='clarify_unit':
  t.user(text,False);t.answer('What destination unit should I use?',dict(kind='missing_unit'))
  t.user('Use '+dst+' as the destination. Execute the conversion.');t.read(t.execute(conv(p['a'],src,dst)),unit=dst,wrapper=wrap)
 elif kind=='denied':t.user(text,False);t.answer('Tool calls are disabled; I cannot execute this request.',dict(kind='disabled'))
 elif kind=='zero':t.user(text);t.read(t.execute(calc('divide',p['a'],0)))
 elif kind=='expression':t.user(text,False);t.answer('('+show(p['a'])+') '+SYMBOLS[op]+' ('+show(p['b'])+')',dict(kind='literal_expression',op=op))
 elif kind=='operation':t.user(text,False);t.answer(OP_NAMES[op],dict(kind='operation_name',op=op))
 else:raise ValueError(kind)
 v.update(kind=kind,family=form['family'],split=form['split'],group=form['group'],index=index,turns=t.turns);return t.lesson,v

def session(plan,templates,form,index):
 v=parameters(plan,form,index);p=v['parameters'];ops=form['operations'];src,dst=v['src'],v['dst'];fmt={k:show(n) for k,n in p.items()};fmt.update(op=ops[0],symbol=SYMBOLS.get(ops[0]),op2=ops[1],symbol2=SYMBOLS[ops[1]],op3=ops[2],symbol3=SYMBOLS[ops[2]],op4=ops[3],symbol4=SYMBOLS[ops[3]],src=src,dst=dst,e=show(p['a']+.5))
 t=Teacher(form['family']);user=form['forms'][v['form_index']].format(**fmt);t.user(user)
 r1=t.execute(conv(p['a'],src,dst) if form['kind']=='convert' else calc(ops[0],p['a'],p['b']));r2=t.execute(calc(ops[1],r1['data']['result'],p['c']));t.read(r2)
 t.user(templates['common_templates']['session_second'][index%2].format(**fmt));r3=t.execute(calc(ops[2],r2['data']['result'],p['d']));r4=t.execute(calc(ops[3],r3['data']['result'],p['b']));t.read(r4)
 mode=['recall','recap','correction'][index%3];t.user(templates['common_templates']['session_final'][mode].format(**fmt),False);values=[r['data']['result'] for r in (r1,r2,r3,r4)]
 if mode=='recall':answer=f'Initial value was {show(p["a"])}; final record was {show(values[-1])}.'
 elif mode=='recap':answer='The returns were '+', '.join(show(x) for x in values[:3])+', and '+show(values[-1])+'.'
 else:answer=f'Initial value is now {show(p["a"]+.5)}; final record remains {show(values[-1])}.'
 t.answer(answer,dict(kind=mode,original=p['a'],corrected=p['a']+.5,observations=values));assert [len(x['calls']) for x in t.turns]==[2,2,0]
 v.update(kind=form['kind'],family=form['family'],split=form['split'],group=mode,index=index,operations=ops,turns=t.turns);return t.lesson,v

SCHEMA='CREATE TABLE documents(doc_id TEXT PRIMARY KEY,text TEXT NOT NULL,family TEXT NOT NULL,split TEXT NOT NULL,original_lesson_json TEXT NOT NULL,adapted_json TEXT NOT NULL,audit_json TEXT NOT NULL,row_metadata_json TEXT NOT NULL,first_call_signature TEXT,rows INTEGER NOT NULL,input_tokens INTEGER NOT NULL,target_tokens INTEGER NOT NULL,no_call_rows INTEGER NOT NULL,actual_observations INTEGER NOT NULL,replay_observations INTEGER NOT NULL,error_observations INTEGER NOT NULL,task_json TEXT NOT NULL)'

def build(source,plan,templates,tok):
 config=plan['sources'][source];dest=ROOT/config['output'];dest.mkdir();start=time.monotonic();limit=plan['resource_limits']
 def check():
  if time.monotonic()-start>limit['seconds']:raise RuntimeError('fixed wall cap')
  if any(p.exists() for p in [ROOT/'runs/STOP',dest/'STOP']):raise RuntimeError('STOP')
  if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)>limit['rss_bytes']:raise RuntimeError('RSS cap')
  if shutil.disk_usage(ROOT).free<limit['free_disk_bytes']:raise RuntimeError('disk floor')
  if sum(p.stat().st_size for p in dest.iterdir() if p.is_file())>limit['source_output_bytes']:raise RuntimeError('source output cap')
 paths=[HERE/'PLAN.json',HERE/'templates.json',HERE/'PROTOCOL.md',pathlib.Path(__file__)]+[ROOT/p for p in ['own_base_tool_adapter.py','own_base_chat.py','own_base_sft_rows.py','dialogue.py','tools/__init__.py','tokenizer.py']]
 pins={str(p.relative_to(ROOT)):sha(p) for p in paths};assets={n:sha(ROOT/'data/tokenizer'/n) for n in ASSETS};assert assets==ASSETS
 write(dest/'policy.json',dict(state='frozen_before_instances',source=source,plan=plan,templates_sha256=sha(HERE/'templates.json'),code_and_protocol=pins,tokenizer=assets));check()
 conn=sqlite3.connect(dest/'candidates.sqlite');conn.execute('pragma cache_size=-2048');conn.execute('pragma journal_mode=DELETE');conn.execute(SCHEMA);conn.commit();counts=collections.defaultdict(collections.Counter);pool=[];families=collections.defaultdict(set);train_calls=set();train_params=set();seen_text=set();exposure=collections.Counter();refused=[];records=[];category_counts=collections.defaultdict(collections.Counter)
 forms=templates['primary' if source=='primary' else 'session'];maker=primary if source=='primary' else session
 failure=None
 try:
  for form in forms:
   families[form['split']].add(form['family'])
   for index in range(config['instances_per_family'][form['split']]):
    check();lesson,task=maker(plan,templates,form,index);did=hashlib.sha256(canonical(lesson).encode()).hexdigest();rank=hashlib.sha256(canonical([plan['seed'],source,form['split'],task['group'],did]).encode()).hexdigest();pool.append((form['split'],task['group'],rank,did,lesson,task));counts[form['split']]['generated_lessons']+=1
  assert not families['train']&families['exposed-development']
  # Retained train inventory is known before development selection; fixed original pools only.
  for split in ['train','exposed-development']:
   for group,percent in config['group_percent'].items():
    cap=config['caps'][split]*percent//100;used=0;closed=False
    for _,_,rank,did,lesson,task in sorted((x for x in pool if x[0]==split and x[1]==group),key=lambda x:x[2]):
     check();cnt=category_counts[split+'/'+group];cnt['generated']+=1
     if closed:counts[split]['not_scanned_after_cap']+=1;cnt['not_scanned_after_cap']+=1;continue
     try:adapt=adapt_lesson(lesson,tok)
     except ValueError as e:refused.append(dict(doc_id=did,family=lesson['family'],split=split,group=group,reason='whole_history_fit_or_replay: '+str(e)));counts[split]['refused']+=1;cnt['refused']+=1;continue
     meta=[];adapted=[]
     for turn in adapt['turns']:
      row=turn['row'];hist=turn['history'];last=max(i for i,m in enumerate(hist) if m['role']=='user');calls=sum('call' in m for m in hist[last:]);meta.append(dict(turn_index=turn['turn_index'],input_tokens=len(row.inputs),assistant_targets=row.target_count,current_turn_calls=calls));adapted.append({k:turn[k] for k in ['turn_index','history','policy']})
     targets=sum(x['assistant_targets'] for x in meta);counts[split]['fitted_targets_before_selection']+=targets;cnt['fitted_targets_before_selection']+=targets
     calls=[m['call'] for m in lesson['history'] if 'call' in m];signatures={canonical(c) for c in calls};params=canonical(task['parameters']);text=canonical(lesson['history'])
     reject='duplicate complete history' if text in seen_text else ('complete cross-split call/parameter overlap' if split!='train' and (signatures&train_calls or params in train_params) else None)
     if reject:refused.append(dict(doc_id=did,family=lesson['family'],split=split,group=group,reason=reject,target_tokens=targets));counts[split]['refused']+=1;cnt['refused']+=1;continue
     if used+targets>cap:
      refused.append(dict(doc_id=did,family=lesson['family'],split=split,group=group,reason='category cap closes at first overflow',target_tokens=targets,remaining=cap-used));closed=True;counts[split]['cap_boundary_lessons']+=1;cnt['cap_boundary_lessons']+=1;continue
     obs=collections.Counter(adapt['audit']['observation_sources']);assert set(obs)<={'offline fixture','synthetic recorded fixture'}
     if source=='session':assert [x['current_turn_calls'] for x in meta]==[2,2,0] and obs['offline fixture']==4 and not obs['synthetic recorded fixture']
     assert adapt['source_lesson_sha256']==did
     conn.execute('INSERT INTO documents VALUES('+','.join(['?']*17)+')',(did,text,lesson['family'],split,canonical(lesson),canonical(adapted),canonical(adapt['audit']),canonical(meta),canonical(calls[0]) if calls else None,len(meta),sum(x['input_tokens'] for x in meta),targets,sum(x['current_turn_calls']==0 for x in meta),obs['offline fixture'],obs['synthetic recorded fixture'],sum(not r['ok'] for r in adapt['audit']['replay_records']),canonical(task)))
     used+=targets;cnt['retained']+=1;cnt['retained_targets']+=targets;counts[split]['retained']+=1;counts[split]['retained_targets']+=targets;seen_text.add(text)
     if split=='train':train_calls|=signatures;train_params.add(params)
     for turn in adapt['turns']:
      for i,label in enumerate(turn['row'].labels):
       if label!=-100:exposure[split+'/'+str((i+1)//256)]+=1
     records.append(dict(doc_id=did,family=lesson['family'],split=split,group=group,index=task['index'],rank=rank,contrast_group=task['contrast_group'],variant=task['variant'],parameters=task['parameters'],targets=targets))
     if len(records)%32==0:conn.commit()
    conn.commit();cnt['target_cap']=cap;cnt['unused_targets']=cap-used
  assert all(sha(ROOT/p)==h for p,h in pins.items());assert conn.execute('pragma quick_check').fetchone()[0]=='ok'
 except Exception as e:conn.rollback();failure=dict(type=type(e).__name__,reason=str(e))
 finally:
  aggregate=[dict(split=s,lessons=n,rows=rows,input_tokens=inp,assistant_targets=targets,actual_observations=actual,replay_observations=replay,error_observations=errors) for s,n,rows,inp,targets,actual,replay,errors in conn.execute('select split,count(*),sum(rows),sum(input_tokens),sum(target_tokens),sum(actual_observations),sum(replay_observations),sum(error_observations) from documents group by split')];familycount=[dict(split=s,families=n) for s,n in conn.execute('select split,count(distinct family) from documents group by split')];conn.close()
 write(dest/'source-records.json',records);write(dest/'refused.json',refused)
 manifest=dict(state='partial_candidate_not_admitted' if failure else 'candidate_only_not_admitted',training_admitted=False,semantics_verified=False,failure=failure,database=dict(path=str(dest/'candidates.sqlite'),sha256=sha(dest/'candidates.sqlite'),bytes=(dest/'candidates.sqlite').stat().st_size),policy_sha256=sha(dest/'policy.json'),source_records_sha256=sha(dest/'source-records.json'),refused_sha256=sha(dest/'refused.json'),code_and_protocol=pins,tokenizer=assets,counts={k:dict(v) for k,v in counts.items()},category_counts={k:dict(v) for k,v in category_counts.items()},committed_aggregates=aggregate,retained_families=familycount,position_exposure=dict(exposure),split_relation=dict(family_overlap=0,retained_complete_call_and_parameter_tuple_overlap=0 if failure is None else 'not certified on partial failure'),seconds=time.monotonic()-start,limitations='Candidate-only authoring selfchecks; independent interpreter, natural-language review, root custody and independent framing reload required. No post-custody refill. Exact history duplicate check only; normalized phrase concentration reported separately before admission.')
 write(dest/'candidate-manifest.json',manifest);print(json.dumps({k:manifest[k] for k in ['state','failure','committed_aggregates','retained_families','seconds']}),flush=True)
 if failure:raise RuntimeError(failure)

def main():
 plan=json.loads((HERE/'PLAN.json').read_text())
 if plan['state']!='approved_for_candidate_generation':raise RuntimeError('prospective v2 requires root review before freeze and generation')
 os.nice(10);templates=json.loads((HERE/'templates.json').read_text());tok=load()
 for source in ['primary','session']:build(source,plan,templates,tok)
if __name__=='__main__':main()
