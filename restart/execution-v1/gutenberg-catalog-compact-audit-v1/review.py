import ast,copy,hashlib,json,os,pathlib,sqlite3,sys,tempfile,zlib
from unittest.mock import patch
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'gutenberg-catalog-compact-preparation-v1';sys.path.insert(0,str(S));import compact as c
h=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest();EXPECTED='3241ed2ea04521f35fe51b0d504d80c2be7a7f818a9363c3cbfa6d0c079e288a';assert h(S/'ready.json')=='30e2d37f09ad68768b25b19fab6024f2dec6b971c7d4078d99c4d58bb1887715';assert h(S/'manifest.json')==EXPECTED and h(S/'compact.py')=='57f1ed572a1f10e01e5d0347ff5641b19bbcfc3d208308e1350440c9c4e06520';c.pins(EXPECTED);inputs={str(p):h(p) for p in S.iterdir() if p.is_file()};cases=[]
orig=pathlib.Path.write_text
def route(self,data,*a,**kw):return orig(D/'offline-controls.json' if self==S/'offline-checks.json' else self,data,*a,**kw)
with patch.object(pathlib.Path,'write_text',route):exec(compile((S/'check_offline.py').read_bytes(),str(S/'check_offline.py'),'exec'),{'__name__':'__audit_controls__'})
def refuse(fn):
 try:fn()
 except ValueError:return
 raise AssertionError('ValueError required')
with tempfile.TemporaryDirectory() as td:
 p=pathlib.Path(td)/'manifest';p.write_text(json.dumps({'environment':c.environment(),'files_SHA256':{}}))
 with patch.object(c,'MANIFEST',p):refuse(lambda:c.pins(EXPECTED));refuse(lambda:c.pins(h(p)))
 cases.append('empty_registry_rejected_by_external_digest_and_exact_inventory')
with patch.object(sys,'argv',['compact','--manifest-sha256','0'*64,'--execute']),patch.object(c,'execute',side_effect=AssertionError('Must not create outputs')):refuse(c.main)
cases.append('main_bad_digest_refused_before_mutation')
with patch.dict(os.environ,{'PGCOMPACT_PARENT_PID':str(os.getppid()),'PGCOMPACT_SHARED_START':str(c.clock())}),patch.object(c,'inventory',side_effect=AssertionError('Must not scan')):refuse(lambda:c.worker('0'*64))
cases.append('worker_bad_digest_refused_before_mutation')
with patch.object(sys,'argv',['compact','--manifest-sha256',EXPECTED,'--worker']),patch.object(c,'worker',return_value=None) as worker:c.main();worker.assert_called_once_with(EXPECTED)
cases.append('main_forwards_exact_external_digest_to_worker')
real=c.subprocess.Popen;captured={}
def dummy(command,**kw):
 if command[0]=='/bin/ps':return real(command,**kw)
 captured['command']=command;captured['env']=kw['env'];return real([sys.executable,'-c','import time;time.sleep(30)'],**kw)
out=D/'offline-supervisor-dummy-v2'
with patch.object(c,'DEST',out),patch.object(c,'EXTERNAL_SECONDS',.1),patch.object(c,'storage',return_value=0),patch.object(c.subprocess,'Popen',side_effect=dummy):
 try:c.execute(EXPECTED)
 except SystemExit as e:assert e.code==1
assert captured['command'][-2:]==['--manifest-sha256',EXPECTED] and captured['env']['PGCOMPACT_PARENT_PID']==str(os.getpid());sup=json.loads((out/'supervisor-result.json').read_text());assert sup['status']=='FAILED' and sup['reason']=='external600secondcap' and not sup['retry'] and sup['elapsed_seconds']<5;cases.append('actual_supervisor_digest_parent_propagation_and_local_dummy_watchdog')
# Real retained prefix records, read-only: prove all JSON fields/types survive codec.
db=sqlite3.connect((c.ORIGINAL/'catalog.sqlite3').resolve().as_uri()+'?mode=ro',uri=True);count=0
for member,payload in db.execute('select member,data from records order by member limit 20'):
 row=json.loads(payload);packed=c.pack(row);assert c.unpack(*packed)==row;assert set(c.unpack(*packed))==set(row);assert packed[1]==hashlib.sha256(payload.encode()).hexdigest();count+=1
 assert c.indexes(c.unpack(*packed))==c.indexes(row)
db.close();assert count==20;cases.append('twenty_actual_original_prefix_records_all_fields_types_rawhash_and_queryindexes_roundtrip')
obj={'unknown_nested_future_field':{'unicode':'é日本語','null':None,'booleans':[True,False],'array':[{'empty':{}},[]]},'long':'x'*100000};packed=c.pack(obj);assert c.unpack(*packed)==obj;cases.append('unknown_fields_nested_types_and_unicode_lossless')
blob=zlib.compress(b'x'*1000000);refuse(lambda:c.unpack(12,'0'*64,c.sha(blob),c.CODEC,blob));cases.append('compressed_expansion_stops_at_claimed_rawlength_plus_one')
assert c.RAW_JSON_CAP==16000000 and c.DB_CAP==400000000 and c.HEADROOM==32000000 and c.DECODED_CAP==4000000000 and c.OUTPUT_CAP==1000000000 and c.RSS_CAP==1000000000 and c.EXTERNAL_SECONDS==600 and c.WORKER_SECONDS==570;cases.append('all_reviewed_caps_exact')
# No reachable downloader or ledger import in new entrypoint/reader/parser.
for f in ['compact.py','archive_reader.py','parse_rdf.py']:
 tree=ast.parse((S/f).read_text());imports=[]
 for n in ast.walk(tree):
  if isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
  if isinstance(n,ast.ImportFrom):imports.append(n.module)
 assert not any(x and (x in ['urllib.request','urllib'] or x.split('.')[0] in ['requests','socket','acquire_sources']) for x in imports)
cases.append('new_entrypoint_reader_parser_have_no_network_or_ledger_imports')
assert all(h(pathlib.Path(p))==v for p,v in inputs.items());c.pins(EXPECTED)
result={'status':'PASS_FOCUSED_INDEPENDENT_COMPACT_REVIEW_NO_CONFIRMED_BLOCKER','parent_manifest_SHA256':EXPECTED,'ready_SHA256':inputs[str(S/'ready.json')],'baseline_controls':json.loads((D/'offline-controls.json').read_text())['case_count'],'independent_cases':cases,'input_SHA256':inputs,'all_preparation_and_original_pinned_source_inputs_unchanged':True,'full_archive_reader':'Exact reused strict tar/bzip2 decoder independently reviewed in prior catalog audit; this control suite also checks CRC, trailing bytes, byte caps and complete EOF.','scope_limit':'No actual compact inventory executed. Complete record roundtrip/index/prefix/input hash reconciliation remains mandatory after parent dispatch. Metadata discovery is not original English/rights/quality admission.','network_requests':0,'ledger_mutations':0,'actual_compact_worker_launched':False};(D/'review.json').write_text(json.dumps(result,indent=2)+'\n');manifest={str(p.relative_to(D)):h(p) for p in D.rglob('*') if p.is_file() and p.name!='manifest.json'};(D/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(json.dumps({'status':result['status'],'baseline_controls':result['baseline_controls'],'independent_cases':len(cases),'manifest_SHA256':h(D/'manifest.json')}))
