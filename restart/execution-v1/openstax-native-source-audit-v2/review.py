import copy,hashlib,importlib.util,json,os,pathlib,sys,tempfile,time
from unittest.mock import patch
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'openstax-native-source-preparation-v2';V1=D.parent/'openstax-native-source-preparation-v1'
spec=importlib.util.spec_from_file_location('acquire',S/'acquire.py');a=importlib.util.module_from_spec(spec);sys.modules['acquire']=a;spec.loader.exec_module(a)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected='cc88641ad05d1a121bc628655fb2c237a679443e79cc28896e45fc0aea4a3459'
assert sha(S/'ready.json')=='1d13611bd274e92870b36561e19da499c051f738f310cb62523423899f4483d5'
assert sha(a.PINS)==expected
inputs={str(S/n):sha(S/n) for n in ['acquire.py','check_offline.py','policy.json','code-pins.json','ready.json','offline-checks.json']}
policy,pin=a.pins(expected);cases=[]
def refuse(fn):
 try:fn()
 except ValueError:return
 raise AssertionError('Expected refusal')
assert (S/'policy.json').read_bytes()==(V1/'policy.json').read_bytes();cases.append('policy_and_source_evidence_inventory_exactly_unchanged')
paths=a.bound_input_paths();run=D/'offline-control-run';run.mkdir(exist_ok=True)
with patch.object(a,'HERE',run),patch.object(a,'bound_input_paths',lambda:paths):
 exec(compile((S/'check_offline.py').read_bytes(),str(S/'check_offline.py'),'exec'),{'__name__':'__audit_controls__'})
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)/'pins.json';p.write_text(json.dumps({'input_code_SHA256':{}}))
 with patch.object(a,'PINS',p):
  refuse(lambda:a.pins(expected));cases.append('original_empty_registry_exploit_refused_by_dispatch_digest')
  refuse(lambda:a.pins(sha(p)));cases.append('empty_registry_refused_with_recomputed_digest')
  p.write_text(json.dumps({'environment':a.environment_identity(),'input_code_SHA256':{}}))
  refuse(lambda:a.pins(sha(p)));cases.append('empty_inventory_with_valid_runtime_refused')
  changed=copy.deepcopy(pin);changed['input_code_SHA256'].pop(str(a.POLICY.resolve()));p.write_text(json.dumps(changed))
  refuse(lambda:a.pins(sha(p)));cases.append('omitted_policy_inventory_refused')
with patch.dict(os.environ,{'OPENSTAX162_PARENT_PID':str(os.getppid()),'OPENSTAX162_SHARED_START':str(a.clock())}),patch.object(a,'IntakeLedger',side_effect=AssertionError('Ledger must remain untouched')):
 refuse(lambda:a.worker('0'*64));cases.append('worker_rechecks_dispatch_digest_before_ledger')
with patch.object(sys,'argv',[str(S/'acquire.py'),'--code-pins-sha256','0'*64,'--execute']),patch.object(a,'execute',side_effect=AssertionError('Must not execute')):
 refuse(a.main);cases.append('main_rechecks_dispatch_digest_before_dispatch')
with patch.object(sys,'argv',[str(S/'acquire.py'),'--code-pins-sha256',expected,'--worker']),patch.object(a,'worker',return_value=None) as w:
 a.main();w.assert_called_once_with(expected);cases.append('main_propagates_exact_digest_to_worker')
# Exercise actual supervisor path with a local sleeping dummy, never the acquisition worker.
dummy=D/'supervisor-dummy';dummy.mkdir(exist_ok=True);dummy.rmdir()
real_popen=a.subprocess.Popen;captured={}
def spawn(command,**kwargs):
 captured['command']=command;captured['environment']=kwargs['env'];return real_popen([sys.executable,'-c','import time; time.sleep(30)'],**kwargs)
with patch.object(a,'DEST',dummy),patch.object(a,'EXTERNAL_SECONDS',.1),patch.object(a.subprocess,'Popen',side_effect=spawn):
 try:a.execute(expected)
 except SystemExit as e:assert e.code==1
assert captured['command'][-2:]==['--code-pins-sha256',expected] and '--worker' in captured['command']
assert captured['environment']['OPENSTAX162_PARENT_PID']==str(os.getpid())
terminal=json.loads((dummy/'supervisor-result.json').read_text());assert terminal['external_timeout'] and terminal['retry'] is False and terminal['elapsed_seconds']<5
cases.append('supervisor_propagates_exact_digest_and_parent_identity_to_child');cases.append('actual_offline_dummy_watchdog_kills_without_retry')
assert a.CAP==32000000 and a.WORKER_SECONDS==570 and a.EXTERNAL_SECONDS==600 and a.TERMINAL_HEADROOM==524288
assert sum(x['body_cap'] for x in policy['items'])==5565940
assert all(sha(pathlib.Path(n))==h for n,h in inputs.items());cases.append('all_preparation_inputs_unchanged')
report={'status':'PASS_FOCUSED_REVIEW_NO_CONFIRMED_REMAINING_BLOCKER','prior_finding':'FIXED: dispatch digest bound and exact inventory enforced in main and worker','baseline_controls':json.loads((run/'offline-checks.json').read_text())['case_count'],'independent_cases':cases,'source_policy_identical_to_v1':True,'caps_unchanged':True,'code_pins_SHA256':expected,'input_SHA256':inputs,'network_requests':0,'ledger_writes':0,'actual_acquisition_launched':False,'offline_dummy_watchdog':terminal}
(D/'review.json').write_text(json.dumps(report,indent=2)+'\n')
manifest={p.name:sha(p) for p in [D/'review.py',D/'review.json',run/'offline-checks.json']};(D/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'review':str(D/'review.json'),'manifest_SHA256':sha(D/'manifest.json'),'baseline_controls':report['baseline_controls'],'independent_cases':len(cases),'status':report['status']}))
