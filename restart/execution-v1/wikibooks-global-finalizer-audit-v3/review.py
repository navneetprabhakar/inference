import hashlib,json,pathlib,sqlite3,subprocess,sys
from unittest.mock import patch
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'wikibooks-global-finalizer-preparation-v3';V2=S.with_name('wikibooks-global-finalizer-preparation-v2');sys.path.insert(0,str(S));import finalize as f;import code_guard as guard
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();EXPECTED='f08d15baa20204a6922a35232a6e9e80dbfbfaca1c0fe9f2e1c8d7bbc78775cf';assert h(S/'code-pins.json')==EXPECTED and h(S/'readiness.json')=='a29d30f5ce0bcbb233e108316a834abb9a2e090bfbddd63c287bc5def3db1893';guard.verify(EXPECTED);inputs={str(p):h(p) for p in S.iterdir() if p.is_file()};cases=[]
for name in ['supervise.py','code_guard.py','check_rules.py','check_controls.py']:assert (S/name).read_bytes()==(V2/name).read_bytes()
old=(V2/'finalize.py').read_text();new=(S/'finalize.py').read_text();added="    if page!=r['page_id'] or rev!=r['revision_id']:raise RuntimeError('outer_SQL_payload_identity_mismatch')\n";assert added in new and new.replace(added,'',1)==old;cases.append('only_production_change_is_outer_page_revision_equality_guard')
# Repeat the exact combined outer-page/revision mutation from the independent v2 exploit.
source=(S/'check_pipeline.py').read_text();needle="(i,i,i+10,'old-unreconciled',json.dumps(r))";assert needle in source;modified=source.replace(needle,"(i,999,9999,'old-unreconciled',json.dumps(r))");real=f.run;observed=[]
def watch(*a,**kw):
 try:return real(*a,**kw)
 except RuntimeError as e:
  out=a[1];receipt=json.loads((out/'result.json').read_text());db=sqlite3.connect(out/'finalized.sqlite3');n=db.execute('select count(*) from pages').fetchone()[0];db.close();observed.append({'exception':str(e),'receipt_status':receipt['status'],'inserted_pages':n});raise
with patch.object(f,'run',side_effect=watch):
 try:exec(compile(modified,str(S/'check_pipeline.py'),'exec'),{'__name__':'__original_counterexample__','__file__':str(S/'check_pipeline.py')})
 except RuntimeError as e:assert str(e)=='outer_SQL_payload_identity_mismatch'
 else:raise AssertionError('Original counterexample unexpectedly accepted')
assert observed==[{'exception':'outer_SQL_payload_identity_mismatch','receipt_status':'PARTIAL_GLOBAL_RECONCILIATION_NO_ADMISSION','inserted_pages':0}];cases.append('exact_v2_counterexample_refused_with_partial_receipt_and_zero_inserted_pages')
counts={}
for name in ['check_rules.py','check_controls.py','check_pipeline.py']:
 out=subprocess.run([sys.executable,str(S/name)],capture_output=True,text=True,check=True,timeout=30);(D/(name+'.stdout')).write_text(out.stdout);counts[name]=json.loads(out.stdout)['passed']
assert counts=={'check_rules.py':14,'check_controls.py':12,'check_pipeline.py':10};cases.append('separate_page_and_revision_tamper_regressions_and_all36_controls_pass')
assert all(h(pathlib.Path(n))==v for n,v in inputs.items());guard.verify(EXPECTED)
result={'status':'PASS_FOCUSED_V3_REVIEW_PRIOR_FINDING_FIXED_NO_NEW_CONFIRMED_ISSUE','external_codepins_SHA256':EXPECTED,'readiness_SHA256':inputs[str(S/'readiness.json')],'independent_cases':cases,'original_counterexample_result':observed,'baseline_controls':counts,'holds_recipe_source_caps_supervisor_and_ownership_unchanged':True,'preparation_inputs_unchanged':True,'input_SHA256':inputs,'execution_limit':'No actual finalizer dispatch; complete residual union and parent-frozen input recipe still required.','actual_corpus_finalizer_run':False,'network_requests':0,'ledger_writes':0};(D/'review.json').write_text(json.dumps(result,indent=2)+'\n');(D/'manifest.json').write_text(json.dumps({p.name:h(p) for p in D.iterdir() if p.is_file() and p.name!='manifest.json'},indent=2)+'\n');print(json.dumps({'status':result['status'],'controls':counts,'manifest_SHA256':h(D/'manifest.json')}))
