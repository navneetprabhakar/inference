"""Offline fake-response, temporary-ledger and virtual-stream controls only."""
import pathlib,tempfile,json,hashlib,io,email.message,threading,time,types,concurrent.futures,sys,signal
import transport_core as c,segmented as s
class Response:
 def __init__(self,raw,part=None,code=206,url=s.URL):
  self.raw=io.BytesIO(raw);self.code=code;self.url=url;self.headers=email.message.Message()
  if part:
   self.headers['Content-Length']=str(part['bytes']);self.headers['Content-Range']=f"bytes {part['start']}-{part['end']}/{s.SIZE}";self.headers['ETag']=s.ETAG
 def read1(self,n):return self.raw.read(n)
 def geturl(self):return self.url
 def close(self):pass

def run():
 tests=[]
 def no(name,fn):
  try:fn()
  except (ValueError,TimeoutError,OSError):tests.append(name);return
  raise AssertionError(name)
 parts=c.partition(s.PREFIX_SIZE,s.SIZE,s.WIDTH);assert len(parts)==65 and sum(x['bytes'] for x in parts)==8679640223 and parts[-1]['bytes']==89705631 and sum(x['bytes']+1 for x in parts)==8679640288 and parts[0]['start']==17988844772 and parts[-1]['end']==26668484994;assert all(a['end']+1==b['start'] for a,b in zip(parts,parts[1:]));tests.append('exact65_contiguous128MiB_last_range_and_EOFcaps')
 p={'ordinal':0,'start':10,'end':13,'bytes':4};r=Response(b'abcd',p);raw,_=c.header_packet(r);c.validate(r,raw,p,s.URL,s.SIZE,s.ETAG);tests.append('valid_exact206_identity')
 for name,mutate in [('whole200',lambda r:setattr(r,'code',200)),('redirectURL',lambda r:setattr(r,'url',s.URL+'?other')),('wrong_length',lambda r:r.headers.replace_header('Content-Length','3')),('wrong_range',lambda r:r.headers.replace_header('Content-Range','bytes 10-14/26668484995')),('wrong_total',lambda r:r.headers.replace_header('Content-Range','bytes 10-13/10')),('wrong_ETag',lambda r:r.headers.replace_header('ETag','"changed"')),('weak_ETag',lambda r:r.headers.replace_header('ETag','W/'+s.ETAG)),('duplicate_length',lambda r:r.headers.add_header('Content-Length','4')),('duplicate_range',lambda r:r.headers.add_header('Content-Range',f'bytes 10-13/{s.SIZE}')),('duplicate_ETag',lambda r:r.headers.add_header('ETag',s.ETAG)),('encoded',lambda r:r.headers.add_header('Content-Encoding','gzip')),('chunked',lambda r:r.headers.add_header('Transfer-Encoding','chunked'))]:
  r=Response(b'abcd',p);mutate(r);raw,_=c.header_packet(r);no(name,lambda r=r,raw=raw:c.validate(r,raw,p,s.URL,s.SIZE,s.ETAG))
 no('aggregate_oversize_headers',lambda:c.validate(Response(b'abcd',p),b'x'*65537,p,s.URL,s.SIZE,s.ETAG))
 with tempfile.TemporaryDirectory() as temp:
  root=pathlib.Path(temp);f=root/'ok';res=c.receive(Response(b'abcd'),f,4,lambda:None,lambda *x:None);assert f.read_bytes()==b'abcd' and res['SHA256']==hashlib.sha256(b'abcd').hexdigest();tests.append('actual_stream_success_exact_bytes_hash_fsync')
  no('short_body_preserved',lambda:c.receive(Response(b'abc'),root/'short',4,lambda:None,lambda *x:None));assert (root/'short').read_bytes()==b'abc'
  no('one_extra_EOF_byte_preserved_charged',lambda:c.receive(Response(b'abcde'),root/'extra',4,lambda:None,lambda *x:None));assert (root/'extra').read_bytes()==b'abcde'
  no('cancel_before_sourcebody_write',lambda:c.receive(Response(b'abcd'),root/'cancel',4,lambda:(_ for _ in ()).throw(TimeoutError('cancel')),lambda *x:None));assert (root/'cancel').stat().st_size==0
  components=[]
  for i,b in enumerate([b'prefix',b'one',b'two']):
   f=root/f'part{i}';f.write_bytes(b);components.append({'path':str(f),'bytes':len(b),'SHA256':hashlib.sha256(b).hexdigest(),'stat':c.stat_id(f)})
  whole=c.hash_components(components,lambda:None);payload=b'prefixonetwo';assert (whole['MD5'],whole['SHA1'],whole['SHA256'],whole['bytes'])==(hashlib.md5(payload).hexdigest(),hashlib.sha1(payload).hexdigest(),hashlib.sha256(payload).hexdigest(),len(payload));tests.append('ordered_virtual_stream_worker_plus_independent_equal_without_copy')
  independent=c.hash_components(components,lambda:None);assert independent==whole;tests.append('second_independent_virtual_stream')
  bad=[{**components[0],'SHA256':'0'*64}]+components[1:];no('bad_prefix_hash_stops',lambda:c.hash_components(bad,lambda:None));no('part_order_cannot_match_publisher',lambda:(_ for _ in ()).throw(ValueError()) if c.hash_components([components[0],components[2],components[1]],lambda:None)['SHA256']!=whole['SHA256'] else None)
  no('component_length_mismatch',lambda:c.hash_components([{**components[0],'bytes':1}],lambda:None));no('component_stat_changed',lambda:c.hash_components([{**components[0],'stat':[0]*5}],lambda:None))
  link=root/'link';link.symlink_to(components[0]['path']);no('symlink_component_refused',lambda:c.hash_components([{**components[0],'path':str(link)}],lambda:None))
  # Temporary actual durable ledger only; never touches global IntakeLedger.
  L,C,_=s.deps();contract={**C,'limits':{'requests':10,'body_bytes':1000,'rows':10,'output_bytes':10000},'wall_seconds':60};ledger=L(root/'ledger',contract);ledger.reserve('output',output_bytes=1000);assert ledger.db.execute('select charge from attempts where key=?',('output',)).fetchone();ledger.reserve('range',requests=1,body_bytes=5,output_bytes=0);s.streamed_complete(ledger,'range',{'bytes':4,'SHA256':hashlib.sha256(b'abcd').hexdigest()});assert ledger.db.execute('select state,actual_bytes from attempts where key=?',('range',)).fetchone()==('complete',4);tests.append('actual_ledger_output_before_IO_and_streamed_range_exact_success');no('range_cannot_complete_twice',lambda:s.streamed_complete(ledger,'range',{'bytes':4,'SHA256':'a'*64}));ledger.reserve('failed',requests=1,body_bytes=5);ledger.finish('failed',raw=None);before=ledger.totals();ledger.close();ledger=L(root/'ledger',contract);assert ledger.totals()==before and ledger.db.execute('select state from attempts where key=?',('failed',)).fetchone()[0]=='failed';ledger.close();tests.append('failed_conservative_charges_survive_reopen_no_refund')
 # Actual supervisor first-file allocation lifecycle with temporaryledger only.
 old=(s.OUT,s.ROOT,s.verify,s.deps);L,C,tls=s.deps()
 with tempfile.TemporaryDirectory() as temp:
  root=pathlib.Path(temp);s.ROOT=root;s.OUT=root/'job'
  s.verify=lambda a:{};s.deps=lambda:(L,C,tls);a=types.SimpleNamespace(code_pins_sha256='fixture',profile_sha256='fixture')
  oldwrite=pathlib.Path.write_bytes
  def broken(path,data):
   if path.name=='worker-result.json':
    db=__import__('sqlite3').connect(root/'charges/ledger.sqlite');r=db.execute('select charge,state from attempts where key=?',(s.KEY+'-output',)).fetchone();db.close();assert r and r[1]=='pending' and json.loads(r[0])=={'requests':0,'body_bytes':0,'rows':0,'output_bytes':9000000000};raise OSError('synthetic_firstslot_after_precharge')
   return oldwrite(path,data)
  pathlib.Path.write_bytes=broken
  try:no('actual_supervisor_output_precharge_before_first_file_and_partial_cleanup',lambda:s.supervise(a))
  finally:pathlib.Path.write_bytes=oldwrite
  db=__import__('sqlite3').connect(root/'charges/ledger.sqlite');assert db.execute('select state from attempts where key=?',(s.KEY+'-output',)).fetchone()[0]=='failed';db.close();assert json.loads((s.OUT/'supervisor-result.json').read_text())['status']=='TERMINAL_PARTIAL_NO_RETRY_NO_COMPLETE_ARCHIVE'
  before=(s.OUT/'supervisor-result.json').read_bytes();no('actual_existing_output_no_overwrite_no_newcharge',lambda:s.supervise(a));assert (s.OUT/'supervisor-result.json').read_bytes()==before
  s.OUT=root/'term'
  def pre(a):
   assert signal.getitimer(signal.ITIMER_REAL)[0]>0 and callable(signal.getsignal(signal.SIGTERM));signal.raise_signal(signal.SIGTERM)
  s.verify=pre;no('actual_supervisor_TERM_before_preflight',lambda:s.supervise(a));assert not s.OUT.exists()
 s.OUT,s.ROOT,s.verify,s.deps=old
 # Real start gate +two-thread scope with fakeopener; no sockets or corpusbytes.
 gate=c.StartGate();times=[];active=0;peak=0;lock=threading.Lock()
 class Opener:
  def open(self,req,timeout):
   nonlocal active,peak
   with lock:times.append(time.clock_gettime(time.CLOCK_MONOTONIC));active+=1;peak=max(peak,active)
   return Response(b'')
 def task():
  nonlocal active
  response,t=gate.open(Opener(),None,lambda:None);time.sleep(1.2)
  with lock:active-=1
  return t
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:record=list(pool.map(lambda _:task(),range(3)))
 assert peak<=2 and all(b-a>=1 for a,b in zip(times,times[1:]));tests.append('actual_two_threads_fake_HTTP_starts_atleast1second_and_max2')
 no('expired_original_deadline',lambda:s.arm(-1));assert s.CAPS['retries']==s.CAPS['redirects']==s.CAPS['decompressed_bytes']==0;tests.append('strict_no_retry_redirect_or_decompression_policy')
 # Actual frozen nonexecuting preflight: prohibit the retained operational body and network.
 if (s.HERE/'code-pins.json').exists():
  a=types.SimpleNamespace(code_pins_sha256=s.sha(s.HERE/'code-pins.json'),profile_sha256=s.sha(s.HERE/'profile.json'))
  original_open=pathlib.Path.open;original_http=s.urllib.request.OpenerDirector.open
  def guarded_open(path,*args,**kwargs):
   if path.resolve()==s.PREFIX.resolve():raise AssertionError('preflight_prefix_body_read')
   return original_open(path,*args,**kwargs)
  def no_http(*args,**kwargs):raise AssertionError('preflight_HTTP')
  pathlib.Path.open=guarded_open;s.urllib.request.OpenerDirector.open=no_http
  try:
   s.verify(a);tests.append('actual_frozen_preflight_prohibits_prefixbody_and_HTTP')
   bad=types.SimpleNamespace(code_pins_sha256='0'*64,profile_sha256=a.profile_sha256);no('actual_external_manifest_digest_refused',lambda:s.verify(bad))
   original_text=pathlib.Path.read_text
   def no_inventory(path,*args,**kwargs):
    if path.resolve()==(s.HERE/'code-pins.json').resolve():return '{"SHA256":{}}'
    return original_text(path,*args,**kwargs)
   pathlib.Path.read_text=no_inventory
   try:no('actual_empty_manifest_inventory_refused',lambda:s.verify(a))
   finally:pathlib.Path.read_text=original_text
  finally:pathlib.Path.open=original_open;s.urllib.request.OpenerDirector.open=original_http
 return {'status':'PASS_OFFLINE_SYNTHETIC_NO_NETWORK_PREFIXBODY_OR_GLOBALLEDGER','controls':len(tests),'cases':tests}
if __name__=='__main__':print(json.dumps(run(),indent=2))
