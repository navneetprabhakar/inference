import pathlib,sys,json,hashlib,runpy,io,contextlib,tempfile,email.message,types,os,ssl,sqlite3,urllib.error
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parent;D=P.parent/'enwiki-native-index-acquisition-preparation-v1';h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();before={str(p):h(p) for p in D.iterdir() if p.is_file()};assert h(D/'code-pins.json')=='d92d766dd047f78137b007243d7517180f48cef86c6fb31b7de7bdcf53474317';assert h(D/'profile.json')=='d41a80ed2bdd82498146ef536ab3f149667910f949643086bdb23ec32a5c9c5c';sys.path.insert(0,str(D));log=io.StringIO()
with contextlib.redirect_stdout(log):scope=runpy.run_path(str(D/'checks.py'),run_name='__main__')
(P/'baseline-checks.json').write_text(log.getvalue());a=scope['d'];Ledger=scope['IntakeLedger'];a.verify('d92d766dd047f78137b007243d7517180f48cef86c6fb31b7de7bdcf53474317','d41a80ed2bdd82498146ef536ab3f149667910f949643086bdb23ec32a5c9c5c');cases=[];payload=b'exact-index-fixture\n';targetmd5=hashlib.md5(payload).hexdigest();targetsha1=hashlib.sha1(payload).hexdigest()
class Response:
 def __init__(self,status,body):self.code=status;self.body=body;self.pos=0;self.headers=email.message.Message();self.headers['Content-Length']=str(len(body))
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def geturl(self):return a.URL
 def read1(self,n):b=self.body[self.pos:self.pos+n];self.pos+=len(b);return b
for label in ['success','opener_URLError','redirect302','checksum_mismatch']:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);out=root/'out';out.mkdir();contract={'limits':{'requests':1,'body_bytes':300000000,'rows':1,'output_bytes':305000000},'wall_seconds':30};helper=types.SimpleNamespace(trusted_context=ssl.create_default_context);calls=[];res=Response(302 if label=='redirect302' else 200,b'x'+payload[1:] if label=='checksum_mismatch' else payload)
  for n,length in a.SLOTS.items():(out/n).write_bytes(b' '*length)
  class Opener:
   def open(self,request,timeout):
    db=sqlite3.connect(root/'charges/ledger.sqlite');reserved=db.execute('select state,charge from attempts where key=?',(a.KEY,)).fetchone();db.close();assert reserved[0]=='pending' and json.loads(reserved[1])['requests']==1;calls.append(request.full_url)
    if label=='opener_URLError':raise urllib.error.URLError('offline synthetic TLS failure')
    return res
  args=types.SimpleNamespace(code_pins_sha256='audit',profile_sha256='audit',start=str(a.clk()),supervisor_pid=os.getppid())
  with patch.object(a,'ROOT',root),patch.object(a,'OUT',out),patch.object(a,'verify',lambda *args:{}),patch.object(a,'dependencies',lambda:(Ledger,contract,helper)),patch.object(a.urllib.request,'build_opener',lambda *args:Opener()),patch.object(a,'SIZE',len(payload)),patch.object(a,'MD5',targetmd5),patch.object(a,'SHA1',targetsha1):
   try:a.worker(args)
   except Exception:assert label!='success'
  db=sqlite3.connect(root/'charges/ledger.sqlite');state,n,charge=db.execute('select state,actual_bytes,charge from attempts where key=?',(a.KEY,)).fetchone();db.close();assert calls==[a.URL] and json.loads(charge)=={'requests':1,'body_bytes':300000000,'rows':0,'output_bytes':305000000};receipt=json.loads((out/'worker-result.json').read_text());assert state==('complete' if label=='success' else 'failed')
  if label=='success':assert n==len(payload) and (out/a.NAME).read_bytes()==payload and receipt['local_SHA256']==hashlib.sha256(payload).hexdigest() and receipt['index_decompressed_bytes']==0
  if label=='redirect302':assert res.pos==0 and not (out/'index.partial').exists()
  if label=='checksum_mismatch':assert (out/'index.partial').read_bytes()==res.body and receipt['partial_SHA256']==hashlib.sha256(res.body).hexdigest()
  cases.append({'case':label,'one_mocked_HTTP_open':True,'preIO_durable_charge':True,'terminal_ledger_state':state,'full_reserve_retained':True,'response_bytes':n,'receipt_status':receipt['status']})
with tempfile.TemporaryDirectory() as td:
 ledger=Ledger(pathlib.Path(td)/'ledger',{'limits':{'requests':2,'body_bytes':300000010,'rows':1,'output_bytes':305000010},'wall_seconds':30});ledger.reserve(a.KEY,requests=1,body_bytes=300000000,output_bytes=305000000);ledger.reserve('unrelated-owned-by-other-job',requests=1,body_bytes=10,output_bytes=10);before_totals=ledger.totals();assert a.settle_owned(ledger)=='failed_charge_retained';assert ledger.db.execute('select state from attempts where key=?',('unrelated-owned-by-other-job',)).fetchone()==('pending',) and ledger.totals()==before_totals;ledger.close();cases.append({'case':'postdeath_cleanup_exact_KEY_only','unrelated_allocation_unchanged':True,'all_charges_retained':True})
assert all(h(pathlib.Path(p))==d for p,d in before.items());result={'status':'PASS_FOCUSED_OFFLINE_INDEX_ONLY_WORKER_AND_ACCOUNTING_CONTROLS','baseline_controls':7,'independent_worker_controls':5,'cases':cases,'preparation_unchanged':True,'actual_network_requests':0,'global_ledger_writes':0,'index_downloads':0,'XML_downloads':0,'index_decompressions':0};(P/'focused-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'PASS','baseline':7,'independent':5}))
