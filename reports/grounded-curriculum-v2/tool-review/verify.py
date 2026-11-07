"""Independent finite-domain tool candidate verification; no author/helper imports.
CPU only. Reads no private or evaluation cases. Uses reviewed frozen templates as
syntax, independent state programs, Fraction math, actual offline broker replay,
and separately reconstructed framing/masks. Does not admit training data.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[k]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import collections,copy,hashlib,json,math,pathlib,random,re,sqlite3,string,sys,time
from fractions import Fraction
ROOT=pathlib.Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tokenizer import load,ASSETS
from tools import FixtureSession
HERE=pathlib.Path(__file__).resolve().parent
AUTHOR=ROOT/'reports/grounded-curriculum-v2/tools'
OPERATIONS=['add','subtract','multiply','divide']
SYMBOL=dict(zip(OPERATIONS,['+','-','*','/']))
SCALE={'mm':Fraction(1,1000),'cm':Fraction(1,100),'m':Fraction(1),'km':Fraction(1000),'g':Fraction(1),'kg':Fraction(1000),'ml':Fraction(1),'l':Fraction(1000),'s':Fraction(1),'min':Fraction(60),'h':Fraction(3600),'day':Fraction(86400)}
PAIRS=[p for a,b in [('mm','cm'),('cm','m'),('m','km'),('g','kg'),('ml','l'),('s','min'),('min','h'),('h','day')] for p in [(a,b),(b,a)]]
NUM=r'[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?'

def cj(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def digest(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def hashed(v):return hashlib.sha256(cj(v).encode()).hexdigest()
def require(ok,message):
 if not ok:raise AssertionError(message)
def stable(v):return {k:x for k,x in v.items() if k!='timestamp'}
def number(v):return str(int(v)) if int(v)==v else str(v)
def calc(op,a,b):return {'name':'calculate','arguments':{'op':op,'a':a,'b':b}}
def convert(a,src,dst):return {'name':'convert','arguments':{'value':a,'from':src,'to':dst}}

def derive_parameters(plan,form,index):
 block,variant=divmod(index,4)
 seed=int(hashlib.sha256(cj([plan['seed'],form['family'],block]).encode()).hexdigest(),16)
 rng=random.Random(seed);lo,hi=plan['parameter_domains']['train_absolute_a' if form['split']=='train' else 'development_absolute_a'];fr=plan['parameter_domains']['fractions']
 p={'a':rng.choice([-1,1])*(rng.randint(lo,hi)+rng.choice(fr)), 'b':rng.choice([-1,1])*(rng.randint(13,41)+rng.choice([0,.5])), 'c':rng.randint(3,9),'d':rng.choice([-1,1])*(rng.randint(43,97)+rng.choice(fr))}
 if form['kind'] in ['conversion','clarify_unit','chain_convert','convert']:p['a']=abs(p['a'])
 if variant in [2,3] and form['kind']!='observation':p['a' if variant==2 else 'b']+=.25
 op=OPERATIONS[(block+(variant==1 and form['kind']!='observation'))%4];op2=OPERATIONS[(block+2)%4];src,dst=PAIRS[block%16]
 return p,block,variant,op,op2,src,dst,block%2

def check_math(call,record,fixture):
 a=call['arguments']
 if fixture is not None:
  require(record['source']=='synthetic recorded fixture','fixture provenance')
  if 'error' in fixture:require(not record['ok'] and record['error']==fixture['error'],'fixture error')
  else:require(record['ok'] and record['data']['result']==fixture['result'],'fixture number')
  return
 require(record['source']=='offline fixture','ordinary provenance')
 if call['name']=='calculate':
  x,y=Fraction(str(a['a'])),Fraction(str(a['b']))
  if a['op']=='divide' and y==0:
   require(not record['ok'] and record['error']=='division by zero','zero failure');return
  exact={'add':lambda:x+y,'subtract':lambda:x-y,'multiply':lambda:x*y,'divide':lambda:x/y}[a['op']]()
 else:exact=Fraction(str(a['value']))*SCALE[a['from']]/SCALE[a['to']]
 require(record['ok'] and math.isclose(float(exact),record['data']['result'],rel_tol=1e-12,abs_tol=1e-12),'independent Fraction arithmetic')

def oracle(plan,templates,source,form,index):
 """Derive finite reviewed instruction programs, then independently execute them."""
 p,block,variant,op,op2,src,dst,fi=derive_parameters(plan,form,index);kind=form['kind'];ops=form.get('operations')
 values={k:number(v) for k,v in p.items()};values.update(op=op,op2=op2,symbol=SYMBOL[op],symbol2=SYMBOL[op2],verb={'add':'add','subtract':'subtract','multiply':'multiply by','divide':'divide by'}[op],verb2={'add':'add','subtract':'subtract','multiply':'multiply by','divide':'divide by'}[op2],src=src,dst=dst)
 if source=='session':values.update(op=ops[0],op2=ops[1],op3=ops[2],op4=ops[3],symbol=SYMBOL.get(ops[0]),symbol2=SYMBOL[ops[1]],symbol3=SYMBOL[ops[2]],symbol4=SYMBOL[ops[3]],e=number(p['a']+.5))
 first=form['forms'][fi].format(**values);common=templates['common_templates'];program=[]
 def step(prompt,calls,answer='read',fixture=None,permit=True,unit=None,wrapper=False):program.append(dict(prompt=prompt,calls=calls,answer=answer,fixture=fixture,permit=permit,unit=unit,wrapper=wrapper))
 # Calls with left operand 'last' explicitly consume the latest observed result.
 c0=calc(op,p['a'],p['b']);wrap=index%2==0
 if source=='session':
  step(first,[convert(p['a'],src,dst) if kind=='convert' else calc(ops[0],p['a'],p['b']),calc(ops[1],'last',p['c'])])
  step(common['session_second'][index%2].format(**values),[calc(ops[2],'last',p['d']),calc(ops[3],'last',p['b'])])
  mode=['recall','recap','correction'][index%3];step(common['session_final'][mode].format(**values),[],answer=mode,permit=False)
 elif kind=='arithmetic':step(first,[c0],wrapper=wrap)
 elif kind=='conversion':step(first,[convert(p['a'],src,dst)],unit=dst,wrapper=wrap)
 elif kind in ['chain_calc','chain_convert']:step(first,[c0 if kind=='chain_calc' else convert(p['a'],src,dst),calc(op2,'last',p['c'])],wrapper=wrap)
 elif kind=='observation':
  fixture=None if variant==0 else ({'error':'fixture timeout'} if variant==3 else {'result':p['a']+p['d']+(17 if variant==1 else -23)})
  step(first,[c0],fixture=fixture,wrapper=wrap);step(common['followup_observation'][block%2],[],permit=False)
 elif kind=='correction':step(first,[c0],wrapper=wrap);step(common['correction'][block%2].format(**values),[calc(op,p['d'],p['b'])],wrapper=not wrap)
 elif kind=='retry':step(first,[c0],fixture={'error':'fixture timeout'});step(common['retry'][block%2],[c0],wrapper=wrap)
 elif kind=='clarify':step(first,[],answer='missing_operand',permit=False);step('The second operand is '+number(p['b'])+'. Execute the original operation.',[c0],wrapper=wrap)
 elif kind=='clarify_unit':step(first,[],answer='missing_unit',permit=False);step('Use '+dst+' as the destination. Execute the conversion.',[convert(p['a'],src,dst)],unit=dst,wrapper=wrap)
 elif kind=='denied':step(first,[],answer='disabled',permit=False)
 elif kind=='zero':step(first,[calc('divide',p['a'],0)])
 elif kind=='expression':step(first,[],answer='literal_expression',permit=False)
 elif kind=='operation':step(first,[],answer='operation_name',permit=False)
 else:raise AssertionError('unreviewed kind '+kind)
 broker=FixtureSession();history=[];policies=[];observations=[];derived=[]
 for instruction in program:
  fixture=instruction['fixture'];policy={'permit_calls':instruction['permit'],'fixture_for':instruction['calls'][0] if fixture is not None else None,'fixture':fixture};policies.append(policy);broker.start_turn(**policy)
  history.append({'role':'user','text':instruction['prompt']});executed=[]
  for rawcall in instruction['calls']:
   call=copy.deepcopy(rawcall)
   if call['arguments'].get('a')=='last':call['arguments']['a']=observations[-1]['data']['result']
   observed=stable(broker.propose(cj(call),assistant_call_boundary=True));check_math(call,observed,fixture);require(broker.decisions[-1]['dispatched'],'expected dispatched')
   observations.append(observed);executed.append({'proposal':call,'observation':observed});projection={'name':observed['name'],'id':observed['call_id'],'result':observed['data']['result']} if observed['ok'] else {'id':observed['call_id'],'error':observed['error']}
   history.extend([{'role':'assistant','call':call},{'role':'tool','result':projection}])
  rule=instruction['answer'];rulemeta=None
  if rule=='read':
   last=observations[-1]
   if not last['ok']:
    answer='The calculator failed: division by zero.' if last['error']=='division by zero' else 'The tool failed; no numeric result was returned.';rulemeta={'kind':'error','error':last['error']}
   else:
    atom=number(last['data']['result'])+(' '+instruction['unit'] if instruction['unit'] else '')
    answer=('The tool returned '+atom+'.') if instruction['wrapper'] else atom;rulemeta={'kind':'last_observation','unit':instruction['unit'],'wrapper':instruction['wrapper']}
  elif rule in ['recall','recap','correction']:
   outputs=[r['data']['result'] for r in observations]
   if rule=='recall':answer='Initial value was '+number(p['a'])+'; final record was '+number(outputs[-1])+'.'
   elif rule=='recap':answer='The returns were '+', '.join(number(x) for x in outputs[:3])+', and '+number(outputs[-1])+'.'
   else:answer='Initial value is now '+number(p['a']+.5)+'; final record remains '+number(outputs[-1])+'.'
   rulemeta={'kind':rule,'original':p['a'],'corrected':p['a']+.5,'observations':outputs}
  else:
   answer={'missing_operand':'What is the second operand?','missing_unit':'What destination unit should I use?','disabled':'Tool calls are disabled; I cannot execute this request.','literal_expression':'('+number(p['a'])+') '+SYMBOL[op]+' ('+number(p['b'])+')','operation_name':dict(zip(OPERATIONS,['Addition.','Subtraction.','Multiplication.','Division.']))[op]}[rule]
   rulemeta={'kind':rule}
   if rule in ['literal_expression','operation_name']:rulemeta['op']=op
  history.append({'role':'assistant','text':answer});derived.append({'user':instruction['prompt'],'policy':policy,'calls':executed,'answer_rule':rulemeta})
 lesson={'family':form['family'],'history':history,'observations':observations,'policy':policies}
 task={'parameters':p,'contrast_group':block,'variant':variant,'op':op,'op2':op2,'src':src,'dst':dst,'form_index':fi,'kind':kind,'family':form['family'],'split':form['split'],'group':mode if source=='session' else form['group'],'index':index,'turns':derived}
 if source=='session':task['operations']=ops
 if kind=='observation':task.update(fixture_mode='ordinary' if program[0]['fixture'] is None else 'synthetic_recorded',fixture=program[0]['fixture'])
 return lesson,task,broker

POLICY_PREFIX=('Host policy for the current user turn; prior tool records may reflect earlier permissions. '
'Tools are offline calculator/conversion fixtures, not external services. '
'Use actual observed tool records when answering. Return exactly one JSON object: '
'{"text":"your answer"} or {"call":{"name":"tool name","arguments":{...}}}. '
'End the frame with EOT. Current policy: ')
def host_policy(permit):
 schemas={'calculate':{'arguments':['op','a','b'],'operations':sorted(OPERATIONS)},'convert':{'arguments':['value','from','to'],'units':sorted(SCALE)}} if permit else {}
 return POLICY_PREFIX+cj({'permit_calls':permit,'allowed_tools':['calculate','convert'] if permit else [],'calls_per_turn':2,'calls_per_session':4,'tools':schemas})

class FitError(Exception):pass

def frames(tok,history):
 """Independent raw frame tokenizer and last-user masking; no dialogue imports."""
 raw=[];flags=[];last_user=0;prefixes=[];state='user';pending=None;used=set()
 for i,message in enumerate(history):
  role=message['role'];require(role==state or (i==0 and role=='system'),'frame role transition')
  if role=='user':last_user=len(raw)
  if role=='assistant' and 'call' in message:
   require(set(message)=={'role','call','call_id'} and message['call_id'] not in used,'call linkage');used.add(message['call_id']);pending=(message['call_id'],message['call']);payload={'call':message['call']};state='tool'
  elif role=='tool':
   payload=message['record'];require(payload['call_id']==pending[0] and payload['name']==pending[1]['name'],'record linkage');state='assistant'
  else:payload={'text':message['text']};state='assistant' if role=='user' else 'user'
  header=tok.encode('['+role+']\n').ids;body=tok.encode(cj(payload).replace('<','\\u003c').replace('>','\\u003e')).ids+[50256]
  require(50256 not in body[:-1],'embedded terminator')
  if role=='assistant':
   prefix=len(raw)+len(header)
   if prefix+256>1024 or not 0<len(body)<=256:raise FitError('reply reservation')
   prefixes.append((prefix,len(body)))
  raw+=header+body;flags += [False]*len(header)+[role=='assistant']*len(body)
 require(state=='user','incomplete history')
 if not 0<len(raw)-1<=1024:raise FitError('context')
 inputs=raw[:-1];labels=[t if flags[pos] and pos>=last_user else -100 for pos,t in enumerate(raw[1:],1)]
 require(any(x!=-100 for x in labels),'empty mask')
 return inputs,labels,prefixes

def independently_adapt(tok,lesson):
 cumulative=[];observation=0;turn=-1;meta=[];adapted=[];rows=[];exposure=collections.Counter();current_calls=0
 def finish():
  if turn<0:return
  history=[{'role':'system','text':host_policy(lesson['policy'][turn]['permit_calls'])}]+copy.deepcopy(cumulative)
  inputs,labels,prefix=frames(tok,history);rows.append((inputs,labels));meta.append({'turn_index':turn,'input_tokens':len(inputs),'assistant_targets':sum(x!=-100 for x in labels),'current_turn_calls':current_calls});adapted.append({'turn_index':turn,'history':history,'policy':lesson['policy'][turn]})
  for i,label in enumerate(labels):
   if label!=-100:exposure[str((i+1)//256)]+=1
 for message in lesson['history']:
  if message['role']=='user':finish();turn+=1;current_calls=0;cumulative.append(message)
  elif 'call' in message:
   record=lesson['observations'][observation];cumulative.append({'role':'assistant','call':message['call'],'call_id':record['call_id']});current_calls+=1
  elif message['role']=='tool':cumulative.append({'role':'tool','record':lesson['observations'][observation]});observation+=1
  else:cumulative.append(message)
 finish();return adapted,meta,rows,exposure

def verify_source(source,plan,templates,tok):
 started=time.monotonic();dest=ROOT/plan['sources'][source]['output'];manifest=json.loads((dest/'candidate-manifest.json').read_text());policy=json.loads((dest/'policy.json').read_text());config=plan['sources'][source]
 require(manifest['state']=='candidate_only_not_admitted' and manifest['failure'] is None and not manifest['training_admitted'],'complete candidate state')
 require(digest(dest/'candidates.sqlite')==manifest['database']['sha256'],'database hash')
 require(digest(dest/'policy.json')==manifest['policy_sha256'],'policy hash')
 require(digest(dest/'source-records.json')==manifest['source_records_sha256'] and digest(dest/'refused.json')==manifest['refused_sha256'],'record/refusal hash')
 require(policy['plan']==plan and policy['source']==source and policy['state']=='frozen_before_instances','prospective policy')
 require(policy['templates_sha256']==digest(AUTHOR/'templates.json'),'template hash')
 require(manifest['code_and_protocol']==policy['code_and_protocol'],'pin agreement')
 for path,pin in policy['code_and_protocol'].items():require(digest(ROOT/path)==pin,'code pin '+path)
 require(policy['tokenizer']==manifest['tokenizer']==ASSETS,'tokenizer declaration')
 for path,pin in ASSETS.items():require(digest(ROOT/'data/tokenizer'/path)==pin,'tokenizer file')
 db=sqlite3.connect(f'file:{dest/"candidates.sqlite"}?mode=ro',uri=True);db.row_factory=sqlite3.Row
 require(db.execute('pragma integrity_check').fetchone()[0]=='ok','SQLite integrity')
 stored={r['doc_id']:dict(r) for r in db.execute('select * from documents')};db.close()
 forms=templates['primary' if source=='primary' else 'session'];family_splits=collections.defaultdict(set)
 for form in forms:family_splits[form['family']].add(form['split']);require(len(form['forms'])==2 and form['forms'][0]!=form['forms'][1],'two distinct forms')
 require(all(len(v)==1 for v in family_splits.values()),'family split')
 pool=[];expected_counts=collections.defaultdict(collections.Counter);category=collections.defaultdict(collections.Counter)
 for form in forms:
  for index in range(config['instances_per_family'][form['split']]):
   lesson,task,broker=oracle(plan,templates,source,form,index);did=hashed(lesson);rank=hashed([plan['seed'],source,form['split'],task['group'],did]);pool.append((form['split'],task['group'],rank,did,lesson,task,broker));expected_counts[form['split']]['generated_lessons']+=1
 retained=[];refused=[];seen=set();train_calls=set();train_params=set();verified=set();exposure=collections.Counter();coverage=collections.defaultdict(set);checks=collections.Counter();frame_digest=hashlib.sha256();familyforms=collections.defaultdict(set);remaining={}
 for split in ['train','exposed-development']:
  for group,percent in config['group_percent'].items():
   cap=config['caps'][split]*percent//100;used=0;closed=False;cnt=category[split+'/'+group]
   for _,_,rank,did,lesson,task,broker in sorted((x for x in pool if x[:2]==(split,group)),key=lambda x:x[2]):
    cnt['generated']+=1
    if closed:expected_counts[split]['not_scanned_after_cap']+=1;cnt['not_scanned_after_cap']+=1;continue
    try:adapted,meta,rows,exp=independently_adapt(tok,lesson)
    except FitError:
     # Keep exact builder reason outside our independent serializer; identities
     # and fit-failure membership are checked below, not implementation wording.
     refused.append({'doc_id':did,'family':lesson['family'],'split':split,'group':group,'reason_class':'fit'});expected_counts[split]['refused']+=1;cnt['refused']+=1;continue
    targets=sum(x['assistant_targets'] for x in meta);expected_counts[split]['fitted_targets_before_selection']+=targets;cnt['fitted_targets_before_selection']+=targets
    calls=[m['call'] for m in lesson['history'] if 'call' in m];signatures={cj(x) for x in calls};params=cj(task['parameters']);text=cj(lesson['history'])
    reason='duplicate complete history' if text in seen else ('complete cross-split call/parameter overlap' if split!='train' and (signatures & train_calls or params in train_params) else None)
    if reason:refused.append({'doc_id':did,'family':lesson['family'],'split':split,'group':group,'reason':reason,'target_tokens':targets});expected_counts[split]['refused']+=1;cnt['refused']+=1;continue
    if used+targets>cap:
     refused.append({'doc_id':did,'family':lesson['family'],'split':split,'group':group,'reason':'category cap closes at first overflow','target_tokens':targets,'remaining':cap-used});closed=True;expected_counts[split]['cap_boundary_lessons']+=1;cnt['cap_boundary_lessons']+=1;continue
    require(did in stored,'independently selected row missing '+did);row=stored[did];verified.add(did)
    require(row['family']==lesson['family'] and row['split']==split and row['text']==text,'row identity/text')
    require(json.loads(row['original_lesson_json'])==lesson,'full original lesson differs from independently derived program')
    require(json.loads(row['task_json'])==task,'typed task differs from independently derived program')
    require(json.loads(row['adapted_json'])==adapted,'whole-history adapted content')
    require(json.loads(row['row_metadata_json'])==meta,'independent framing metadata')
    require(row['rows']==len(meta) and row['input_tokens']==sum(x['input_tokens'] for x in meta) and row['target_tokens']==targets,'framing totals')
    require(row['first_call_signature']==(cj(calls[0]) if calls else None),'first call signature')
    require(row['no_call_rows']==sum(x['current_turn_calls']==0 for x in meta),'no-call total')
    if source=='session':require([m['current_turn_calls'] for m in meta]==[2,2,0],'full four-call trajectory')
    audit=json.loads(row['audit_json']);require(audit['original']==lesson and [stable(x) for x in audit['replay_records']]==lesson['observations'],'audit original/observations');require(audit['decisions']==broker.decisions,'broker dispatch decisions');require(audit['observation_sources']==[x['source'] for x in lesson['observations']],'audit provenance')
    for result in audit['replay_records']:require(isinstance(result['timestamp'],(float,int)) and math.isfinite(result['timestamp']),'audit timestamp')
    sources=collections.Counter(x['source'] for x in lesson['observations']);require(row['actual_observations']==sources['offline fixture'] and row['replay_observations']==sources['synthetic recorded fixture'] and row['error_observations']==sum(not x['ok'] for x in lesson['observations']),'observation counts')
    # Independent numeric literal extraction protects against accidental shared
    # serializer rounding even if reviewed answer templates are also compared.
    answers=[m['text'] for m in lesson['history'] if m['role']=='assistant' and 'text' in m];prior=[]
    for turn,answer in zip(task['turns'],answers):
     prior.extend(x['observation'] for x in turn['calls']);rule=turn['answer_rule']['kind'];expected=None
     if rule=='last_observation':expected=[prior[-1]['data']['result']]
     elif rule=='recall':expected=[task['parameters']['a'],prior[-1]['data']['result']]
     elif rule=='recap':expected=[x['data']['result'] for x in prior]
     elif rule=='correction':expected=[task['parameters']['a']+.5,prior[-1]['data']['result']]
     if expected is not None:
      numeric=[Fraction(x.group()) for x in re.finditer(NUM,answer)];require(numeric==[Fraction(str(x)) for x in expected],'exact observed-number readback');checks['exact_numeric_answers']+=1
    for call in calls:
     if call['name']=='convert':coverage[split].add((call['arguments']['from'],call['arguments']['to']))
    familyforms[task['family']].add(task['form_index']);checks['histories']+=1;checks['turns']+=len(meta);checks['observations']+=len(calls);checks['synthetic_observations']+=row['replay_observations'];checks['error_observations']+=row['error_observations']
    for inputs,labels in rows:frame_digest.update(cj({'inputs':inputs,'labels':labels}).encode());checks['masked_targets']+=sum(x!=-100 for x in labels)
    used+=targets;cnt['retained']+=1;cnt['retained_targets']+=targets;expected_counts[split]['retained']+=1;expected_counts[split]['retained_targets']+=targets;seen.add(text)
    if split=='train':train_calls |= signatures;train_params.add(params)
    exposure.update({split+'/'+k:v for k,v in exp.items()})
    retained.append({'doc_id':did,'family':lesson['family'],'split':split,'group':group,'index':task['index'],'rank':rank,'contrast_group':task['contrast_group'],'variant':task['variant'],'parameters':task['parameters'],'targets':targets})
   cnt['target_cap']=cap;cnt['unused_targets']=cap-used
 require(verified==set(stored),'unexpected or unverified retained rows')
 require(json.loads((dest/'source-records.json').read_text())==retained,'fixed selection source records')
 actual_refused=json.loads((dest/'refused.json').read_text());require(len(actual_refused)==len(refused),'refusal count')
 for actual,expected in zip(actual_refused,refused):
  if expected.get('reason_class')=='fit':
   require(actual['reason'].startswith('whole_history_fit_or_replay: '),'fit refusal class');require({k:v for k,v in actual.items() if k!='reason'}=={k:v for k,v in expected.items() if k!='reason_class'},'fit refusal identity')
  else:require(actual==expected,'independent refusal/first-overflow boundary')
 require({k:dict(v) for k,v in expected_counts.items()}==manifest['counts'],'complete pool/selection counters')
 require({k:dict(v) for k,v in category.items()}==manifest['category_counts'],'category counters')
 require(dict(exposure)==manifest['position_exposure'],'position exposure')
 require(all(expected_counts[split]['retained_targets']<=config['caps'][split] for split in expected_counts),'target ceilings')
 require(all(len(forms)==2 for forms in familyforms.values()),'both wording forms actually retained per family')
 aggregates=[];familycounts=[]
 for split in sorted(expected_counts):
  subset=[r for r in stored.values() if r['split']==split];aggregates.append(dict(split=split,lessons=len(subset),rows=sum(r['rows'] for r in subset),input_tokens=sum(r['input_tokens'] for r in subset),assistant_targets=sum(r['target_tokens'] for r in subset),actual_observations=sum(r['actual_observations'] for r in subset),replay_observations=sum(r['replay_observations'] for r in subset),error_observations=sum(r['error_observations'] for r in subset)));familycounts.append(dict(split=split,families=len({r['family'] for r in subset})))
 require(aggregates==manifest['committed_aggregates'] and familycounts==manifest['retained_families'],'aggregate totals')
 require(manifest['split_relation']=={'family_overlap':0,'retained_complete_call_and_parameter_tuple_overlap':0},'split declaration')
 # Coverage is descriptive; fixed cap selection must never be refilled to repair it.
 result={'state':'PASS_independent_grounded_candidates_not_admitted','scope':'Independent exhaustive finite authored-domain semantic, exact-readback, broker, Fraction, framing, masks, deterministic whole-pool selection and split verification; not arbitrary language entailment or training admission.','database_sha256':digest(dest/'candidates.sqlite'),'manifest_sha256':digest(dest/'candidate-manifest.json'),'verified_rows':len(stored),'failures':[],'policy_sha256':digest(dest/'policy.json'),'verifier_sha256':digest(__file__),'surface_review_sha256':digest(HERE/'SURFACE-REVIEW.md'),'counts':dict(checks),'reconstructed_frame_stream_sha256':frame_digest.hexdigest(),'conversion_directions':{k:sorted(v) for k,v in coverage.items()},'actual_family_form_counts':{k:len(v) for k,v in familyforms.items()},'seconds':time.monotonic()-started,'custody':'pending legacy/private plus exposed-development exclusion union; no custody case access by verifier','limitations':['Finite reviewed templates and operation programs, not arbitrary prose entailment.','Arithmetic uses Fraction checks with float tolerance; readback literals exactly match observations with no tolerance.','Train/development share mathematical primitives; family labels indicate wording/composition separation, not unseen mathematical skills.','Root custody and final admission remain required; no training or model-quality claim.']}
 with (dest/'candidate-verification.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
 return result

def main():
 os.nice(10);plan=json.loads((AUTHOR/'PLAN.json').read_text());templates=json.loads((AUTHOR/'templates.json').read_text());require(plan['state']=='approved_for_candidate_generation','root-approved plan');tok=load();results=[]
 review=json.loads((HERE/'surface-review-pins.json').read_text());require(review['templates_sha256']==digest(AUTHOR/'templates.json'),'reviewed templates pin');require(review['review_sha256']==digest(HERE/'SURFACE-REVIEW.md'),'review text pin')
 for source in ['primary','session']:
  try:result=verify_source(source,plan,templates,tok);results.append(result);print(cj({'source':source,'state':result['state'],'verified_rows':result['verified_rows'],'counts':result['counts'],'seconds':result['seconds']}),flush=True)
  except Exception as e:
   report={'state':'FAIL_independent_candidate_verification','source':source,'error':type(e).__name__+': '+str(e),'verifier_sha256':digest(__file__)}
   with (HERE/('failure-'+source+'-'+str(time.time_ns())+'.json')).open('x') as f:json.dump(report,f,indent=2)
   raise
 if results:
  with (HERE/'verification-summary.json').open('x') as f:json.dump(results,f,indent=2)
if __name__=='__main__':main()
