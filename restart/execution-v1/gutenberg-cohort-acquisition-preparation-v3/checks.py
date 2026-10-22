"""Finite transport-upgrade controls, offline HTTP mocks and isolated ledgers."""
import acquire as a,json,pathlib,tempfile,sys,email.message,urllib.error
from unittest.mock import patch
sys.path.insert(0,str(a.REPO/'src'))
from slm.data.intake_ledger import IntakeLedger
checks=[];native='https://www.gutenberg.org/ebooks/123.txt.utf-8';target='https://www.gutenberg.org/cache/epub/123/pg123.txt'
class Response:
 def __init__(self,status=200,body=b'English prose.',headers=None):
  self.code=status;self.body=body;self.pos=0;self.headers=email.message.Message()
  for k,v in (headers or {'Content-Type':'text/plain; charset=utf-8','Content-Length':str(len(body))}).items():self.headers[k]=v
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def geturl(self):return target
 def read1(self,n):b=self.body[self.pos:self.pos+n];self.pos+=len(b);return b
for name,response,good in [('direct_HTTPS_target_only_no_original_replay',Response(),True),('sameID_HTTPS_redirect_refused',Response(302,b'never read',{'Location':target}),False),('HTTP_redirect_refused',Response(302,b'never read',{'Location':'http://www.gutenberg.org/cache/epub/123/pg123.txt'}),False),('HTTP503_retained_no_retry',Response(503,b'Unavailable'),False),('invalidUTF8_partial',Response(200,b'bad\xff'),False),('cap_exact_no_EOF_overread',Response(200,b'x'*2400000),False),('URL_error',urllib.error.URLError('mock'),False),('timeout',TimeoutError('mock'),False),('absolute_deadline',a.BodyDeadline('mock'),False)]:
 with tempfile.TemporaryDirectory() as tmp:
  root=pathlib.Path(tmp);out=root/'out';out.mkdir();ledger=IntakeLedger(root/'ledger',{'limits':{'requests':1,'body_bytes':2400000,'rows':1,'output_bytes':2400000},'wall_seconds':30});ledger.reserve('body',body_bytes=2400000,output_bytes=2400000);calls=[]
  def open_(op,url,timeout):
   assert url==target and url!=native and url.startswith('https://');assert ledger.db.execute("select state from attempts where key='body-hop0'").fetchone()==('pending',);calls.append(url)
   if isinstance(response,BaseException):raise response
   return response
  row={'ebook_ID':123,'ordinal':1,'family_component_ID':123,'frame_raw_hash':'hash','source_binding':{},'metadata_stratum':'proxy','format':{'resolved_URL':native},'transport_target_URL':target}
  r=a.transfer(row,out,ledger,'body',None,{'last_request':None,'requests':0},a.clk(),open_)
  assert len(calls)==1 and (r['error'] is None)==good
  assert ledger.db.execute("select count(*) from attempts where state='pending'").fetchone()==(0,)
  assert ledger.totals()['requests']==1
  if not isinstance(response,BaseException) and response.code==302:assert response.pos==0
  if isinstance(response,BaseException):
   failure=json.loads((out/'pg123-hop0-failure.json').read_text());assert failure['url']==target and failure['IO_began']
  ledger.close();checks.append(name)
print(json.dumps({'status':'PASS_OFFLINE_TRANSPORT_ONLY','count':len(checks),'checks':checks,'network_requests':0},indent=2))
