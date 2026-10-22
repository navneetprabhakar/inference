"""Tiny inert synthetic wheel/HTTP/local-ledger fixtures only; no package execution."""
import acquire as a,io,csv,json,base64,hashlib,pathlib,tempfile,zipfile,types,email.message,time
from unittest.mock import patch
checks=[]
def ok(n):checks.append(n)
def refuse(name,fn,kind=(ValueError,zipfile.BadZipFile,TimeoutError,RuntimeError)):
 try:fn()
 except kind:ok(name)
 else:raise AssertionError(name)
prefix=a.PACKAGE+'-'+a.VERSION+'.dist-info/'
def wheel(changes=None,record_bad=False,unrecorded=False,path=None,mode=None):
 files={a.PACKAGE+'/__init__.py':b'raise RuntimeError("MUST NEVER EXECUTE SYNTHETIC CODE")\n',prefix+'METADATA':f'Name: {a.PACKAGE}\nVersion: {a.VERSION}\nLicense: MIT\n'.encode(),prefix+'WHEEL':b'Wheel-Version: 1.0\nTag: cp312-cp312-macosx_11_0_arm64\n',prefix+'licenses/LICENSE':b'Copyright fixture\nPermission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:\nThe above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.\nTHE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.\n'}
 files.update(changes or {})
 if path:files[path]=b'fixture'
 s=io.StringIO(newline='');w=csv.writer(s,lineterminator='\n')
 for n,b in files.items():
  if not (unrecorded and n==a.PACKAGE+'/__init__.py'):w.writerow([n,'sha256='+('bad' if record_bad else base64.urlsafe_b64encode(hashlib.sha256(b).digest()).decode().rstrip('=')),str(len(b))])
 w.writerow([prefix+'RECORD','','']);files[prefix+'RECORD']=s.getvalue().encode();buf=io.BytesIO()
 with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
  for n,b in files.items():
   if mode is not None and n==a.PACKAGE+'/__init__.py':i=zipfile.ZipInfo(n);i.external_attr=mode<<16;z.writestr(i,b)
   else:z.writestr(n,b)
 return buf.getvalue()
def inspect(raw):
 with patch.object(a,'EXPECTED',hashlib.sha256(raw).hexdigest()):return a.inspect_wheel(raw)
raw=wheel();r=inspect(raw);assert r['all_CRCs_complete'] and r['all_RECORD_files_hash_and_size_verified'] and r['downloaded_code_imports']==0;ok('inert_wheel_all_CRC_RECORD_metadata_MIT_no_execution')
refuse('publisher_SHA_refusal',lambda:a.inspect_wheel(raw))
for name,rawbad in [('path_escape',wheel(path='../escape')),('absolute_path',wheel(path='/absolute')),('backslash',wheel(path='x\\escape')),('symlink',wheel(mode=0o120777)),('RECORD_bad_hash',wheel(record_bad=True)),('RECORD_missing_file',wheel(unrecorded=True)),('wrong_internal_version',wheel(changes={prefix+'METADATA':b'Name: mwparserfromhell\nVersion: 9\n'})),('wrong_tag',wheel(changes={prefix+'WHEEL':b'Tag: cp311-cp311-macosx_11_0_arm64\n'})),('license_missing_grant',wheel(changes={prefix+'licenses/LICENSE':b'Not a license'}))]:refuse(name,lambda b=rawbad:inspect(b))
# Declared decode limits are checked before inflation.
with patch.dict(a.CAPS,ZIP_member_decoded_bytes=8):refuse('ZIP_member_decode_cap',lambda:inspect(raw))
with patch.dict(a.CAPS,ZIP_total_decoded_bytes=8):refuse('ZIP_aggregate_decode_cap',lambda:inspect(raw))
with patch.dict(a.CAPS,ZIP_entries=1):refuse('ZIP_entry_count_cap',lambda:inspect(raw))
meta={'info':{'name':a.PACKAGE,'version':a.VERSION,'license':'MIT'},'urls':[{'filename':a.FILENAME,'url':'https://files.pythonhosted.org/packages/observed-only/'+a.FILENAME,'digests':{'sha256':a.EXPECTED},'packagetype':'bdist_wheel','python_version':'cp312','yanked':False,'size':154600}]}
sel=a.parse_metadata(json.dumps(meta).encode());assert sel['URL']==meta['urls'][0]['url'] and sel['no_URL_guessed'];ok('exact_wheel_URL_comes_only_from_metadata')
for name,field,value in [('hash','digests',{'sha256':'0'*64}),('host','url','https://example.com/packages/'+a.FILENAME),('HTTP','url','http://files.pythonhosted.org/packages/'+a.FILENAME),('query','url',meta['urls'][0]['url']+'?x'),('yanked','yanked',True),('name','filename','wrong.whl'),('size','size',a.WHEEL_CAP)]:
 m=json.loads(json.dumps(meta));m['urls'][0][field]=value;refuse('metadata_'+name,lambda m=m:a.parse_metadata(json.dumps(m).encode()))
refuse('duplicate_JSON_fields',lambda:a.parse_metadata(b'{"info":{},"info":{}}'))
L,C,T=a.dependencies();ctx=T.trusted_context();assert ctx.check_hostname and ctx.verify_mode==a.ssl.CERT_REQUIRED;ok('actual_imports_CA_preflight_no_socket')
contract={'limits':{'requests':2,'body_bytes':1000000,'rows':1,'output_bytes':5000000},'wall_seconds':30}
class Response:
 def __init__(self,url,body,status=200,headers=None):
  self.url=url;self.body=body;self.p=0;self.code=status;self.headers=email.message.Message()
  for k,v in (headers or {'Content-Length':str(len(body))}).items():self.headers[k]=v
 def __enter__(self):return self
 def __exit__(self,*x):pass
 def geturl(self):return self.url
 def read1(self,n):b=self.body[self.p:self.p+n];self.p+=len(b);return b
for mode in ['metadata_only_mismatch','success','wheel_URL_error','wheel_bad_hash','ZIP_invalid']:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);out=root/'out';out.mkdir();lr=root/'ledger';seen=[];instances=[]
  class Local(L):
   def __init__(self,p,c):super().__init__(lr,contract);instances.append(self)
  content=raw if mode!='ZIP_invalid' else b'not a ZIP';expected=hashlib.sha256(content).hexdigest()
  m=json.loads(json.dumps(meta));m['urls'][0]['size']=len(content);m['urls'][0]['digests']['sha256']=expected
  if mode=='metadata_only_mismatch':m['urls'][0]['filename']='bad.whl'
  body=json.dumps(m).encode();url=m['urls'][0]['url']
  class Open:
   def open(self,req,timeout):
    seen.append(req.full_url);l=instances[-1];key=a.PREFIX+('metadata' if len(seen)==1 else 'wheel');assert l.db.execute('select state from attempts where key=?',(key,)).fetchone()==('pending',)
    if len(seen)==2 and mode=='wheel_URL_error':raise a.urllib.error.URLError('fixture')
    return Response(req.full_url,body if len(seen)==1 else (b'X'+content[1:] if mode=='wheel_bad_hash' else content))
  with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'EXPECTED',expected),patch.object(a,'verify',return_value={}),patch.object(a,'dependencies',return_value=(Local,contract,T)),patch.object(a.urllib.request,'build_opener',return_value=Open()),patch.object(a.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)):
   l=Local(None,None);a.reserve_output(l);l.close()
   for n,size in a.SLOTS.items():(out/n).write_bytes(b' '*size)
   args=types.SimpleNamespace(code_pins_sha256='c',profile_sha256='p',supervisor_pid=a.os.getppid(),start=str(a.clk()))
   if mode=='success':a.worker(args)
   else:refuse('actual_worker_'+mode,lambda:a.worker(args),(ValueError,zipfile.BadZipFile,a.urllib.error.URLError))
  l=Local(None,None);assert l.db.execute("select count(*) from attempts where state='pending'").fetchone()==(0,);assert l.totals()['requests']==(1 if mode=='metadata_only_mismatch' else 2);assert l.totals()['body_bytes']<=1000000;l.close();assert len(seen)==(1 if mode=='metadata_only_mismatch' else 2)
  assert (out/a.FILENAME).exists()==(mode=='success');ok('actual_worker_'+mode+'_oneattempt_no_install_no_refund')
# Header rejection before any response body read, local request reservation retained.
for status in [302,503]:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);out=root/'out';out.mkdir();l=L(root/'ledger',contract);res=Response(a.META_URL,b'unread',status);op=types.SimpleNamespace(open=lambda *x,**y:res)
  with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)):refuse('HTTP'+str(status)+'_no_body_read',lambda:a.fetch(l,op,'key',a.META_URL,200000,'p',a.clk()))
  assert res.p==0 and l.totals()['requests']==1;l.close()
# Actual external alarm must include blocked verify/TLS/disk preflight and not touch ledger/output.
for stage in ['verify','TLS','disk']:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);out=root/'no';events=[]
  def blocked(*x,**y):events.append(stage);time.sleep(2)
  def never(*x,**y):raise AssertionError('no ledger/child')
  with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'EXTERNAL',.03),patch.object(a,'verify',blocked if stage=='verify' else lambda *x:{}),patch.object(a,'dependencies',blocked if stage=='TLS' else lambda:(never,None,None)),patch.object(a.shutil,'disk_usage',blocked if stage=='disk' else lambda x:types.SimpleNamespace(free=10**15)),patch.object(a,'cleanup',never):refuse('alarm_interrupts_'+stage+'_before_allocation',lambda:a.supervise(types.SimpleNamespace(code_pins_sha256='c',profile_sha256='p')),RuntimeError)
  assert events==[stage] and not out.exists() and not (root/'charges').exists()
# Durable5MB output precharge is closed before first slot; setup failure cleans onlyowned keys.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);out=root/'out';lr=root/'ledger';original=pathlib.Path.open
 class Local(L):
  def __init__(self,p,c):super().__init__(lr,contract)
 def opened(p,*x,**y):
  if p==out/'worker-result.json':
   l=Local(None,None);a.require_output(l);l.close();raise OSError('first_slot_fault')
  return original(p,*x,**y)
 with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'verify',return_value={}),patch.object(a,'dependencies',return_value=(Local,contract,T)),patch.object(a.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)),patch.object(pathlib.Path,'open',opened):refuse('supervisor_firstslot_precharged_and_closed',lambda:a.supervise(types.SimpleNamespace(code_pins_sha256='c',profile_sha256='p')),OSError)
 l=Local(None,None);assert l.totals()['output_bytes']==5000000 and l.totals()['requests']==0 and l.db.execute('select state from attempts').fetchone()==('failed',);l.close();ok('setup_failure_output_charge_retained_no_HTTP_allocation')
import code_guard
refuse('wrong_external_registry',lambda:code_guard.verify('0'*64),(ValueError,FileNotFoundError))
# Read every ZIP file through EOF: damaged stored bytes must trigger CRC failure.
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',zipfile.ZIP_STORED) as z:z.writestr('crc-fixture',b'PAYLOAD-CRC-FIXTURE')
corrupt=buf.getvalue().replace(b'PAYLOAD-CRC-FIXTURE',b'PAYLOAD-CRC-FAILURE')
refuse('ZIP_CRC_damage_refused',lambda:inspect(corrupt),zipfile.BadZipFile)
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);l=L(root/'ledger',contract)
 refuse('aged_fetch_no_request_allocation',lambda:a.fetch(l,types.SimpleNamespace(open=lambda *x,**y:(_ for _ in ()).throw(AssertionError('noHTTP'))),'expired',a.META_URL,200000,'p',a.clk()-a.WORK-1),TimeoutError)
 assert l.totals()['requests']==0;l.close()
# Fake already-reaped child proves both external digests are passed; cleanup marks
# profile output failed and cannot affect an unrelated local fixture charge.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);out=root/'out';lr=root/'ledger';seen=[]
 class Local(L):
  def __init__(self,p,c):super().__init__(lr,contract)
 class Child:
  pid=12345;returncode=1
  def poll(self):return 1
  def wait(self,timeout):return 1
 def launch(cmd,**kw):seen.extend(cmd);return Child()
 with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'verify',return_value={}),patch.object(a,'dependencies',return_value=(Local,contract,T)),patch.object(a.shutil,'disk_usage',return_value=types.SimpleNamespace(free=10**15)),patch.object(a.subprocess,'Popen',launch):refuse('fakechild_partial_terminal_no_retry',lambda:a.supervise(types.SimpleNamespace(code_pins_sha256='CODE',profile_sha256='PROFILE')),(ValueError,json.JSONDecodeError))
 assert seen[seen.index('--code-pins-sha256')+1]=='CODE' and seen[seen.index('--profile-sha256')+1]=='PROFILE';l=Local(None,None);assert l.db.execute('select state from attempts').fetchone()==('failed',);l.close();ok('main_to_worker_external_pins_postreaped_cleanup')
with tempfile.TemporaryDirectory() as td:
 h=pathlib.Path(td);f=h/'input';f.write_bytes(b'original');manifest=h/'code-pins.json'
 def save(x):manifest.write_text(json.dumps(x));return hashlib.sha256(manifest.read_bytes()).hexdigest()
 good={'runtime':a.runtime(),'sha256':{str(f):hashlib.sha256(f.read_bytes()).hexdigest()}}
 with patch.object(code_guard,'HERE',h),patch.object(a,'inventory',return_value={str(f)}):
  code_guard.verify(save(good));ok('actual_registry_exact_inventory_runtime')
  refuse('empty_registry_refusal',lambda:code_guard.verify(save({'runtime':a.runtime(),'sha256':{}})))
  pin=save(good);f.write_bytes(b'changed');refuse('dependency_tamper_refusal',lambda:code_guard.verify(pin))
print(json.dumps({'status':'PASS_OFFLINE_NO_NETWORK_NO_INSTALL','count':len(checks),'checks':checks,'actual_HTTP_requests':0,'global_ledger_writes':0,'packages_installed_or_imported':0},indent=2))
