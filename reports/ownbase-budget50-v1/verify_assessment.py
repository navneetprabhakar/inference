"""Independent code results, tool references and worst-case192-token reply framing."""
import contextlib,copy,hashlib,io,json,math,sys
from pathlib import Path
sys.path[:0]=[str(Path('.').resolve()),str(Path('runs/nanochat-source').resolve())]
from nanochat.tokenizer import RustBPETokenizer
from cloud_training.nano_chat_format import encode_conversation,stable_record
from tools import FixtureSession
P=Path('reports/ownbase-budget50-v1');suite=json.loads((P/'assessment.json').read_text());tok=RustBPETokenizer.from_directory('runs/ownbase-v2-data/tokenizer')
checks=0
def check(x):
 global checks
 assert x;checks+=1
# Selected Python families: independent small executions, not model/teacher scoring.
a=[['north'],['south']];b=a.copy();b[0].append('east');check(a==b==[['north','east'],['south']]);b=[r.copy() for r in a];b[0].append('west');check(a[0]==['north','east'])
def limit(c):
 v=c.get('retries');return 3 if v is None else v
check([limit({}),limit({'retries':None}),limit({'retries':0}),limit({'retries':5})]==[3,3,0,5])
p=['bolt','pin','nut','peg']
for part in p:
 if len(part)==3:p.remove(part)
check(p==['bolt','nut']);alias=p;p[:]=[x for x in p if len(x.strip())>3];check(alias is p and p==['bolt'])
level=4
def invalid():
 level+=1
try:invalid();raise AssertionError('missing error')
except UnboundLocalError:checks+=1
def counter():
 level=4
 def inc():
  nonlocal level
  level+=1;return level
 return inc
f=counter();g=counter();check([f(),f(),g()]==[5,6,5])
labels=['  RIVET\n','  MAST\n']
for label in labels:label.strip().lower()
check(labels==['  RIVET\n','  MAST\n']);check([x.rstrip().lower() for x in labels]==['  rivet','  mast'])
def record(name,log=[]):log.append(name);return log
a=record('Iris');b=record('Otto');check(a is b and a==['Iris','Otto'])
def fixed(name,log=None):
 result=[] if log is None else list(log);result.append(name);return result
original=[];check(fixed('Iris',original)==['Iris'] and original==[])
stock={'tea':2,'rice':1}
try:
 for key in stock:
  if stock[key]==1:del stock[key]
 raise AssertionError('missing RuntimeError')
except RuntimeError:checks+=1
stock={'tea':2,'rice':1,'salt':0};alias=stock
for key,value in list(stock.items()):
 if value<=1:del stock[key]
check(stock=={'tea':2} and stock is alias)
callbacks=[]
for room in ['red','blue','gold']:callbacks.append(lambda:room)
check([f() for f in callbacks]==['gold']*3)
def factory(room):
 def callback():return room
 return callback
callbacks=[factory(room) for room in ['red','blue','gold']];check([f() for f in callbacks]==['red','blue','gold']);check(all(f.__code__.co_argcount==0 for f in callbacks))
grid=[[0]*3]*2;grid[0][1]=7;check(grid==[[0,7,0],[0,7,0]])
grid=[[0]*3]*2;grid[0]=[0,7,0];check(grid==[[0,7,0],[0,0,0]])
check('report.txt'.rstrip('.txt')=='repor');check('notes.txt.txt'.removesuffix('.txt')=='notes.txt');label='Report.TXT';check((label[:-4] if label.lower().endswith('.txt') else label)=='Report')
gen=(n*2 for n in range(3));check(list(gen)==[0,2,4] and list(gen)==[])
gen=(n*2 for n in range(3));check(next(gen)==0 and list(gen)==[2,4])
def result():
 try:return 10
 finally:return 20
check(result()==20)
def cleaned():
 try:return 10
 finally:print('cleanup')
s=io.StringIO()
with contextlib.redirect_stdout(s):v=cleaned()
check(v==10 and s.getvalue()=='cleanup\n');check(not (1<5<5) and 1<=5<=5)
items=[10,20,30,40,50];check(items[-4:-1]==[20,30,40] and items[-1:-4:-1]==[50,40,30] and items[:1:-1]==[50,40,30])
try:x,y=(3,4,5);raise AssertionError('missing ValueError')
except ValueError:checks+=1
x,*rest=(3,4,5);check(x==3 and rest==[4,5]);scores=[8,2,5];ordered=scores.sort();check(scores==[2,5,8] and ordered is None)
scores=[8,2,5];ordered=sorted(scores);check(scores==[8,2,5] and ordered==[2,5,8]);config={'timeout':None};check(config.get('timeout') is None and config.get('retries') is None and 'timeout' in config and 'retries' not in config)
check(0.1+0.2!=0.3 and math.isclose(0.1+0.2,0.3,rel_tol=0,abs_tol=1e-9));check(list(enumerate(['red','blue'],1))==[(1,'red'),(2,'blue')]);check(list(enumerate(['red','blue','green'][1:],1))==[(1,'blue'),(2,'green')]);settings={'mode':'fast','mode':'safe'};check(settings['mode']=='safe');settings={'mode':['fast','safe']};check(settings['mode'][1]=='safe')
# Reference tool outputs and deliberately long synthetic placeholders exercise framing only.
lengths=[];exact=[]
for session in suite['sessions']:
 messages=[];policies=[];broker=FixtureSession()
 for t in session['turns']:
  policy={'permit_calls':t['permit_calls'],'allowed_names':['calculate','convert'] if t['permit_calls'] else []};policies.append(policy);messages.append({'role':'user','content':t['user']});broker.start_turn(**policy)
  for call in t['expected_calls']:
   rec=broker.propose(json.dumps(call),assistant_call_boundary=True);check(rec['ok']);cid=rec['call_id'];messages.extend([{'role':'assistant','tool_call':call,'call_id':cid},{'role':'tool','call_id':cid,'record':stable_record(rec,call=call,call_id=cid)}])
  messages.append({'role':'assistant','content':'word '*192})
  if t['acceptable_answers']:exact.append({'id':session['id'],'answers':t['acceptable_answers']})
 encoded=encode_conversation(tok,messages,policies=policies,context=2048);lengths.append(len(encoded['ids']))
report={'suite_sha256':hashlib.sha256((P/'assessment.json').read_bytes()).hexdigest(),'executable_checks':checks,'sessions_framed':len(lengths),'maximum_reference_tokens_with192word_placeholders':max(lengths),'exact_answers':exact,'limitation':'Framing placeholders are not generated answers and not semantic evidence. No4Klate-context cases.'}
(P/'assessment-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
