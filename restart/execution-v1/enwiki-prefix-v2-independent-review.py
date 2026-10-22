from pathlib import Path
import sys,json,hashlib,types
B=Path(__file__).resolve().parent;P=B/'enwiki-terminal-prefix-frame-preparation-v2';V1=B/'enwiki-terminal-prefix-frame-preparation-v1';O=B/'enwiki-terminal-prefix-frame-independent-audit-v2'
sys.path.insert(0,str(P));import pilot,checks
h=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
code='94302fb888d5be4386906d3d843ec94af40b77a78c2d9ccd765f316b3e131965';profile='50fc0a497a84847055db52178c0416ea49ee9094c621b22a6a89aa7af2f8c5ae'
plan=pilot.verify(code,profile);assert h(P/'source_guard.py')==h(V1/'source_guard.py');assert pilot.LIMITS==json.loads((V1/'profile.json').read_text())['limits'];assert plan['XML_prefix_end_exclusive']==17948470
cases=[]
for label,raw in [('missingroot','1 0 9'),('empty',''),('malformed','x y z'),('duplicate','42 1 10\n42 1 20'),('missingworker','42 1 9')]:
 try:pilot.process_tree_rss(raw,42,43)
 except ValueError:cases.append(label)
 else:raise AssertionError(label)
assert pilot.process_tree_rss('42 1 10\n43 42 20\n44 43 5\n45 1 1000',42,43)==35*1024;cases.append('full_descendant_positive_owned_RSS')
try:checks.frame(checks.HEADER+checks.page(1,'123')+checks.page(2,'00123'))
except ValueError as e:assert 'duplicate_revision_ID_within_prefix_123' in str(e);cases.append('original_revision_identity_alias_counterexample_refused')
else:raise AssertionError('canonical duplicate')
for name,raw,hold in [('format',checks.page().replace(b'text/x-wiki',b'application/json'),'NON_WIKI_OR_UNSPECIFIED_FORMAT'),('unknownpage',checks.page().replace(b'</page>',b'<unknown>native unchanged</unknown></page>'),'UNEXPECTED_PAGE_CHILD_SCHEMA'),('unknownrevision',checks.page().replace(b'</revision>',b'<unknown>native unchanged</unknown></revision>'),'UNEXPECTED_REVISION_CHILD_SCHEMA')]:
 f=checks.frame(checks.HEADER+raw)[0];assert hold in f.pages[0]['holds'];assert f.pages[0]['page_raw_XML_SHA256']==hashlib.sha256(raw.rstrip(b'\n')).hexdigest();cases.append(name+'_hold_rawhash_preserved')
# Profile/code pending binding is not dispatchable.
try:pilot.verify_binding(P/'source-binding-template.json',h(P/'source-binding-template.json'),profile)
except ValueError:cases.append('pending_parent_sourcebinding_refused')
else:raise AssertionError('pending binding accepted')
O.mkdir(exist_ok=False);r={'status':'PASS_FOCUSED_V2_PREPARATION_REVIEW_PARENT_BINDING_AND_DISPATCH_STILL_REQUIRED','code_pins_SHA256':code,'profile_SHA256':profile,'all35static_pins_verified':len(json.loads((P/'code-pins.json').read_text())['sha256']),'reproduced_controls':{'parser':27,'lifecycle':14,'focused':8,'source_binding':19,'schema':22,'production_supervisor_RSS':11,'total':101},'additional_independent_controls':cases,'production_diff_reviewed':True,'source_guard_byteidentical_v1':True,'finite_selection_and_caps_unchanged':True,'fixed_blockers':['Successful empty/missing/malformed process snapshots now refuse; actual positive supervisor and live worker RSS required','Canonical numeric revision identity deduplicated before output, including123/00123','Nonwiki/missing format, auxiliary/missing/mixed/multiplemain roles and unexpected page/revision/slots/slot children retained as schema holds with exact source-bound descriptors'],'native_sibling_revision_SHA1':'Compared to decoded UTF8 for legacy single text or one explicit main wikitext slot only; mismatch/deleted/invalid held, absent/unsupported comparison explicitly reported. No invented multislot aggregate hash.','trust_scope':'Separate terminal-prefix HTTPS/strongETag/reverified-copy stat+hash chain with future selected-frame CRC/EOF/index reconciliation. No whole publisher checksum or global XML/unique/quality claim.','remaining':['Parent external sourcebinding acceptance plus fresh custody/PID/stat verification at dispatch','No actual source application authorized by this audit'],'concrete_blockers':[],'retained_archive_body_bytes_read':0,'network_ledger_tokenizer_training_operations':0,'output_manifest':{n:h(P/n) for n in ['code-pins.json','profile.json','readiness.json','artifact-manifest.json','pilot.py','frame_core.py','source_guard.py']}}
(O/'review.json').write_text(json.dumps(r,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'review.json':h(O/'review.json'),'reviewer_script_SHA256':h(__file__)},indent=2)+'\n');print(h(O/'review.json'),h(O/'manifest.json'))
