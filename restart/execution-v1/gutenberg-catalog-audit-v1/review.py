"""Read-only independent catalog predispatch audit, no real acquisition."""
import copy,hashlib,importlib.util,json,os,pathlib,sys,tempfile
from unittest.mock import patch
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'gutenberg-catalog-preparation-v1';sys.path.insert(0,str(S));import catalog as c
h=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest();EXPECTED='2e9b21599cb0b15e6efb301c1e704884cc6a244db9233b650c84bf82aceec6ed';assert h(S/'ready.json')=='83048648ea8e242d7160ed8ec1b727a499f4afc365b5a83dfd44aa3e136a6ccc';assert h(S/'manifest.json')==EXPECTED;c.pins(EXPECTED);inputs={str(p):h(p) for p in S.iterdir() if p.is_file()};cases=[]
# Reexecute byte-identical controls with only their final result redirected.
orig_write=pathlib.Path.write_text

def routed_write(self,data,*args,**kwargs):return orig_write(D/'offline-controls.json' if self==S/'offline-checks.json' else self,data,*args,**kwargs)
with patch.object(pathlib.Path,'write_text',routed_write):exec(compile((S/'check_offline.py').read_bytes(),str(S/'check_offline.py'),'exec'),{'__name__':'__independent_controls__'})

def refuse(fn):
 try:fn()
 except ValueError:return
 raise AssertionError('Expected ValueError')
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)/'manifest';p.write_text(json.dumps({'environment':c.environment(),'files_SHA256':{}}))
 with patch.object(c,'MANIFEST',p):
  refuse(lambda:c.pins(EXPECTED));cases.append('old_empty_manifest_exploit_rejected_by_dispatch_digest')
  refuse(lambda:c.pins(h(p)));cases.append('recomputed_empty_inventory_refused')
with patch.dict(os.environ,{'PGCAT_PARENT_PID':str(os.getppid()),'PGCAT_SHARED_START':str(c.clock())}),patch.object(c,'IntakeLedger',side_effect=AssertionError('Must not touch ledger')):
 refuse(lambda:c.worker('0'*64));cases.append('worker_pin_refusal_precedes_any_ledger_or_output')
with patch.object(sys,'argv',[str(S/'catalog.py'),'--manifest-sha256','0'*64,'--execute']),patch.object(c,'execute',side_effect=AssertionError('Must not dispatch')):
 refuse(c.main);cases.append('main_refuses_wrong_digest_before_dispatch')
with patch.object(sys,'argv',[str(S/'catalog.py'),'--manifest-sha256',EXPECTED,'--worker']),patch.object(c,'worker',return_value=None) as worker:
 c.main();worker.assert_called_once_with(EXPECTED);cases.append('main_passes_exact_digest_to_worker')
# Actual supervisor path with an exclusively local sleeping dummy, no catalog worker.
real_popen=c.subprocess.Popen;captured={};out=D/'offline-dummy-supervisor-v2'
def dummy(command,**kwargs):
 if command[0]=='/bin/ps':return real_popen(command,**kwargs)
 captured['command']=command;captured['env']=kwargs['env'];return real_popen([sys.executable,'-c','import time;time.sleep(30)'],**kwargs)
with patch.object(c,'DEST',out),patch.object(c,'EXTERNAL_SECONDS',.1),patch.object(c,'storage',return_value=0),patch.object(c.subprocess,'Popen',side_effect=dummy):
 try:c.execute(EXPECTED)
 except SystemExit as e:assert e.code==1
assert captured['command'][-2:]==['--manifest-sha256',EXPECTED] and '--worker' in captured['command'];assert captured['env']['PGCAT_PARENT_PID']==str(os.getpid());terminal=json.loads((out/'supervisor-result.json').read_text());assert terminal['status']=='FAILED' and terminal['reason']=='external600secondcap' and terminal['retry'] is False and terminal['elapsed_seconds']<5;cases.append('actual_supervisor_child_digest_and_parent_identity_propagation');cases.append('actual_local_dummy_external_watchdog_and_no_retry')
# Verify real parser resolves exact retained native URI, typed fields and body extent.
raw=(c.ROOT/'gutenberg-discovery-pilot-v2/metadata.raw').read_bytes();assert hashlib.sha256(raw).hexdigest()=='8a83ea5ae3629d9347fdb6143d3680be42782d324bc4ccc2410fc520d56fc683';r=c.parse_rdf.parse(raw,'cache/epub/1342/pg1342.rdf');authors=[x for x in r['contributors_and_all_roles'] if x['role_qualified_name']=='{http://purl.org/dc/terms/}creator'];assert len(authors)==1 and authors[0]['stable_agent_ID']==68 and authors[0]['names']==['Austen, Jane'];assert r['explicit_root_xmlbase']=='http://www.gutenberg.org/' and r['languages']==['en'] and r['types']==['Text'];assert any(f['resolved_URL'].endswith('/ebooks/1342.txt.utf-8') and f['extent_bytes']==772386 for f in r['formats']);cases.append('actual_retained_RDF_exact_xmlbase_author68_name_and_text_extent')
assert (c.BODY_CAP,c.OUTPUT_CAP,c.DECODED_CAP,c.RSS_CAP,c.EXTERNAL_SECONDS,c.WORKER_SECONDS)==(160000000,1000000000,4000000000,1000000000,600,570);cases.append('all_approved_numeric_caps_exact')
assert all(h(pathlib.Path(p))==v for p,v in inputs.items());result={'status':'PASS_FOCUSED_INDEPENDENT_REVIEW_NO_CONFIRMED_BLOCKER','ready_SHA256':inputs[str(S/'ready.json')],'parent_manifest_SHA256':EXPECTED,'baseline_controls':json.loads((D/'offline-controls.json').read_text())['case_count'],'independent_cases':cases,'input_SHA256':inputs,'preparation_inputs_unchanged':True,'static_review':{'one_precharged_GET':True,'durable_IntakeLedger_before_IO':True,'response_fullEOF_or_stop_with_160MB_reservation':True,'strict_pinned_CA_CERT_REQUIRED_hostname_TLS12':True,'no_redirect_retry_fallback_or_body_follow':True,'full_tar_EOF_and_bzip2_CRC_all_streams':True,'unsupported_tar_profiles_stop_closed':True,'metadata_holds_not_hidden_as_originalEnglish_or_usable_prose':True,'main_and_worker_manifest_bound_to_exact_external_digest_and_inventory':True},'scope_limits':['Actual mutable daily catalog transfer and source-profile compatibility remain unexecuted.','Metadata English/Text is not proof of original English or edition rights.','RSS is sampled; transient unobserved peaks not proven absent.'],'network_requests':0,'global_ledger_writes':0,'acquisition_worker_launched':False};(D/'review.json').write_text(json.dumps(result,indent=2)+'\n');manifest={str(p.relative_to(D)):h(p) for p in D.rglob('*') if p.is_file() and p.name!='manifest.json'};(D/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'status':result['status'],'baseline_controls':result['baseline_controls'],'independent_cases':len(cases),'manifest_SHA256':h(D/'manifest.json')}))
