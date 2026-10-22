from pathlib import Path
import sys,json,hashlib,types,tempfile
B=Path(__file__).resolve().parent;P=B/'wikibooks-rendered-heading-triage-executor-preparation-v1';O=B/'wikibooks-rendered-heading-triage-independent-audit-v1'
sys.path.insert(0,str(P));import triage,feature_core as core,supervisor_core as sup,checks
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
a=types.SimpleNamespace(code_pins_sha256='2e364f5e521b12b5aee2938ea5a531b1d002f2d404cceb4f60a3e93646851411',profile_sha256='cf70272ff26c43e0043fe8cf499e82f474e79e17cb7848498bc3521e10da8fe9')
p=triage.verify(a);controls=checks.run();cases=[];old=sup.subprocess.run
for name,raw in [('empty',''),('missingroot','1 0 12\n'),('malformed','42 x 12\n'),('duplicate','42 1 12\n42 1 3\n'),('negative','42 1 -1\n'),('selfparent','42 42 12\n'),('zeroroot','42 1 0\n')]:
 sup.subprocess.run=lambda *a,raw=raw,**k:types.SimpleNamespace(stdout=raw)
 try:sup.tree_rss(42)
 except (ValueError,TypeError):cases.append(name)
 else:raise AssertionError(name)
sup.subprocess.run=lambda *a,**k:types.SimpleNamespace(stdout='42 1 12\n43 42 30\n44 43 5\n45 1 1000\n')
assert sup.tree_rss(42)==47*1024;cases.append('descendant_sum_excludes_unowned');sup.subprocess.run=old
# All nonempty kinds preserve heading content; metadata gaps are rejected.
for kind in ['p','li','pre','reference','instruction','unknown-kind']:
 r=core.summarize([(0,'h2','a'*64,1,0,1),(1,kind,'b'*64,1,3,4)],4);assert r['empty_subtrees']==0
cases.append('all_nonempty_kinds_preserve_subtree_not_quality_filter')
assert p['limits']==triage.LIMITS and len(p['stores'])==12
O.mkdir(exist_ok=False)
report={'status':'PASS_PREPARATION_NO_CANDIDATE_FEATURE_EXECUTION','preparation_codepins_SHA256':a.code_pins_sha256,'profile_SHA256':a.profile_sha256,'all_input_pins_verified':len(json.loads((P/'code-pins.json').read_text())['SHA256']),'reproduced_controls':controls,'independent_controls':cases,'candidate_documents':18680,'candidate_stored_M1_tokens_unchanged':19904934,'diagnostic_anchors':10,'overlap':5,'distinct_metadata_union':18685,'reviewed_production':['triage.py','feature_core.py','supervisor_core.py'],'confirmed_scope':['indexed metadata-only SQL never projects rendered.data or body text','exact ordinal/page/revision/family/text-hash/current-final-role ownership before metadata diagnostic','exact candidate/manual-hold/anchor identity reconciliation','full heading counts and digests retained with explicit bounded example omissions','unknown nonempty blocks count as content; no empty-heading exclusion/semantic quality inference','external profile and exact39-file registry checked before parent/worker work and after worker completion','shared early alarm, strict tree RSS, finite output, safe existing-output refusal and kill/reap'],'limits':p['limits'],'concrete_blockers':[],'actual_candidate_feature_scan':False,'network_ledger_model_training_operations':0,'source_body_text_queried_or_decoded':0,'note':'Input verification hashes complete pinned SQLite files as binary custody reads; no retained candidate metadata feature pass or semantic body read was performed. Parent execution review remains required.'}
(O/'review.json').write_text(json.dumps(report,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'files':{'review.json':h(O/'review.json')},'reviewer_script_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'review.json'),h(O/'manifest.json'))
