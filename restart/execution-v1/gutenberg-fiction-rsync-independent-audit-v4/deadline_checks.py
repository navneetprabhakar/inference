"""Focused independent synthetic stall checks; no source/network/global ledger."""
import sys,json,signal,tempfile,time,subprocess
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parents[1]/'gutenberg-fiction-rsync-executor-preparation-v4';sys.path.insert(0,str(P));sys.path.insert(0,str(P.parents[2]/'src'))
import controller,validate,attempt_deadline
from slm.data.intake_ledger import IntakeLedger
N=[]
def test(n,fn):fn();N.append(n)
def validation_stall():
 with tempfile.TemporaryDirectory() as z:
  root=Path(z);out=root/'out';out.mkdir();ledger=IntakeLedger(root/'ledger',{'version':1,'limits':{'requests':1000,'body_bytes':1000000000,'output_bytes':1000000000,'rows':1000000},'wall_seconds':600});ledger.reserve('fixture-output',output_bytes=800000000)
  profile={'ledger_prefix':'fixture-','records':[{'ordinal':i,'ebook_ID':123+i,'source_relative_path':f'{123+i}/pg{123+i}.txt','native_catalog_URL':f'https://www.gutenberg.org/ebooks/{123+i}.txt.utf-8','source_row_SHA256':'a'*64,'family_component_ID':123+i} for i in range(2)]}
  def transfer(eid,f,stage,deadline,callback):
   (stage/f'pg{eid}.txt').write_bytes(b'x');return {'exit_code':0,'stdout':'Number of files: 1\nNumber of files transferred: 1\nTotal file size: 1 B\nTotal transferred file size: 1 B\n','stderr':'','received_bytes':1,'remote_started':False},b'x'
  original=validate.result;seen=[]
  def stalled(*args):
   seen.append(signal.getitimer(signal.ITIMER_REAL)[0]);time.sleep(.3);return original(*args)
  before=time.monotonic();error=None
  try:
   with patch.object(validate,'result',stalled):
    try:controller.execute(profile,out,ledger,lambda *a,**kw:None,transfer=transfer,attempt_guard=lambda:attempt_deadline.Guard(attempt_deadline.clk()+10,active_seconds=.04,external_seconds=.2))
    except BaseException as e:error=e
   assert isinstance(error,TimeoutError) and not isinstance(error,controller.transport.IndependentTimeout)
   assert time.monotonic()-before<.2 and 0<seen[0]<.05
   assert ledger.db.execute("select state from attempts where key='fixture-body-000'").fetchone()==('failed',)
   assert not (out/'attempt-001').exists()
   r=json.loads((out/'attempt-000/receipt.json').read_text());assert r['result']['status']=='FATAL_PROFILE_STOP_NO_RETRY'
  finally:signal.setitimer(signal.ITIMER_REAL,0);ledger.close()
test('v3 validation-stall class independently interrupted; fatal charged attempt and no next record',validation_stall)
def restore():
 old=signal.getsignal(signal.SIGALRM)
 def original(*a):raise AssertionError('original unexpectedly fired')
 signal.signal(signal.SIGALRM,original)
 try:
  end=attempt_deadline.clk()+10
  with attempt_deadline.Guard(end,active_seconds=.1,external_seconds=.2):time.sleep(.005)
  assert signal.getsignal(signal.SIGALRM) is original
  n=signal.getitimer(signal.ITIMER_REAL)[0];assert 9<n<=10
  with attempt_deadline.Guard(end,active_seconds=.1,external_seconds=.2):pass
  assert signal.getitimer(signal.ITIMER_REAL)[0]<=n
 finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
test('successful/repeated scopes restore original handler and remaining absolute global timer',restore)
def hard():
 code="""import time,attempt_deadline
with attempt_deadline.Guard(attempt_deadline.clk()+.035,active_seconds=.01,external_seconds=.09):
 try:time.sleep(1)
 finally:time.sleep(1)
"""
 before=time.monotonic();r=subprocess.run([sys.executable,'-B','-c',code],cwd=P,capture_output=True,timeout=1);assert r.returncode==124 and time.monotonic()-before<.5
test('independent actual cleanup stall ends with hard124 in child',hard)
print(json.dumps({'status':'PASS_FOCUSED_V4_NO_REMOTE_OR_GLOBAL_LEDGER','controls':len(N),'names':N,'public_source_connections':0,'global_ledger_writes':0,'retained_body_reads':0},indent=2))
