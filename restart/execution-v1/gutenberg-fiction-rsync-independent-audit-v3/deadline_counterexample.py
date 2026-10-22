"""Actual controller with synthetic transfer and accelerated per-file clock only."""
import sys,json,tempfile,time,signal
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parents[1]/'gutenberg-fiction-rsync-executor-preparation-v3';sys.path.insert(0,str(P));sys.path.insert(0,str(P.parents[2]/'src'))
import controller,validate
from slm.data.intake_ledger import IntakeLedger
clock=[100.0];seen=[];original=validate.result
with tempfile.TemporaryDirectory() as z:
 root=Path(z);out=root/'out';out.mkdir();ledger=IntakeLedger(root/'ledger',{'version':1,'limits':{'requests':1000,'body_bytes':1000000000,'output_bytes':1000000000,'rows':1000000},'wall_seconds':600});ledger.reserve('fixture-output',output_bytes=800000000)
 profile={'ledger_prefix':'fixture-','records':[{'ordinal':0,'ebook_ID':123,'source_relative_path':'123/pg123.txt','native_catalog_URL':'https://www.gutenberg.org/ebooks/123.txt.utf-8','source_row_SHA256':'a'*64,'family_component_ID':123}]}
 def transfer(eid,f,stage,deadline,callback):
  (stage/'pg123.txt').write_bytes(b'x');return {'exit_code':0,'stdout':'Number of files: 1\nNumber of files transferred: 1\nTotal file size: 1 B\nTotal transferred file size: 1 B\n','stderr':'','received_bytes':1,'remote_started':False},b'x'
 def stalled(stage,eid,receipt):
  seen.append({'per_file_signal_alarm_seconds':signal.getitimer(signal.ITIMER_REAL)[0]});time.sleep(.03);clock[0]=161.0;return original(stage,eid,receipt)
 try:
  with patch.object(controller,'clk',lambda:clock[0]),patch.object(validate,'result',stalled):result=controller.execute(profile,out,ledger,lambda *a,**kw:None,transfer=transfer)
  assert result['completed']==1 and clock[0]-100>60
  print(json.dumps({'status':'CONFIRMED_V3_PER_FILE_POSTTRANSFER_DEADLINE_GAP','actual_controller':True,'wall_stall_seconds':.03,'accelerated_elapsed_seconds':61,'not_a_61second_wallclock_claim':True,'validation_alarm_observation':seen,'observed_result':result['status'],'completed':result['completed'],'public_connections':0,'global_ledger_writes':0},indent=2))
 finally:ledger.close()
