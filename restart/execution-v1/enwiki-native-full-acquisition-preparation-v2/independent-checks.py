import importlib.util,pathlib,sys,json,tempfile,subprocess,time,hashlib,types,email.message
from unittest.mock import patch
BASE=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1');PREP=BASE/'enwiki-native-full-acquisition-preparation-v2';OUT=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(PREP));import archive as d
checks=[]
def ok(n):checks.append(n)
def refusal(fn,kind=ValueError):
 try:fn()
 except kind:return
 raise AssertionError('not refused')
pins=json.loads((PREP/'readiness.json').read_text());d.verify(pins['code_pins_SHA256'],pins['profile_SHA256']);ok('actual_external_pins_exact36_inventory_profile_runtime_verified_no_network')
L,C,T=d.dependencies();contract={'limits':{'requests':10,'body_bytes':100,'rows':10,'output_bytes':100},'wall_seconds':60}
# A second real process must fail immediately while a worker owns the exclusive global-style lock.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td)/'ledger';l=L(root,contract)
 code="import sys,json;sys.path.insert(0,sys.argv[1]);from slm.data.intake_ledger import IntakeLedger\ntry: l=IntakeLedger(sys.argv[2],json.loads(sys.argv[3]))\nexcept BlockingIOError: print('REFUSED_LOCKED');sys.exit(0)\nelse: l.close();sys.exit(2)"
 r=subprocess.run([sys.executable,'-B','-c',code,str(d.REPO/'src'),str(root),json.dumps(contract)],capture_output=True,text=True,timeout=3);assert r.returncode==0 and r.stdout.strip()=='REFUSED_LOCKED';l.close();ok('real_second_process_nonblocking_exclusive_ledger_refusal')
with tempfile.TemporaryDirectory() as td:
 l=L(pathlib.Path(td)/'ledger',contract);l.reserve(d.KEY,requests=1,body_bytes=10,output_bytes=10);l.reserve('unrelated',requests=1,body_bytes=10,output_bytes=10)
 state=d.settle(l);assert state['state']=='failed';assert l.db.execute('select state from attempts where key=?',('unrelated',)).fetchone()==('pending',);assert l.totals()['body_bytes']==20;l.close();ok('cleanup_exact_owned_key_only_no_refund')
p=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(30)'],start_new_session=True)
try:d.kill(p);assert p.poll() is not None and p.returncode<0;ok('real_owned_new_session_process_group_SIGKILL_and_reap')
finally:
 if p.poll() is None:p.kill();p.wait(timeout=3)
class Interrupted:
 def __init__(self):self.calls=0
 def read1(self,n):
  self.calls+=1
  if self.calls==1:return b'prefix'
  raise TimeoutError('mock_interrupted_after_prefix')
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)/'partial';s={};refusal(lambda:d.stream(Interrupted(),p,d.clk(),s),TimeoutError);assert p.read_bytes()==b'prefix' and s['bytes']==6 and s['SHA256']==hashlib.sha256(b'prefix').hexdigest();ok('midtransfer_interruption_retains_exact_full_partial_prefix_hash')
class One:
 def read1(self,n):return b'abcdef'
class ShortFile:
 def __init__(self,f):self.f=f
 def __enter__(self):return self
 def __exit__(self,*a):self.f.close()
 def write(self,b):self.f.write(b[:2]);return 2
 def flush(self):return self.f.flush()
 def fileno(self):return self.f.fileno()
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)/'partial';s={};orig=pathlib.Path.open
 def opening(q,*a,**k):
  f=orig(q,*a,**k);return ShortFile(f) if q==p and a==('xb',) else f
 with patch.object(pathlib.Path,'open',opening):refusal(lambda:d.stream(One(),p,d.clk(),s),OSError)
 assert p.read_bytes()==b'ab' and s['bytes']==0 and p.stat().st_size!=s['bytes'];ok('local_short_write_retains_bytes_and_cannot_claim_complete_partial_hash')
for extra in [[('Content-Range','bytes 0-1/2')],[('Transfer-Encoding','identity')]]:
 h=email.message.Message();h['Content-Length']=str(d.SIZE)
 for k,v in extra:h[k]=v
 r=types.SimpleNamespace(code=200,headers=h,geturl=lambda:d.URL);raw,_=d.header_evidence(r);refusal(lambda:d.validate_response(r,raw));ok('unrequested_'+extra[0][0]+'_refused_beforebody')
# Any stale/expired shared start is rejected before response.read1, not given a fresh worker allowance.
class NeverRead:
 def read1(self,n):raise AssertionError('read after expiry')
with tempfile.TemporaryDirectory() as td:refusal(lambda:d.stream(NeverRead(),pathlib.Path(td)/'partial',d.clk()-d.WORK-1,{}),TimeoutError);ok('aged_shared_worker_deadline_has_no_fresh_allowance')
require=bool(d.process_RSS()>0);assert require;ok('actual_process_tree_RSS_observation_positive')
result={'status':'PASS_FOCUSED_OFFLINE_INDEPENDENT_CONTROLS','count':len(checks),'checks':checks,'prep_pins':{'code_pins_SHA256':pins['code_pins_SHA256'],'profile_SHA256':pins['profile_SHA256'],'archive_code_SHA256':pins['archive_code_SHA256']},'actual_HTTP_requests':0,'global_ledger_writes':0,'private_fixture_ledger_only':True}
(OUT/'independent-check-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
