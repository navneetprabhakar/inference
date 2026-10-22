from pathlib import Path
import json,hashlib,sys,collections,copy
B=Path.cwd()/'restart/execution-v1';P=B/'wikibooks-semantic-provenance-preparation-v1';O=B/'wikibooks-semantic-alias-independent-audit-v2';O.mkdir(exist_ok=True)
sys.path.insert(0,str(P));import semantic_provenance as s,checks
H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result=checks.run();assert result['controls']==26
old=B/'wikibooks-three-renewed-custody-preparation-v1';entries=json.loads((old/'body-sources.json').read_text());pins=json.loads((old/'code-pins.json').read_text())['input_SHA256'];canonical=json.loads((P/'canonical-stores.json').read_text());actual=s.annotate(entries,canonical,pins);stored=json.loads((P/'body-sources-semantic.json').read_text());assert actual==stored
expected=json.loads((B/'wikibooks-semantic-alias-independent-audit-v1/expected-role-inventory.json').read_text())['expected_roles'];assert len(actual)==len(expected)==837
for a,e in zip(actual,expected):
 assert a['path']==e['path'];assert (a['semantic_coverage_role']==s.WB)==bool(e['expected_semantic_role'])
wb=[a for a in actual if a['semantic_coverage_role']==s.WB];groups=collections.defaultdict(list)
for a in wb:groups[s.alias_signature(a)].append(a['path'])
assert len(wb)==16 and len(groups)==12 and sum(len(v)-1 for v in groups.values())==4
assert len({a['path'] for a in actual})==837
# Actual frozen semantic variants cannot inherit a current WB role solely on physical SHA.
extra=[]
for key,val in [('coverage_role','PROTECTED'),('required_current_candidate_body_coverage',False),('table','other'),('adapter','sqlite_text')]:
 altered=copy.deepcopy(entries);idx=next(i for i,a in enumerate(actual) if a['semantic_coverage_role']==s.WB and a['path'] not in {c['path'] for c in canonical});altered[idx][key]=val;a=s.annotate(altered,canonical,pins);assert a[idx]['semantic_coverage_role']==s.GENERIC;extra.append(key)
report={'status':'PASS_REUSABLE_HELPER_METADATA_AND_SYNTHETIC_ONLY','helper_controls':result,'independent_actual_frame_checks':{'entries':837,'WB_physical_adapters':16,'canonical_hash_stores':12,'extra_physical_aliases':4,'exact_stored_annotation_and_prior_independent_predictor_agree':True,'noncanonical_physical_alias_semantic_variants_refused':extra},'source_pins':{str(p):H(p) for p in [P/'semantic_provenance.py',P/'checks.py',P/'body-sources-semantic.json',P/'canonical-stores.json',P/'code-pins.json',old/'body-sources.json',old/'code-pins.json',B/'wikibooks-semantic-alias-independent-audit-v1/expected-role-inventory.json']},'remaining_integration_obligations':['Expected owner ordinals must derive from complete pinned canonical store, not caller-selected subset.','Observe and validate every actual owner row before full matching; note_compared only after all required comparisons succeed.','Alias inheritance only from completed owner proof in same bound execution; global 89758 identity union must remain exact.','Current helper audit does not certify actual source role coverage or discharge original failed scan.'],'retained_body_rows_parsed':0,'body_comparisons':0,'admissions':0}
(O/'review.json').write_text(json.dumps(report,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'files':{'review.json':H(O/'review.json')}},indent=2)+'\n');print(json.dumps({'review_SHA256':H(O/'review.json'),'manifest_SHA256':H(O/'manifest.json'),'status':report['status']}))
