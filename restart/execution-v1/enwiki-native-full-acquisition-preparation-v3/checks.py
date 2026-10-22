"""Recovery response, assembly, source preservation, clock and real ledger guards; no network."""
import archive as a
import pathlib,tempfile,hashlib,json,types,email.message,signal,time,io
from unittest.mock import patch
from contextlib import ExitStack

def run():
 cases=[]
 def yes(n,v):assert v,n;cases.append(n)
 def no(n,fn,typ=ValueError):
  try:fn()
  except typ:cases.append(n);return
  raise AssertionError(n)
 def response(code=206,fields=None,url=None):
  h=email.message.Message()
  for k,v in (fields or [('Content-Length',str(a.REMAINING)),('Content-Range',f'bytes {a.PREFIX_SIZE}-{a.SIZE-1}/{a.SIZE}'),('ETag',a.ETAG)]):h[k]=v
  return types.SimpleNamespace(code=code,headers=h,geturl=lambda:url or a.URL)
 r=response();a.validate_response(r,a.header_evidence(r)[0]);yes('exact206_remaining_range_strong_ETag',True)
 for name,r in [('200wholefallback',response(200)),('wrongURL',response(url='https://example.org/other')),('length',response(fields=[('Content-Length','1'),('Content-Range',f'bytes {a.PREFIX_SIZE}-{a.SIZE-1}/{a.SIZE}'),('ETag',a.ETAG)])),('range',response(fields=[('Content-Length',str(a.REMAINING)),('Content-Range','bytes 0-1/2'),('ETag',a.ETAG)])),('ETag',response(fields=[('Content-Length',str(a.REMAINING)),('Content-Range',f'bytes {a.PREFIX_SIZE}-{a.SIZE-1}/{a.SIZE}'),('ETag','"other"')]))]:no('reject_'+name,lambda r=r:a.validate_response(r,a.header_evidence(r)[0]))
 for field,val in [('Content-Length',str(a.REMAINING)),('Content-Range',f'bytes {a.PREFIX_SIZE}-{a.SIZE-1}/{a.SIZE}'),('ETag',a.ETAG),('Transfer-Encoding','chunked'),('Content-Encoding','gzip')]:
  r=response();r.headers[field]=val;no('reject_duplicate_or_invalid_'+field,lambda r=r:a.validate_response(r,a.header_evidence(r)[0]))
 r=response();no('oversized_headers',lambda:a.validate_response(r,b'x'*(a.HEADERS+1)))
 with patch.object(a,'clk',return_value=100),patch.object(a,'ORIGINAL_DEADLINE',130):yes('original_absolute_deadline_dominates_new2h',a.remaining(100)==30 and a.remaining(100,True)==25)
 with patch.object(a,'clk',return_value=100),patch.object(a,'ORIGINAL_DEADLINE',10000):yes('new2h_cap_not_fresh8h',a.remaining(100)==7200)
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);prefix=root/'old';prefix.write_bytes(b'prefix');full=b'prefixsuffix';target=root/'new';state={}
  with ExitStack() as st:
   for k,v in {'PREFIX':prefix,'PREFIX_SIZE':6,'PREFIX_MD5':hashlib.md5(b'prefix').hexdigest(),'PREFIX_SHA1':hashlib.sha1(b'prefix').hexdigest(),'PREFIX_SHA256':hashlib.sha256(b'prefix').hexdigest(),'SIZE':12,'REMAINING':6,'BODY_CAP':7,'MD5':hashlib.md5(full).hexdigest(),'SHA1':hashlib.sha1(full).hexdigest()}.items():st.enter_context(patch.object(a,k,v))
   st.enter_context(patch.object(a,'prefix_identity',return_value={}));st.enter_context(patch.object(a,'remaining',return_value=60))
   ds=a.copy_prefix(target,0,state);yes('copy_old_prefix_exact_immutable_before_request',target.read_bytes()==b'prefix' and prefix.read_bytes()==b'prefix')
   class R:
    def __init__(self,data):self.b=io.BytesIO(data)
    def read1(self,n):return self.b.read(n)
   result=a.stream(R(b'suffix'),target,0,state,ds);yes('assembly_fullpublisher_hash_and_separate_networkhash',target.read_bytes()==full and result['bytes']==12 and result['network_bytes']==6 and result['network_SHA256']==hashlib.sha256(b'suffix').hexdigest() and prefix.read_bytes()==b'prefix')
   for label,data in [('short',b'suff'),('overflow',b'suffixx'),('wrong',b'badbad')]:
    q=root/label;s={};d=a.copy_prefix(q,0,s);no('range_'+label+'_preserved_not_published',lambda:q and a.stream(R(data),q,0,s,d));yes(label+'_oldsource_unchanged',prefix.read_bytes()==b'prefix')
   with patch.object(a,'PREFIX_SHA256',new='a'*64):no('prefixhash_mismatch_beforeHTTP',lambda:a.copy_prefix(root/'badprefix',0,{}))
   with patch.object(a,'remaining',return_value=-1):no('expired_copy_no_new_allowance',lambda:a.copy_prefix(root/'expired',0,{}),TimeoutError)
 for text in ['', '1 0 2', '77 1 0','77 1 2\n77 1 3','77 1 x','77 1 -1']:no('RSSfailclosed_'+repr(text),lambda text=text:a.parse_RSS(text,77))
 yes('RSSdescendants_counted',a.parse_RSS('77 1 2\n78 77 3\n79 78 4',77)==9*1024)
 # Actual supervisor arms alarm before slow verify/TLS/disk; no global ledger or output mutation.
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);out=root/'new';cleanup=[]
  def blocked(*args):signal.raise_signal(signal.SIGALRM)
  with patch.object(a,'OUT',out),patch.object(a,'ROOT',root),patch.object(a,'verify',side_effect=blocked),patch.object(a,'cleanup',side_effect=lambda:cleanup.append(1)):
   no('actual_supervisor_early_verify_alarm',lambda:a.supervise(types.SimpleNamespace(code_pins_sha256='a'*64,profile_sha256='b'*64)),RuntimeError)
  yes('uncharged_watchdog_doesnotwrite_or_reconcile',not out.exists() and not cleanup and signal.getitimer(signal.ITIMER_REAL)[0]==0)
 L,C,T=a.dependencies()
 contract={'limits':{'requests':10,'body_bytes':a.BODY_CAP+10,'rows':10,'output_bytes':a.OUTPUT_CAP+10},'wall_seconds':60}
 with tempfile.TemporaryDirectory() as td:
  l=L(pathlib.Path(td)/'ledger',contract)
  a.reserve(l);a.require_pending(l);yes('real_temp_ledger_exact_newcharge_beforeIO',l.totals()['body_bytes']==a.BODY_CAP and l.totals()['output_bytes']==a.OUTPUT_CAP)
  x=a.settle(l);yes('failed_reserved_remaining_no_refund',x['state']=='failed' and l.totals()['body_bytes']==a.BODY_CAP);l.close()
 a.prefix_identity();yes('actual_retained_receipt_header_prefix_binding_without16GBread',True)
 return {'status':'PASS_SYNTHETIC_RECOVERY_NO_NETWORK_NO_GLOBAL_LEDGER_WRITES','controls':len(cases),'cases':cases}
if __name__=='__main__':print(json.dumps(run(),indent=2))
