"""Eight frozen public-development sessions; no model or private-case loading."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import hashlib,json,pathlib,resource,shutil,sqlite3,sys,time
from copy import deepcopy
R=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(R))
D=R/'data/own-base-tool-session-dev-rubrics-v2';S=R/'data/own-base-tool-session-extension-v1';HERE=pathlib.Path(__file__).parent
from own_base_dev_eval import prepare,fingerprint,resolve,run
from own_base_chat import Chat
from tokenizer import load

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return h.hexdigest()
def read(path):return json.loads(path.read_text())
def canon(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
def write(path,value):
 with path.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n')
def check(start):
 assert time.time()-start<300,'time cap'
 assert not any(p.exists() for p in (R/'runs/STOP',R/'runs/own-base-foundation-01/STOP',D/'STOP')),'STOP'
 assert resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)<=200*1024**2,'RSS'
 assert shutil.disk_usage(R).free>=20*1024**3,'disk floor'
 assert sum(p.stat().st_size for p in D.iterdir() if p.is_file())<=50*1024**2,'output cap'
def pins():
 paths=[S/n for n in ('candidates.sqlite','candidate-manifest.json','custody.json','symbolic-verification.json','source-records.json','policy.json')]
 paths += [R/n for n in ('own_base_dev_eval.py','verify_own_base_dev_eval.py','own_base_chat.py','own_base_tool_adapter.py','own_base_sft_rows.py','dialogue.py','tools/__init__.py','tokenizer.py','data/tokenizer/encoder.json','data/tokenizer/vocab.bpe')]
 paths += [HERE/'build.py',HERE/'PROTOCOL.md',R/'reports/own-base-tool-session-extension-v1/build.py',R/'reports/own-base-tool-session-extension-v1/verify_symbolic.py',R/'reports/own-base-tool-session-extension-v1/PROTOCOL.md']
 paths += [R/'data/own-base-tool-session-dev-rubrics-v1'/n for n in ('cases.json','receipt.json','freeze.json','source-controls.json')]
 return {str(p.relative_to(R)):sha(p) for p in paths}
def ref(turn,call=0):return {'ref':dict(turn=turn,call=call,field='result')}
def calc(op,a,b):return dict(name='calculate',arguments=dict(op=op,a=a,b=b))
def conv(value,source,destination):return dict(name='convert',arguments={'value':value,'from':source,'to':destination})
def compile_case(lesson,source,forms):
 p=source['parameters'];form=forms[lesson['family'].split('/')[1]]
 _,u1,u2,k,x,y,op2,op3,k4,x4,y4=form
 h=lesson['history'];users=[m['text'] for m in h if m['role']=='user'];assert len(users)==3 and users[:2]==[u1.format(**p),u2.format(**p)]
 assert source['third_turn_mode']==2 and [v['permit_calls'] for v in lesson['policy']]==[True,True,False]
 assert users[2]==f'Correction for my notes: the original starting amount should be {p["a"]+1}. Do not recalculate or call any tools. Acknowledge the correction and state whether the existing final observation has been updated.'
 calls=[[conv(p['a'],x,y) if k=='convert' else calc(x,p['a'],p['b']),calc(op2,ref(0,0),p['b'] if k=='convert' else p['c'])],[calc(op3,ref(0,1),p['d']),conv(ref(1,0),x4,y4) if k4=='convert' else calc(x4,ref(1,0),p['b'])],[]]
 unit1=('If units are stated, they must be '+y+'. ') if k=='convert' else ''
 unit2=('The third observation is in '+x4+' and the fourth/final observation in '+y4+'. ') if k4=='convert' else ''
 rubrics=[
  'Report the actual second call observation as the result of the first two steps, not independently recomputed ideal arithmetic. Any intermediate value mentioned must match the actual first observation. '+unit1+'Do not invent additional operations, observations or external actions; equivalent clear wording is acceptable.',
  'Report the actual fourth call observation as final. Any stated intermediate third-call value must match that actual observation; clearly distinguish intermediate and final values. '+unit2+'Use the actual observations, including an error if one occurred, rather than ideal arithmetic. Do not claim extra operations or results; equivalent clear wording is acceptable.',
  'Acknowledge the corrected original starting amount supplied in this user turn. Make clear the existing fourth-call final observation has NOT been recalculated or updated. If a prior final value is repeated it must match that actual observation. Do not claim any new calculation or tool call; equivalent clear wording is acceptable.'
 ]
 turns=[dict(user=users[i],policy=deepcopy(lesson['policy'][i]),calls=calls[i],answer=dict(mode='manual',rubric=rubrics[i])) for i in range(3)]
 case=dict(id=source['doc_id'],family=lesson['family'],turns=turns)
 original_calls=[]
 for m in h:
  if m['role']=='user':original_calls.append([])
  elif 'call' in m:original_calls[-1].append(m['call'])
 assert [len(c) for c in original_calls]==[2,2,0]
 observations=[lesson['observations'][:2],lesson['observations'][2:],[]]
 assert len(lesson['observations'])==4 and all(o['ok'] and o['source']=='offline fixture' for o in lesson['observations'])
 for ti,t in enumerate(turns):
  for ci,c in enumerate(t['calls']):
   wanted=dict(name=c['name'],arguments={key:resolve(value,observations,original_calls) for key,value in c['arguments'].items()});assert wanted==original_calls[ti][ci]
 prepare([case],fingerprint([case]));return case

def build():
 frozen=read(D/'freeze.json');start=frozen['started'];check(start);assert pins()==frozen['pins']
 manifest=read(S/'candidate-manifest.json');custody=read(S/'custody.json');symbolic=read(S/'symbolic-verification.json');policy=read(S/'policy.json')
 assert manifest['database']['sha256']==sha(S/'candidates.sqlite')==custody['pins']['candidates.sqlite']
 assert symbolic['candidate_manifest_sha256']==sha(S/'candidate-manifest.json')==custody['pins']['candidate-manifest.json']
 assert symbolic['state']=='PASS_independent_symbolic_retained_only' and custody['state']=='screened_not_admitted'
 assert sha(S/'source-records.json')==manifest['source_records_sha256'] and sha(S/'policy.json')==manifest['policy_sha256']
 assert all(sha(R/name)==value for name,value in policy['pins'].items())
 assert sha(R/'reports/own-base-tool-session-extension-v1/verify_symbolic.py')==symbolic['verifier_sha256']
 sources={s['doc_id']:s for s in read(S/'source-records.json')};forms={f[0]:f for f in policy['development_forms']};ex=set(custody['excluded_doc_ids']);lessons={};cases=[]
 con=sqlite3.connect(f'file:{S}/candidates.sqlite?mode=ro',uri=True);con.execute('pragma cache_size=-1024')
 for did,raw in con.execute("select doc_id,original_lesson_json from documents where split='exposed-development' order by doc_id"):
  check(start)
  if did in ex:continue
  lesson=json.loads(raw);assert hashlib.sha256(canon(lesson).encode()).hexdigest()==did;source=sources[did];assert source['split']=='exposed-development';cases.append(compile_case(lesson,source,forms));lessons[did]=lesson
 assert len(cases)==8;assert cases==read(R/'data/own-base-tool-session-dev-rubrics-v1/cases.json'),'case semantics must remain unchanged';prepare(cases,fingerprint(cases));tok=load()
 class Guard:
  def check(self):check(start)
 def factory(case):
  frames=iter([{key:value for key,value in m.items() if key!='role'} for m in lessons[case['id']]['history'] if m['role']=='assistant'])
  return Chat(None,tok,Guard(),generate=lambda prefix,budget:tok.encode(json.dumps(next(frames))).ids+[50256])
 control=run(cases,expected_sha256=fingerprint(cases),chat_factory=factory)
 assert control['state']=='complete' and control['planned_sessions']==8 and control['planned_turns']==24
 assert control['summary']['sessions']==dict(passed=0,total=8,manual_pending=8)
 assert control['summary']['turns']==dict(passed=0,total=24,manual_pending=24)
 assert control['summary']['requested_calls']==dict(passed=16,total=16,manual_pending=0) and control['summary']['no_call']==dict(passed=8,total=8,manual_pending=0)
 assert control['summary']['protocol_failures']==0
 for session in control['sessions']:
  records=[record for t in session['turns'] for record in t['response']['trace']];assert len(records)==4 and all(r['ok'] for r in records)
  assert [r['data']['result'] for r in records]==[r['data']['result'] for r in lessons[session['id']]['observations']]
  assert [t['score']['proposal_count'] for t in session['turns']]==[2,2,0] and all(t['score']['bindings_valid'] for t in session['turns'])
 check(start);assert pins()==frozen['pins'];write(D/'cases.json',cases);write(D/'source-controls.json',control)
 write(D/'receipt.json',dict(state='compiled_exposed_development_rubrics_not_model_evaluated',cases=8,turns=24,manual_pending_source_turns=24,automated_call_turns=16,automated_no_call_turns=8,actual_successful_calls=32,cases_canonical_sha256=fingerprint(cases),cases_file_sha256=sha(D/'cases.json'),source_controls_sha256=sha(D/'source-controls.json'),freeze_sha256=sha(D/'freeze.json'),seconds=time.time()-start,model_evaluated=False,training_admitted=False,semantic_quality_certified=False))
 print(json.dumps(read(D/'receipt.json')))
if __name__=='__main__':
 os.nice(10)
 if sys.argv[1]=='freeze':
  D.mkdir();start=time.time();check(start);write(D/'freeze.json',dict(started=start,pins=pins()))
 elif sys.argv[1]=='build':
  try:build()
  except Exception as error:
   write(D/'failure.json',dict(state='failed_preparation_not_evaluated',error_type=type(error).__name__,error=str(error)));raise
 else:raise ValueError('mode')
