"""Exact transport v1 race on mocked302 and isolated durable ledger; no GET."""
import hashlib,importlib.util,io,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
from email.message import Message
BASE=Path(__file__).resolve().parent.parent;V1=BASE/'pressbooks-hansard-acquisition-executor-preparation-v1'
sys.path.insert(0,str(BASE.parents[1]/'src'))
from slm.data.intake_ledger import IntakeLedger
s=importlib.util.spec_from_file_location('old_transport',V1/'transport.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Response:
 code=302
 def __init__(self):self.headers=Message();self.headers['Location']='https://us.aws.cdn.hf.co/file?secret=REDACT_ME';self.reads=0
 def geturl(self):return 'https://huggingface.co/file'
 def close(self):pass
class Opener:
 calls=0
 def open(self,*a,**k):self.calls+=1;return Response()
C={'limits':{'requests':10,'body_bytes':100,'rows':100,'output_bytes':100000},'wall_seconds':30,'scope':'SYNTHETIC_ONLY'}
with tempfile.TemporaryDirectory() as z:
 l=IntakeLedger(Path(z)/'ledger',C);saved={};op=Opener();times=iter([100.,100.999999,101.000001]);sleeps=[]
 def sleep(n):
  sleeps.append(n)
  if n<0:raise ValueError('sleep length must be non-negative')
 try:
  with patch.object(m,'clock',lambda:next(times)),patch.object(m.time,'sleep',sleep):
   m.acquire({'ordinal':1,'url':'https://huggingface.co/file','expected_bytes':3,'expected_sha256':hashlib.sha256(b'abc').hexdigest(),'revision':'x'},Path(z)/'partial',l,'body',['hop0','hop1','hop2'],op,lambda:None,lambda n,r,replace:saved.update({n:json.loads(json.dumps(r))}),{'last_start':None,'requests':0},lambda:10)
 except m.Fault as e:assert str(e)=='file_attempt_terminal_no_retry'
 else:raise AssertionError('old race did not occur')
 assert len(sleeps)==1 and sleeps[0]<0 and op.calls==1 and saved['current-attempt.json']['error']=='ValueError'
 assert l.db.execute('SELECT state FROM attempts WHERE key=?',('hop0',)).fetchone()==('complete',)
 assert l.db.execute('SELECT state FROM attempts WHERE key=?',('hop1',)).fetchone() is None
 rows=l.db.execute('SELECT key,charge,state FROM attempts ORDER BY key').fetchall();l.close()
 print(json.dumps({'status':'EXACT_V1_RACE_REPRODUCED_SYNTHETIC','clock_values':[100.,100.999999,101.000001],'negative_sleep_seconds':sleeps[0],'physical_mock_GETs':op.calls,'next_hop_reserved':False,'redacted_error':saved['current-attempt.json']['error'],'isolated_ledger_rows':rows,'real_GETs':0,'global_ledger_writes':0},indent=2))
