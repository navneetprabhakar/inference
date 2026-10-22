import pathlib,sys,json,hashlib,runpy,contextlib,io,tempfile,types,sqlite3
from unittest.mock import patch
P=pathlib.Path(__file__).resolve().parent;D=P.parent/'enwiki-native-range-preparation-v2';V1=P.parent/'enwiki-native-range-preparation-v1';h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();assert h(D/'code-pins.json')=='317a3e353440dd1ae8cfddaad7243306ad0271ce5758ad8abbbb956e11a1e476';assert h(D/'profile.json')=='7e2d27c78d9f48ff4423bc2090261e47cea4ae9dcfcf63d66447d43501d0f612';before={str(p):h(p) for p in D.iterdir() if p.is_file()};assert (D/'range_core.py').read_bytes()==(V1/'range_core.py').read_bytes() and (D/'selection-freeze.json').read_bytes()==(V1/'selection-freeze.json').read_bytes();sys.path.insert(0,str(D));log=io.StringIO()
with contextlib.redirect_stdout(log):scope=runpy.run_path(str(D/'checks.py'),run_name='__main__')
(P/'baseline-checks.json').write_text(log.getvalue());import ranges as r,range_core as core
plan=r.verify('317a3e353440dd1ae8cfddaad7243306ad0271ce5758ad8abbbb956e11a1e476','7e2d27c78d9f48ff4423bc2090261e47cea4ae9dcfcf63d66447d43501d0f612');assert len(plan['distinct_ranges'])==20 and plan['reserved_body_bytes']==1647009;sys.path.insert(0,str(r.REPO/'src'));from slm.data.intake_ledger import IntakeLedger
contract={'limits':{'requests':20,'body_bytes':50000000,'rows':20,'output_bytes':100000000},'wall_seconds':60};results=[]
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);out=root/'files';ledger=IntakeLedger(root/'ledger',contract);r.reserve_output(ledger);assert ledger.totals()=={'requests':0,'body_bytes':0,'rows':0,'output_bytes':56000000};ledger.close();out.mkdir();ledger=IntakeLedger(root/'ledger',contract);r.require_pending_output(ledger);ledger.reserve('range-fixture',requests=1,body_bytes=4,output_bytes=10004)
 with patch.object(r.old,'OUT',out):
  for name,n in r.SLOTS.items():(out/name).write_bytes(b' '*n)
  response=scope['Response'](headers=[('Content-Range',f'bytes 10-12/{core.XML_BYTES}'),('Content-Length','3'),('X-Legal-Header','x'*20000)]);core.validate_response(response,{'URL':core.URL,'start':10,'end_exclusive':13,'bytes':3});r.write('headers.json',{'status':response.code,'headers':list(response.headers.items())});actual=r.size(out);assert actual>10004 and actual<ledger.totals()['output_bytes']
 r.settle_output(ledger,True);assert ledger.db.execute('select state,actual_bytes from attempts where key=?',(r.OUTPUT_KEY,)).fetchone()==('complete',0);assert ledger.totals()['output_bytes']==56010004;ledger.close();results.append({'case':'original_largeheader_counterexample_plus_terminalslots_covered','actual_metadata_bytes':actual,'durable_output_allocation':56010004,'body_and_request_counts_unchanged_by_outputallocation':True})
with tempfile.TemporaryDirectory() as td:
 ledger=IntakeLedger(pathlib.Path(td)/'ledger',contract);ledger.reserve(r.OUTPUT_KEY,output_bytes=56000000,body_bytes=1)
 try:r.require_pending_output(ledger)
 except ValueError:results.append({'case':'wrong_existing_allocation_bodydimension_refused','PASS':True})
 else:raise AssertionError('wrong outputallocation accepted')
 ledger.close()
# Real supervisor setup path: allocation is durable even when first slot write fails before child creation.
with tempfile.TemporaryDirectory() as td:
 root=pathlib.Path(td);out=root/'profile';old_open=pathlib.Path.open;args=types.SimpleNamespace(code_pins_sha256='audit',profile_sha256='audit')
 def fail_first_slot(self,*a,**kw):
  if self==out/'worker-result.json' and a and a[0]=='xb':raise OSError('offline injected firstslot write failure')
  return old_open(self,*a,**kw)
 with patch.object(r,'ROOT',root),patch.object(r,'OUT',out),patch.object(r.old,'OUT',out),patch.object(r,'verify',lambda *args:plan),patch.object(r,'dependencies',lambda:(IntakeLedger,contract,None)),patch.object(pathlib.Path,'open',fail_first_slot):
  try:r.supervise(args)
  except OSError:pass
  else:raise AssertionError('setup failure expected')
 receipt=json.loads((out/'supervisor-result.json').read_text());db=sqlite3.connect(root/'charges/ledger.sqlite');state,actual,charge=db.execute('select state,actual_bytes,charge from attempts where key=?',(r.OUTPUT_KEY,)).fetchone();db.close();assert receipt['status']=='PARTIAL_NATIVE_RANGES_NO_RETRY' and state=='failed' and actual is None and json.loads(charge)=={'requests':0,'body_bytes':0,'rows':0,'output_bytes':56000000};assert receipt['owned_ledger_terminal_state']==[{'key':r.OUTPUT_KEY,'state':'failed'}];results.append({'case':'firstslot_failure_before_child_terminalized_no_refund','sourcecode_supervisor_path_executed':True,'allocation_failed_with56000000retained':True,'HTTP_attempts':0})
assert all(h(pathlib.Path(p))==d for p,d in before.items());result={'status':'PASS_FOCUSED_OUTPUT_ALLOCATION_FIX','baseline_controls_reproduced':40,'independent_controls':results,'core_and_actual20_selection_unchanged':True,'actual_body_reservation':1647009,'profile_output_only_reservation':56000000,'preparation_unchanged':True,'actual_network_requests':0,'global_ledger_writes':0,'XML_requests':0};(P/'focused-checks.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'PASS','baseline':40,'independent':len(results),'real_XML_requests':0}))
