"""Actual worker lifecycle on tiny synthetic prefix/temp ledger/mocked HTTP only."""
import archive as a
import pathlib,tempfile,hashlib,json,io,types,email.message,os
from unittest.mock import patch
from contextlib import ExitStack

def run():
 cases=[];RealL,_,_=a.dependencies()
 for label,suffix,status in [('complete',b'suffix',206),('short',b'suff',206),('wholefallback',b'suffix',200)]:
  with tempfile.TemporaryDirectory() as td:
   root=pathlib.Path(td);out=root/'output';out.mkdir();old=root/'old';old.write_bytes(b'prefix');full=b'prefixsuffix';ledgerpath=root/'charges'
   for name,n in a.SLOTS.items():(out/name).write_bytes(b' '*n)
   class Response:
    code=status
    def __init__(self):
     self.b=io.BytesIO(suffix);self.headers=email.message.Message();self.headers['Content-Length']='6';self.headers['Content-Range']='bytes 6-11/12';self.headers['ETag']=a.ETAG
    def geturl(self):return a.URL
    def read1(self,n):return self.b.read(n)
    def __enter__(self):return self
    def __exit__(self,*args):pass
   observed=[]
   class Opener:
    def open(self,request,timeout):observed.append(request);return Response()
   contract={'limits':{'requests':10,'body_bytes':100,'rows':10,'output_bytes':10000000},'wall_seconds':60}
   tls=types.SimpleNamespace(CA_SHA256='a'*64,NoRedirect=lambda:None,trusted_context=lambda:None)
   with ExitStack() as st:
    values={'ROOT':root,'OUT':out,'PREFIX':old,'PREFIX_SIZE':6,'PREFIX_MD5':hashlib.md5(b'prefix').hexdigest(),'PREFIX_SHA1':hashlib.sha1(b'prefix').hexdigest(),'PREFIX_SHA256':hashlib.sha256(b'prefix').hexdigest(),'SIZE':12,'REMAINING':6,'RANGE':'bytes=6-11','BODY_CAP':7,'OUTPUT_CAP':5000000,'MD5':hashlib.md5(full).hexdigest(),'SHA1':hashlib.sha1(full).hexdigest()}
    for k,v in values.items():st.enter_context(patch.object(a,k,v))
    st.enter_context(patch.object(a,'verify',return_value={}));st.enter_context(patch.object(a,'prefix_identity',return_value={}));st.enter_context(patch.object(a,'check_storage',return_value=None));st.enter_context(patch.object(a,'remaining',return_value=30));st.enter_context(patch.object(a,'dependencies',return_value=(RealL,contract,tls)));st.enter_context(patch.object(a.urllib.request,'build_opener',return_value=Opener()))
    ledger=RealL(ledgerpath,contract);a.reserve(ledger);ledger.close()
    failed=False
    try:a.worker(types.SimpleNamespace(start=str(a.clk()),supervisor_pid=os.getpid(),code_pins_sha256='a'*64,profile_sha256='b'*64))
    except ValueError:failed=True
    # Worker parent is actual parent, not own PID; patch below at caller.
    if label=='complete':assert not failed
    else:assert failed
    assert observed and observed[0].get_header('Range')=='bytes=6-11' and observed[0].get_header('If-match')==a.ETAG
    assert old.read_bytes()==b'prefix' and not (out/a.NAME).exists()
    ledger=RealL(ledgerpath,contract);row=ledger.db.execute('select state,actual_bytes,body_sha256 from attempts where key=?',(a.KEY,)).fetchone();ledger.close()
    if label=='complete':
     assert row==('complete',6,hashlib.sha256(b'suffix').hexdigest()) and (out/'assembled.partial').read_bytes()==full
     hashes=a.verify_final_file(out/'assembled.partial',hashlib.sha256(full).hexdigest(),a.clk());assert hashes['bytes']==12
    else:assert row[0]=='failed'
    cases.append('actual_worker_'+label+'_prefix_immutable_exactrequest_ledger_settled_no_publication')
 return {'status':'PASS_ACTUAL_MOCK_WORKER_NO_NETWORK','controls':len(cases),'cases':cases}
if __name__=='__main__':
 with patch.object(a.os,'getppid',return_value=os.getpid()):print(json.dumps(run(),indent=2))
