"""Tiny offline stream/checksum fixtures only; no index/body download."""
import index as d,pathlib,tempfile,hashlib,json
from unittest.mock import patch
checks=[]
class Bytes:
 def __init__(self,x):self.x=x;self.p=0
 def read1(self,n):out=self.x[self.p:self.p+n];self.p+=len(out);return out
x=b'index-fixture\n';md5=hashlib.md5(x).hexdigest();sha1=hashlib.sha1(x).hexdigest()
for name,payload,good in [('exact_fixture',x,True),('oversize_one_byte',x+b'x',False),('truncated_fixture',x[:-1],False),('checksum_bad',b'x'+x[1:],False)]:
 with tempfile.TemporaryDirectory() as tmp,patch.object(d,'SIZE',len(x)),patch.object(d,'MD5',md5),patch.object(d,'SHA1',sha1):
  p=pathlib.Path(tmp)/'partial'
  try:n,h=d.stream(Bytes(payload),p,d.clk())
  except ValueError:
   assert not good;assert p.read_bytes()==payload[:len(x)+1]
  else:assert good and n==len(x) and h[2]==hashlib.sha256(x).hexdigest()
  checks.append(name+'_bounded_retained')
with tempfile.TemporaryDirectory() as tmp,patch.object(d,'SIZE',len(x)):
 p=pathlib.Path(tmp)/'partial'
 try:d.stream(Bytes(x),p,d.clk()-571)
 except TimeoutError:assert p.read_bytes()==b''
 else:raise AssertionError('deadline')
 checks.append('work_deadline_before_read')
import sys
sys.path.insert(0,str(d.REPO/'src'))
from slm.data.intake_ledger import IntakeLedger
with tempfile.TemporaryDirectory() as tmp:
 ledger=IntakeLedger(pathlib.Path(tmp)/'ledger',{'limits':{'requests':1,'body_bytes':300000000,'rows':1,'output_bytes':305000000},'wall_seconds':30});ledger.reserve(d.KEY,requests=1,body_bytes=300000000,output_bytes=305000000);assert d.settle_owned(ledger)=='failed_charge_retained';assert ledger.totals()['body_bytes']==300000000;assert ledger.db.execute('select state from attempts').fetchone()==('failed',);ledger.close();checks.append('supervisor_partial_owned_charge_terminalized_without_refund')
import code_guard
try:code_guard.verify('0'*64)
except (ValueError,FileNotFoundError):checks.append('external_registry_digest_refused')
else:raise AssertionError('registry')
print(json.dumps({'status':'PASS_OFFLINE_ONLY','checks':checks,'count':len(checks),'network_requests':0,'index_decompressions':0},indent=2))
