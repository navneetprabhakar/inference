import hashlib,io,json,os,signal,subprocess,sys,tempfile
from pathlib import Path
from email.message import Message
from types import SimpleNamespace
from unittest.mock import patch
BASE=Path(__file__).resolve().parent.parent;PREP=BASE/'pressbooks-hansard-acquisition-executor-preparation-v1';sys.path.insert(0,str(PREP));import acquire as a;import transport as t
sys.path.insert(0,str(a.REPO/'src'));from slm.data.intake_ledger import IntakeLedger
C={'version':'INDEPENDENT_MOCK_ONLY','limits':{'requests':100,'body_bytes':1000000,'rows':100,'output_bytes':10000000},'wall_seconds':120};results=[]
def require(fn):
 try:fn()
 except BaseException:return
 raise AssertionError('must refuse')
def test(name,fn):fn();results.append(name)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pins():
 assert sha(PREP/'readiness.json')=='c8a425cde4c895d722022c15f2b52d25979f627ebf3f33405ab56006de1d4c0c'
 assert sha(PREP/'code-pins.json')=='5ecd59217c8eced010aed0d585151d649ae72f44d3a921af4d6234f0ad8d7dd7'
 assert sha(PREP/'profiles.json')=='55dc7f7506c7c4daadcb87029fe9c1a3735cd2a8b8b2952176701915b20385d6'
 p=json.loads((PREP/'profiles.json').read_text());registry=json.loads((PREP/'code-pins.json').read_text())['SHA256'];assert set(registry)==set(p['required_inventory']) and len(registry)==47
 for f,h in registry.items():assert sha(f)==h
 for source,n,total in [('pressbooks',2,421754480),('uk_hansard',11,3203457551)]:
  q=p['sources'][source];assert len(q['files'])==n and sum(f['expected_bytes'] for f in q['files'])==total
  assert q['limits']['body_reservation_including_one_byte_EOF_probe_per_file']==total+n
  assert q['limits']['max_physical_GETs']==3*n
 testdata=p
 return testdata
test('47 exact externally bound pins and original 2/11 files/body+probe/request bounds',pins)
for x in ['https://huggingface.co/a\u00a0','https://huggingface.co/a\x7f','https://huggingface.co/a\u0085','https://huggingface.co/a\u2066']:
 test('Unicode URL rejection '+repr(x[-1]),lambda x=x:require(lambda:t.url(x)))
class R:
 def __init__(self,url,status=302):self.url=url;self.code=status;self.headers=Message();self.headers['Location']='https://us.aws.cdn.hf.co/file?secret=HIDDEN';self.closed=False;self.reads=0
 def geturl(self):return self.url
 def close(self):self.closed=True
 def read1(self,n):self.reads+=1;return b''
def worker_timeout():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z);out=root/'out';out.mkdir()
  for n,k in a.SLOTS.items():(out/n).write_bytes(b' '*k)
  l=IntakeLedger(root/'charges',C);l.reserve('x-output',output_bytes=1000000);l.close()
  item={'ordinal':0,'path':'raw.gz','url':'https://huggingface.co/exact','revision':'abc','expected_bytes':3,'expected_sha256':hashlib.sha256(b'abc').hexdigest()};p={'key':'x','output':str(out),'files':[item],'limits':{'worker_seconds':30,'per_file_seconds_all_hops':5,'output_precharge_bytes':1000000}}
  class O:
   calls=0
   def open(self,request,timeout):
    self.calls+=1
    if self.calls==1:self.r=R(request.full_url);return self.r
    raise TimeoutError('HIDDEN')
  op=O()
  with patch.object(a,'ROOT',root),patch.object(a,'verify',lambda _:p),patch.object(a,'disk',lambda *x:None),patch.object(a,'helpers',lambda:(IntakeLedger,C,None)),patch.object(a.urllib.request,'build_opener',lambda *x:op):
   assert a.worker(SimpleNamespace(supervisor_pid=os.getppid()),a.clock())==1
  signal.setitimer(signal.ITIMER_REAL,0)
  l=IntakeLedger(root/'charges',C);rows=dict(l.db.execute('SELECT key,state FROM attempts'));assert rows=={'x-output':'failed','x-body-000':'failed','x-hop-000-0':'complete','x-hop-000-1':'failed'};assert l.totals()['requests']==2 and l.totals()['body_bytes']==4;l.close()
  assert op.calls==2 and op.r.closed and op.r.reads==0 and not (out/'raw.gz.partial').exists()
  for f in out.iterdir():assert b'HIDDEN' not in f.read_bytes()
test('actual worker redirected-open timeout exact hop/body/output settlement without secret leakage',worker_timeout)
def existing():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z);out=root/'old';out.mkdir();f=out/'original';f.write_bytes(b'old evidence');before=sha(f);p={'output':str(out),'limits':{'external_seconds_including_preflight_hashes_and_terminal':30}}
  with patch.object(a,'verify',lambda _:p),patch.object(a,'handoff',lambda _:{}),patch.object(a,'helpers',lambda:(_ for _ in ()).throw(AssertionError('ledger must not open'))):assert a.supervise(SimpleNamespace(source='pressbooks'),a.clock())==1
  signal.setitimer(signal.ITIMER_REAL,0);assert sha(f)==before and list(out.iterdir())==[f]
test('actual supervisor existing frozen output refusal no ledger/no mutation',existing)
def postspawn():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z);out=root/'out';p={'key':'x','output':str(out),'files':[],'limits':{'output_precharge_bytes':1000000,'external_seconds_including_preflight_hashes_and_terminal':30,'body_reservation_including_one_byte_EOF_probe_per_file':0,'max_physical_GETs':0}};children=[];original=subprocess.Popen;save=a.save
  def popen(*args,**kw):
   c=original([sys.executable,'-c','import time;time.sleep(30)'],start_new_session=True);children.append(c);return c
  def fail(p,name,*args,**kwargs):
   if name=='ownership.json':raise OSError('synthetic postspawn failure')
   return save(p,name,*args,**kwargs)
  with patch.object(a,'ROOT',root),patch.object(a,'verify',lambda _:p),patch.object(a,'handoff',lambda _:{}),patch.object(a,'disk',lambda *x:None),patch.object(a,'helpers',lambda:(IntakeLedger,C,None)),patch.object(a.subprocess,'Popen',popen),patch.object(a,'save',fail):assert a.supervise(SimpleNamespace(source='pressbooks',code_pins_sha256='x',profiles_sha256='y'),a.clock())==1
  signal.setitimer(signal.ITIMER_REAL,0);assert len(children)==1 and children[0].poll() is not None;require(lambda:os.kill(children[0].pid,0))
  l=IntakeLedger(root/'charges',C);assert l.db.execute('SELECT state FROM attempts WHERE key=?',('x-output',)).fetchone()==('failed',);l.close();assert json.loads((out/'supervisor-result.json').read_text())['worker_reaped']
test('actual supervisor postspawn fault kills/reaps separate session and settles own reservation',postspawn)
rss=a.load('independent_RSS',a.RSS_HELPER)
for text in ['', '123 1 5\n', f'{os.getpid()} 1 -1\n',f'{os.getpid()} 1 1\n{os.getpid()} 1 2\n',f'{os.getpid()} 1 1\nBAD\n']:
 def check(text=text):
  with patch.object(rss.subprocess,'run',lambda *x,**kw:SimpleNamespace(stdout=text)):require(lambda:rss.tree_rss(os.getpid()))
 test('strict RSS snapshot rejection '+repr(text),check)
print(json.dumps({'status':'PASS','independent_controls':len(results),'names':results,'actual_GETs':0,'global_ledger_writes':False,'retained_source_body_reads':False},indent=2))
