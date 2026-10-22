import pathlib,sys,runpy,contextlib,io,tempfile,json,urllib.error
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parent;D=P.parent/'gutenberg-cohort-acquisition-preparation-v1';sys.path.insert(0,str(D));log=io.StringIO()
with contextlib.redirect_stdout(log):scope=runpy.run_path(str(D/'checks.py'),run_name='__main__')
(P/'baseline-checks.json').write_text(log.getvalue());a=scope['a'];Ledger=scope['IntakeLedger'];Response=scope['Response'];rows=[]
for label,error,redirect in [('URLError_firsthop',urllib.error.URLError('offline synthetic TLS/connection failure'),False),('Timeout_firsthop',TimeoutError('offline synthetic connect timeout'),False),('AbsoluteDeadline_firsthop',a.BodyDeadline('offline synthetic body deadline'),False),('URLError_after_redirect',urllib.error.URLError('offline synthetic redirected-hop failure'),True)]:
 with tempfile.TemporaryDirectory() as td:
  root=pathlib.Path(td);out=root/'out';out.mkdir();ledger=Ledger(root/'ledger',{'limits':{'requests':3,'body_bytes':2400000,'rows':1,'output_bytes':2400000},'wall_seconds':30});ledger.reserve('book',body_bytes=2400000,output_bytes=2400000);state={'requests':0,'last_request':None};calls=[]
  def open_fn(opener,url,timeout):
   calls.append(url)
   if redirect and len(calls)==1:return Response(url,302,b'',{'Location':'https://www.gutenberg.org/cache/epub/123/pg123.txt'})
   raise error
  row={'ebook_ID':123,'ordinal':1,'family_component_ID':123,'frame_raw_hash':'audit_fixture','source_binding':{},'metadata_stratum':'audit_fixture','format':{'resolved_URL':'https://www.gutenberg.org/ebooks/123.txt.utf-8'}}
  with patch.object(a.time,'sleep',lambda _:None):receipt=a.transfer(row,out,ledger,'book',None,state,a.clk(),open_fn)
  snap=ledger.snapshot();pending=[x['key'] for x in snap['attempts'] if x['state']=='pending'];assert pending==['book-hop1' if redirect else 'book-hop0'];assert next(x for x in snap['attempts'] if x['key']=='book')['state']=='failed';assert receipt['status']=='FAILED_PARTIAL_NO_RETRY';assert not (out/('pg123-hop'+str(1 if redirect else 0)+'.json')).exists();rows.append({'case':label,'actual_network_requests':0,'mocked_open_attempts':len(calls),'receipt':receipt,'ledger_snapshot':snap,'pending_attempts_despite_terminal_body_receipt':pending,'request_charge_retained':ledger.totals()['requests']});ledger.close()
(P/'counterexamples.json').write_text(json.dumps({'status':'BLOCKER_REPRODUCED_FOUR_OFFLINE_CASES','cases':rows,'actual_network_requests':0,'global_ledger_writes':0},indent=2)+'\n');print(json.dumps({'status':'BLOCKER','offline_cases':4,'baseline_controls':13,'actual_network_requests':0}))
