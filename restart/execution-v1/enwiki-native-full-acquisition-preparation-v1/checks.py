"""Finite offline mocked transport/filesystem/ledger controls. No network."""
import archive as d,pathlib,tempfile,hashlib,json,types,email.message,sys
from unittest.mock import patch
checks=[]
def passed(name):checks.append(name)
def raises(name,fn,err=(ValueError,TimeoutError,OSError)):
 try:fn()
 except err:passed(name)
 else:raise AssertionError(name)
class Bytes:
 def __init__(self,b):self.b=b;self.p=0
 def read1(self,n):b=self.b[self.p:self.p+n];self.p+=len(b);return b
x=b'BZh9-mock-compressed-native-XML\n'
for name,data,good in [('exact',x,True),('extra',x+b'X',False),('short',x[:-1],False),('corrupt',b'X'+x[1:],False)]:
 with tempfile.TemporaryDirectory() as t,patch.object(d,'SIZE',len(x)),patch.object(d,'BODY_CAP',len(x)+1),patch.object(d,'MD5',hashlib.md5(x).hexdigest()),patch.object(d,'SHA1',hashlib.sha1(x).hexdigest()):
  p=pathlib.Path(t)/'partial';s={}
  try:r=d.stream(Bytes(data),p,d.clk(),s)
  except ValueError:assert not good and p.read_bytes()==data and s['bytes']==len(data)
  else:assert good and r['SHA256']==hashlib.sha256(x).hexdigest()
  passed(name+'_partial_bytes_and_hash_retained')
with tempfile.TemporaryDirectory() as t:
 p=pathlib.Path(t)/'p';raises('worker_deadline_precedes_read',lambda:d.stream(Bytes(x),p,d.clk()-d.WORK-1,{}));assert p.read_bytes()==b''
class Stall(Bytes):
 def read1(self,n):raise TimeoutError('mock_socket_stall')
with tempfile.TemporaryDirectory() as t:
 p=pathlib.Path(t)/'p';raises('socket_stall_preserves_empty_partial',lambda:d.stream(Stall(x),p,d.clk(),{}));assert p.read_bytes()==b''
def response(status=200,url=d.URL,headers=None):
 h=email.message.Message()
 for k,v in (headers if headers is not None else [('Content-Length',str(d.SIZE))]):h[k]=v
 return types.SimpleNamespace(code=status,headers=h,geturl=lambda:url)
r=response();raw,ev=d.header_evidence(r);d.validate_response(r,raw);passed('exact_header')
for name,r in [('redirect',response(302)),('wrong_URL',response(url=d.URL+'?x')),('206',response(206)),('missing_length',response(headers=[])),('duplicate_length',response(headers=[('Content-Length',str(d.SIZE))]*2)),('wrong_length',response(headers=[('Content-Length','1')])),('encoding',response(headers=[('Content-Length',str(d.SIZE)),('Content-Encoding','gzip')])),('chunked',response(headers=[('Content-Length',str(d.SIZE)),('Transfer-Encoding','chunked')]))]:
 raw,ev=d.header_evidence(r);raises(name+'_before_body',lambda:d.validate_response(r,raw))
r=response(headers=[('Content-Length',str(d.SIZE)),('X-Large','X'*70000)]);raw,ev=d.header_evidence(r);assert ev['prefix_only'] and len(ev['prefix_hex'])==2*d.HEADERS;raises('aggregate_header_refused_and_bounded_evidence',lambda:d.validate_response(r,raw))
L,C,T=d.dependencies()
contract={'limits':{'requests':2,'body_bytes':d.BODY_CAP*2,'rows':1,'output_bytes':d.OUTPUT_CAP*2},'wall_seconds':30}
with tempfile.TemporaryDirectory() as t:
 l=L(pathlib.Path(t)/'ledger',contract);d.reserve(l);d.require_pending(l);raises('once_only_replay_refused',lambda:d.reserve(l));s=d.settle(l);assert s['state']=='failed' and l.totals()['body_bytes']==d.BODY_CAP and l.totals()['requests']==1 and l.totals()['output_bytes']==d.OUTPUT_CAP;passed('failure_no_refund_terminalized');l.close()
with tempfile.TemporaryDirectory() as t:
 l=L(pathlib.Path(t)/'ledger',contract);l.reserve(d.KEY,requests=1,body_bytes=1,output_bytes=d.OUTPUT_CAP);raises('wrong_pending_charge_refused',lambda:d.require_pending(l));l.close()
ctx=T.trusted_context();assert ctx.check_hostname and ctx.verify_mode==d.ssl.CERT_REQUIRED;passed('verified_pinned_CA_hostname_required')
with tempfile.TemporaryDirectory() as t,patch.object(d,'ROOT',pathlib.Path(t)),patch.object(d,'OUT',pathlib.Path(t)/'out'):
 d.OUT.mkdir()
 with patch.object(d.shutil,'disk_usage',return_value=types.SimpleNamespace(free=d.FREE-1)):raises('protected_disk_floor',d.check_storage)
 with patch.object(d,'OUTPUT_CAP',10),patch.object(d,'META_RESERVE',0):raises('output_prewrite',lambda:d.check_storage(11))
 with patch.object(d,'COMBINED_CAP',10):raises('combined_raw_processed_prewrite',lambda:d.check_storage(11))
# Setup fault must precharge before any profile file and reconcile only after no child exists.
with tempfile.TemporaryDirectory() as t:
 root=pathlib.Path(t);out=root/'out';lroot=root/'ledger'
 def deps():return L,contract,T
 original=pathlib.Path.open
 def fault(p,*a,**kw):
  if p==out/'worker-result.json':raise OSError('first_slot_fault')
  return original(p,*a,**kw)
 with patch.object(d,'ROOT',root),patch.object(d,'OUT',out),patch.object(d,'verify',return_value={}),patch.object(d,'dependencies',deps),patch.object(d,'size',return_value=0),patch.object(d.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)),patch.object(d.subprocess,'Popen',side_effect=AssertionError('must not launch')),patch.object(pathlib.Path,'open',fault):
  # Use scoped temp ledger rather than global charges while preserving production reserve/cleanup.
  def deps2():
   class Local(L):
    def __init__(self,p,c):super().__init__(lroot,contract)
   return Local,contract,T
  with patch.object(d,'dependencies',deps2):raises('first_slot_failure_settles_reserved_profile',lambda:d.supervise(types.SimpleNamespace(code_pins_sha256='x',profile_sha256='y')))
 l=L(lroot,contract);assert l.db.execute('select state from attempts where key=?',(d.KEY,)).fetchone()==('failed',);assert l.totals()['output_bytes']==d.OUTPUT_CAP;l.close();passed('setup_fault_retains_all_body_request_output_charges')
# Exercise actual worker paths against a local ledger and fake response, not a socket.
for mode in ['success','URL_error','socket_timeout','checksum_mismatch','changed_pin_before_publish']:
 with tempfile.TemporaryDirectory() as t:
  root=pathlib.Path(t);out=root/'out';out.mkdir();ledgerroot=root/'charges'
  class Local(L):
   def __init__(self,p,c):super().__init__(ledgerroot,contract)
  class Response(Bytes):
   code=200
   def __init__(self,b):super().__init__(b);self.headers=response(headers=[('Content-Length',str(len(x)))]).headers
   def geturl(self):return d.URL
   def __enter__(self):return self
   def __exit__(self,*a):pass
  opener=types.SimpleNamespace(open=lambda *a,**k:Response(x if mode!='checksum_mismatch' else b'X'+x[1:]))
  if mode in ['URL_error','socket_timeout']:
   def failed_open(*a,**k):raise d.urllib.error.URLError('fixture') if mode=='URL_error' else TimeoutError('fixture')
   opener.open=failed_open
  calls=[]
  def verified(c,p):
   calls.append((c,p))
   if mode=='changed_pin_before_publish' and len(calls)==2:raise ValueError('fixture_code_changed')
  with patch.object(d,'ROOT',root),patch.object(d,'OUT',out),patch.object(d,'SIZE',len(x)),patch.object(d,'BODY_CAP',len(x)+1),patch.object(d,'MD5',hashlib.md5(x).hexdigest()),patch.object(d,'SHA1',hashlib.sha1(x).hexdigest()),patch.object(d,'verify',verified),patch.object(d,'dependencies',return_value=(Local,contract,T)),patch.object(d.urllib.request,'build_opener',return_value=opener),patch.object(d.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)):
   l=Local(None,None);d.reserve(l);l.close()
   for name,n in d.SLOTS.items():(out/name).write_bytes(b' '*n)
   args=types.SimpleNamespace(code_pins_sha256='codepin',profile_sha256='profilepin',start=str(d.clk()),supervisor_pid=d.os.getppid())
   if mode=='success':d.worker(args)
   else:raises('worker_'+mode+'_terminal_failure',lambda:d.worker(args),(ValueError,TimeoutError,d.urllib.error.URLError))
   l=Local(None,None);row=l.db.execute('select state,actual_bytes from attempts where key=?',(d.KEY,)).fetchone();assert row==(('complete',len(x)) if mode=='success' else ('failed',None));assert l.totals()['requests']==1 and l.totals()['body_bytes']==len(x)+1;l.close()
   assert calls[0]==('codepin','profilepin')
   if mode=='success':assert (out/d.NAME).read_bytes()==x and not (out/'archive.partial').exists()
   else:assert not (out/d.NAME).exists()
   passed('actual_worker_'+mode+'_receipt_and_durable_charge')
# Supervisor forwards both external pins before any child operation; fake child exits,
# proving post-reaped cleanup without running acquisition.
with tempfile.TemporaryDirectory() as t:
 root=pathlib.Path(t);out=root/'out';lr=root/'ledger';seen=[]
 class Local(L):
  def __init__(self,p,c):super().__init__(lr,contract)
 class Child:
  pid=12345;returncode=1
  def poll(self):return 1
  def wait(self,timeout):return 1
 def launch(args,**kw):seen.extend(args);return Child()
 with patch.object(d,'ROOT',root),patch.object(d,'OUT',out),patch.object(d,'verify',return_value={}),patch.object(d,'dependencies',return_value=(Local,contract,T)),patch.object(d.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)),patch.object(d.subprocess,'Popen',launch):
  rc=d.supervise(types.SimpleNamespace(code_pins_sha256='codepin',profile_sha256='profilepin'));assert rc==1
 assert seen[seen.index('--code-pins-sha256')+1]=='codepin' and seen[seen.index('--profile-sha256')+1]=='profilepin';l=Local(None,None);assert l.db.execute('select state from attempts').fetchone()==('failed',);l.close();passed('supervisor_child_both_pins_and_post_reap_cleanup')
with tempfile.TemporaryDirectory() as t,patch.object(d,'SIZE',len(x)),patch.object(d,'MD5',hashlib.md5(x).hexdigest()),patch.object(d,'SHA1',hashlib.sha1(x).hexdigest()),patch.object(d,'check_storage',return_value=None),patch.object(d,'process_RSS',return_value=1):
 f=pathlib.Path(t)/'final';f.write_bytes(x);r=d.verify_final_file(f,hashlib.sha256(x).hexdigest(),d.clk());assert r['bytes']==len(x);passed('supervisor_independent_three_hashes')
 f.write_bytes(b'X'+x[1:]);raises('supervisor_disk_tamper_refused',lambda:d.verify_final_file(f,hashlib.sha256(x).hexdigest(),d.clk()))
 raises('supervisor_hash_deadline',lambda:d.verify_final_file(f,'0'*64,d.clk()-d.EXTERNAL))
import code_guard
with tempfile.TemporaryDirectory() as t:
 h=pathlib.Path(t);f=h/'input';f.write_bytes(b'original');registry=h/'code-pins.json'
 good={'runtime':d.runtime(),'sha256':{str(f):hashlib.sha256(f.read_bytes()).hexdigest()}}
 def save(r):registry.write_text(json.dumps(r));return hashlib.sha256(registry.read_bytes()).hexdigest()
 with patch.object(code_guard,'HERE',h),patch.object(d,'inventory',return_value={str(f)}):
  code_guard.verify(save(good));passed('exact_registry_inventory_runtime')
  raises('empty_registry_cannot_bypass',lambda:code_guard.verify(save({'runtime':d.runtime(),'sha256':{}})))
  wrong=dict(good,runtime={});raises('runtime_drift_refused',lambda:code_guard.verify(save(wrong)))
  pin=save(good);f.write_bytes(b'tampered');raises('dependency_tamper_refused',lambda:code_guard.verify(pin))
import code_guard
raises('bad_external_registry_digest',lambda:code_guard.verify('0'*64))
# Actual pin checks are exercised by the nonexecuting dispatch after final manifest freeze.
print(json.dumps({'status':'PASS_OFFLINE_ONLY_NO_NETWORK','count':len(checks),'checks':checks,'actual_HTTP_requests':0,'global_ledger_writes':0},indent=2))
