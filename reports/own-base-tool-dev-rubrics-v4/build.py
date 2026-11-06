"""Explicit family-registry compilation; never loads a model or private cases."""
import os
for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'):os.environ[k]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import ast,collections,hashlib,json,pathlib,re,resource,shutil,sqlite3,string,sys,time
from copy import deepcopy
R=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(R))
from own_base_dev_eval import prepare,fingerprint,resolve,answer_score
from own_base_tool_adapter import adapt_lesson,canonical
from tokenizer import load
D=R/'data/own-base-tool-dev-rubrics-v4';SRC=R/'data/own-base-tool-candidates';REPORT=pathlib.Path(__file__).parent
DISPLAY=dict(mode='python-significant',digits=9)

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_text())
def write(p,v):
 with pathlib.Path(p).open('x') as f:json.dump(v,f,indent=2,ensure_ascii=False);f.write('\n')
def registry():
 wanted={'INTERNAL_ARITHMETIC','INTERNAL_CONVERSIONS','INTERNAL_SPECIAL','UNIT_PAIRS'};values={}
 for node in ast.parse((R/'tool_teaching_varied.py').read_text()).body:
  if isinstance(node,ast.Assign):
   for target in node.targets:
    if isinstance(target,ast.Name) and target.id in wanted:values[target.id]=ast.literal_eval(node.value)
 assert values.keys()==wanted
 result={}
 def put(family,template,mode):
  key=family+'/'+hashlib.sha256(template.encode()).hexdigest()[:12]
  assert key not in result;result[key]=dict(template=template,mode=mode)
 for op,domains in values['INTERNAL_ARITHMETIC'].items():
  for domain,templates in domains.items():
   for template in templates:put(f'arith/{op}/{domain}',template,'arithmetic')
 for domain in values['UNIT_PAIRS']:
  for template in values['INTERNAL_CONVERSIONS']:put('convert/'+domain,template,'conversion')
 for mode,templates in values['INTERNAL_SPECIAL'].items():
  for template in templates:put('special/'+mode,template,mode)
 return result

def ref(t,c=0,field='result'):return {'ref':dict(turn=t,call=c,field=field)}
def outcome(t,c=0,unit=None,unitless=False):
 success=dict(mode='number',value=ref(t,c),display=deepcopy(DISPLAY))
 if unit is not None:success['unit']=unit
 if unitless:success['allow_unitless']=True
 return dict(mode='observed_status',observation=ref(t,c,'ok'),success=success,
             error=dict(mode='error',observation=ref(t,c,'ok')))
def template_match(template,text):
 pattern=''.join(re.escape(literal)+(r'.+?' if field is not None else '') for literal,field,_format,_conversion in string.Formatter().parse(template))
 suffixes=('', ' Use the offline fixture and tell me its observed result.', ' Quote what the fixture actually returns.', " Use the fixture's observed first value for the second step.")
 return any(re.fullmatch(pattern+re.escape(s),text,re.S) is not None for s in suffixes)
def source_turns(lesson):
 result=[]
 for msg in lesson['history']:
  if msg['role']=='user':result.append(dict(user=msg['text'],calls=[],answer=None))
  elif msg['role']=='assistant' and 'call' in msg:result[-1]['calls'].append(deepcopy(msg['call']))
  elif msg['role']=='assistant' and 'text' in msg:
   assert result[-1]['answer'] is None;result[-1]['answer']=msg['text']
  elif msg['role']!='tool':raise ValueError('unexpected source role')
 assert result and all(t['answer'] is not None for t in result) and len(result)==len(lesson['policy'])
 return result

def compile_lesson(lesson,did,reg):
 if lesson['family'] not in reg:raise ValueError('unregistered family')
 entry=reg[lesson['family']];mode=entry['mode'];source=source_turns(lesson)
 if not template_match(entry['template'],source[0]['user']):raise ValueError('registered first template mismatch')
 turns=[dict(user=t['user'],policy=deepcopy(lesson['policy'][i]),calls=deepcopy(t['calls']),answer=None) for i,t in enumerate(source)]
 def shape(counts):
  if [len(t['calls']) for t in turns]!=counts:raise ValueError('registered call/turn shape mismatch')
 def expect_call(t,c,name,op=None):
  call=turns[t]['calls'][c]
  if call['name']!=name or (op is not None and call['arguments'].get('op')!=op):raise ValueError('registered operation mismatch')
 def final(t):
  c=len(turns[t]['calls'])-1
  if c<0:raise ValueError('readback requires source proposal')
  unit=ref(t,c,'proposal_argument:to') if turns[t]['calls'][c]['name']=='convert' else None
  turns[t]['answer']=outcome(t,c,unit=unit)
 if mode in ('arithmetic','conversion'):
  if len(turns) not in (1,2) or len(turns[0]['calls'])!=1:raise ValueError('base turn shape')
  expect_call(0,0,'calculate' if mode=='arithmetic' else 'convert',lesson['family'].split('/')[1] if mode=='arithmetic' else None);final(0)
  if len(turns)==2:
   prompt=turns[1]['user']
   if prompt in ('What number did that tool report?','Remind me of its actual reading.','Repeat only the result already returned.'):
    shape([1,0]);turns[1]['answer']=outcome(0,unitless=mode=='conversion')
   elif prompt=='What was the first operand actually sent to the calculator?' and mode=='arithmetic':
    shape([1,0]);turns[1]['answer']=dict(mode='number',value=ref(0,0,'proposal_argument:a'),display=deepcopy(DISPLAY))
   elif prompt=='Which unit did I start with? Give its abbreviation.' and mode=='conversion':
    shape([1,0]);turns[1]['answer']=dict(mode='exact',value=ref(0,0,'proposal_argument:from'))
   elif re.fullmatch(r'Use the calculator to multiply that returned number by .+\.',prompt):
    shape([1,1]);expect_call(1,0,'calculate','multiply');turns[1]['calls'][0]['arguments']['a']=ref(0);final(1)
   else:raise ValueError('unregistered base followup prompt')
 elif mode.startswith('missing_'):
  shape([0,1]);turns[0]['answer']=dict(mode='manual',rubric='Ask only for the missing '+{'missing_divisor':'divisor','missing_start':'starting quantity','missing_target':'destination unit','missing_source':'source unit'}[mode]+'; do not invent a value or call a tool.');final(1)
  expected={'missing_divisor':('calculate','divide',r'Divide it by .+\.'),'missing_start':('calculate','subtract',r'I started with .+\.'),'missing_target':('convert',None,r'Use .+\.'),'missing_source':('convert',None,r'The source label is .+\.')}
  name,op,pattern=expected[mode];expect_call(1,0,name,op)
  if not re.fullmatch(pattern,turns[1]['user']):raise ValueError('clarification followup mismatch')
 elif mode=='permission_change':
  shape([0,1]);expect_call(1,0,'calculate','add')
  if turns[1]['user']!='Now you may use the calculator. Give me the sum.':raise ValueError('permission followup mismatch')
  turns[0]['answer']=dict(mode='manual',rubric='Identify addition/summing as the operation, without a tool call; equivalent operation names allowed.');final(1)
 elif mode=='no_call_expression':
  shape([0]);turns[0]['answer']=dict(mode='exact',value=source[0]['answer'])
 elif mode in ('no_call_after','paired_observation'):
  shape([1,0]);expect_call(0,0,'calculate','add' if mode=='no_call_after' else 'subtract');final(0);turns[1]['answer']=outcome(0)
  expected='Repeat the earlier result without using any tools.' if mode=='no_call_after' else 'What did that same fixture return? Do not use a tool.'
  if turns[1]['user']!=expected:raise ValueError('recall followup mismatch')
 elif mode=='correct_input':
  shape([1,1]);expect_call(0,0,'calculate','subtract');expect_call(1,0,'calculate','subtract')
  if not re.fullmatch(r'Correction: the starting amount was .+, but the deduction stays the same\.',turns[1]['user']):raise ValueError('correction prompt mismatch')
  final(0);final(1)
 elif mode in ('two_calls','convert_chain'):
  shape([2]);expect_call(0,0,'calculate' if mode=='two_calls' else 'convert','add' if mode=='two_calls' else None);expect_call(0,1,'calculate','divide' if mode=='two_calls' else 'multiply')
  if mode=='convert_chain' and turns[0]['calls'][1]['arguments']['b']!=2:raise ValueError('double factor mismatch')
  turns[0]['calls'][1]['arguments']['a']=ref(0,0)
  turns[0]['answer']=outcome(0,1,unit=ref(0,0,'proposal_argument:to') if mode=='convert_chain' else None)
 elif mode=='transient':
  if len(turns)!=2 or len(turns[0]['calls'])!=1:raise ValueError('transient shape')
  expect_call(0,0,'calculate','multiply');final(0)
  if turns[1]['user']=='Try that same call once more now.':
   shape([1,1]);expect_call(1,0,'calculate','multiply')
   turns[1]['calls'][0]['arguments']={key:ref(0,0,'proposal_argument:'+key) for key in ('op','a','b')};final(1)
  elif turns[1]['user']=='Was a numeric result returned? No tools.':
   shape([1,0]);turns[1]['answer']=dict(mode='observed_status',observation=ref(0,0,'ok'),
    success=dict(mode='manual',rubric='Affirm that the actual earlier observation returned a numeric result; no new tool call.'),
    error=dict(mode='error',observation=ref(0,0,'ok')))
  else:raise ValueError('transient followup mismatch')
 elif mode in ('zero_divisor','signed_conversion'):
  shape([1]);expect_call(0,0,'calculate' if mode=='zero_divisor' else 'convert','divide' if mode=='zero_divisor' else None)
  if mode=='zero_divisor' and turns[0]['calls'][0]['arguments']['b']!=0:raise ValueError('zero divisor mismatch')
  final(0)
 else:raise ValueError('unregistered family mode')
 if any(t['answer'] is None for t in turns):raise ValueError('missing rubric')
 case=dict(id=did,family=lesson['family'],turns=turns);prepare([case],fingerprint([case]));return case,source

def check(start):
 if time.time()-start>300:raise RuntimeError('300-second cap')
 if any(p.exists() for p in (R/'runs/STOP',R/'runs/own-base-foundation-01/STOP',D/'STOP')):raise RuntimeError('STOP')
 rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
 if rss>200*1024**2:raise RuntimeError('200 MiB RSS cap')
 if shutil.disk_usage(R).free<20*1024**3:raise RuntimeError('20 GiB disk floor')
 if D.exists() and sum(p.stat().st_size for p in D.iterdir() if p.is_file())>50*1024**2:raise RuntimeError('50 MiB output cap')
def pins():
 files=[pathlib.Path(__file__),REPORT/'PROTOCOL.md',D/'family-registry.json']+[SRC/n for n in ('candidates.sqlite','candidate-manifest.json','custody.json')]
 files +=[R/n for n in ('own_base_dev_eval.py','verify_own_base_dev_eval.py','data/own-base-tool-dev-rubrics-v3/freeze.json','data/own-base-tool-dev-rubrics-v3/receipt.json','data/own-base-tool-dev-rubrics-v3/review-finding.json','data/own-base-tool-dev-rubrics-v2/freeze.json','data/own-base-tool-dev-rubrics-v2/receipt.json','data/own-base-tool-dev-rubrics-v2/review-finding.json','data/own-base-tool-dev-rubrics-v1/freeze.json','data/own-base-tool-dev-rubrics-v1/failure.json','own_base_tool_adapter.py','own_base_chat.py','own_base_sft_rows.py','dialogue.py','tools/__init__.py','tokenizer.py','tool_teaching_varied.py','tool_teaching.py','data/tokenizer/encoder.json','data/tokenizer/vocab.bpe')]
 return {str(p.relative_to(R)):sha(p) for p in files}
def synthetic():
 reg=registry();tested=set()
 for family,entry in reg.items():
  mode=entry['mode']
  if mode in tested or mode not in {'arithmetic','conversion','two_calls','convert_chain','transient','missing_divisor','permission_change','zero_divisor','signed_conversion'}:continue
  first=entry['template'].format(a='six',b='two',z='two',s='metres',d='centimetres',neg='minus two',v='six',s_plural='metres')
  calc=lambda op,a,b:dict(name='calculate',arguments=dict(op=op,a=a,b=b))
  conv=dict(name='convert',arguments={'value':6,'from':'m','to':'cm'})
  calls=[calc(family.split('/')[1],6,2)] if mode=='arithmetic' else [conv]
  user_calls=[(first,calls)]
  if mode=='two_calls':user_calls=[(first,[calc('add',6,2),calc('divide',8,2)])]
  if mode=='convert_chain':user_calls=[(first,[conv,calc('multiply',600,2)])]
  if mode=='transient':user_calls=[(first,[calc('multiply',6,2)]),('Try that same call once more now.',[calc('multiply',6,2)])]
  if mode=='missing_divisor':user_calls=[(first,[]),('Divide it by two.',[calc('divide',6,2)])]
  if mode=='permission_change':user_calls=[(first,[]),('Now you may use the calculator. Give me the sum.',[calc('add',6,2)])]
  if mode=='zero_divisor':user_calls=[(first,[calc('divide',6,0)])]
  history=[];policy=[]
  for user,cs in user_calls:
   history.append(dict(role='user',text=user));policy.append(dict(permit_calls=bool(cs),fixture_for=None,fixture=None))
   for c in cs:history.append(dict(role='assistant',call=c));history.append(dict(role='tool',result={}))
   history.append(dict(role='assistant',text='Synthetic reference'))
  compile_lesson(dict(family=family,history=history,policy=policy,observations=[]),'synthetic',reg);tested.add(mode)
 assert len(tested)==9
 print('PASS nine representative synthetic compiler families')
def build():
 freeze=read(D/'freeze.json');start=freeze['started'];check(start);assert pins()==freeze['pins']
 custody=read(SRC/'custody.json');manifest=read(SRC/'candidate-manifest.json')
 assert sha(SRC/'candidates.sqlite')==custody['pins']['candidates.sqlite']==manifest['database']['sha256']
 assert sha(SRC/'candidate-manifest.json')==custody['pins']['candidate-manifest.json']
 ex=set(custody['excluded_doc_ids']);reg=read(D/'family-registry.json');tok=load();cases=[];sources=[];counts=collections.Counter();manual=0;automated=0
 con=sqlite3.connect(f'file:{SRC}/candidates.sqlite?mode=ro',uri=True);con.execute('PRAGMA cache_size=-1024')
 for did,family,raw,rows in con.execute("SELECT doc_id,family,original_lesson_json,rows FROM documents WHERE split='exposed-development' ORDER BY doc_id"):
  check(start)
  if did in ex:continue
  lesson=json.loads(raw);assert lesson['family']==family and hashlib.sha256(canonical(lesson).encode()).hexdigest()==did
  case,source=compile_lesson(lesson,did,reg);adapted=adapt_lesson(lesson,tok);assert rows==len(case['turns'])==len(adapted['turns'])
  observations=[];proposals=[];cursor=0
  for ti,(turn,authored,adapted_turn) in enumerate(zip(case['turns'],source,adapted['turns'])):
   assert turn['policy']==adapted_turn['policy'] and turn['user']==authored['user']
   n=len(authored['calls']);observations.append(adapted['audit']['replay_records'][cursor:cursor+n]);cursor+=n;proposals.append(authored['calls'])
   for ci,call in enumerate(turn['calls']):
    actual=dict(name=call['name'],arguments={k:resolve(v,observations,proposals) for k,v in call['arguments'].items()});assert actual==authored['calls'][ci]
   verdict=answer_score(turn['answer'],authored['answer'],observations,proposals)
   if verdict is None:manual+=1
   elif verdict is True:automated+=1
   else:raise ValueError('source reference answer failed for '+did+' turn '+str(ti)+' mode '+turn['answer']['mode'])
  cases.append(case);counts[reg[family]['mode']]+=1
  sources.append(dict(doc_id=did,original_lesson_sha256=did,family=family,turns=rows,source_reference_checks='automated-pass-or-manual-pending'))
 assert len(cases)==422;prepare(cases,fingerprint(cases));assert pins()==freeze['pins'];check(start)
 write(D/'cases.json',cases);write(D/'source-map.json',sources)
 receipt=dict(state='compiled_exposed_development_rubrics_not_model_evaluated',cases=422,turns=sum(len(c['turns']) for c in cases),automated_source_reference_passes=automated,manual_pending_source_turns=manual,families=dict(counts),cases_canonical_sha256=fingerprint(cases),cases_file_sha256=sha(D/'cases.json'),source_map_sha256=sha(D/'source-map.json'),freeze_sha256=sha(D/'freeze.json'),seconds=time.time()-start,model_evaluated=False,training_admitted=False,semantic_quality_certified=False)
 write(D/'receipt.json',receipt);print(json.dumps(receipt,indent=2))
if __name__=='__main__':
 os.nice(10);mode=sys.argv[1]
 if mode=='self-test':synthetic()
 elif mode=='freeze':
  D.mkdir(parents=True,exist_ok=True);start=time.time();check(start);write(D/'family-registry.json',registry());write(D/'freeze.json',dict(started=start,pins=pins()))
 elif mode=='build':
  try:build()
  except Exception as error:
   write(D/'failure.json',dict(state='failed_preparation_not_evaluated',error_type=type(error).__name__,error=str(error)));raise
 else:raise ValueError('mode')
