"""Read-only review of exact v2 fixes; no real source payloads."""
import copy,hashlib,importlib.util,json,pathlib
D=pathlib.Path(__file__).resolve().parent;S=D.parent/'family-validator-preparation-v2';src=S/'validate.py'
spec=importlib.util.spec_from_file_location('family_validator_v2_review',src);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
prior=json.loads((D.parent/'family-validator-audit-v1/counterexample-results.json').read_text())
expected={'known_synthetic_M2_ancestor_with_M5_teacher_inapplicable':'synthetic_ancestor_teacher_inapplicable','whitespace_only_family_identifiers':'empty_or_invalid_family_keys','protected_family_trailing_whitespace_alias':'empty_or_invalid_family_keys','control_exact_protected_key_refuses':'protected_component_exposure','M8_base_axes_only_cross_split':'M8_requires_dataset_specific_validator','control_renamed_protected_parent_cannot_train':'transitive_split_conflict','undeclared_semantic_tool_rename':None,'unicode_noncanonical_identity':'empty_or_invalid_family_keys'}
results=[]
def check(name,b,error):
 try:value=m.validate(b);reason=None
 except m.Refusal as e:value=None;reason=str(e)
 assert reason==error,(name,reason,error)
 results.append({'case':name,'observed_reason':reason,'accepted':reason is None,'outcome_matches_expected':True})
for case in prior['cases']:check(case['name'],copy.deepcopy(case['bundle']),expected[case['name']])
def rebind(b):
 b['receipts']={}
 for r in b['records']:
  r.pop('admission_receipt_sha256',None);receipt={'record_binding_sha256':m.sha(m.canonical(r)),'synthetic_only':True};h=m.sha(m.canonical(receipt));b['receipts'][h]=receipt;r['admission_receipt_sha256']=h
 return b
base=copy.deepcopy(prior['cases'][0]['bundle'])
# A deeper known ancestor must survive multiple honest human-edit generations.
p,c=base['records'];middle=copy.deepcopy(p);middle['record_id']='middle';middle['source_id']='artificial-source:middle';middle['payload_utf8']='Synthetic audit human edit middle';middle['payload_sha256']=m.sha(middle['payload_utf8'].encode());middle['synthetic_generation']=False;middle['parent_record_ids']=[p['record_id']];middle['family_keys']+=['source_document:middle','duplicate_component:middle'];c['parent_record_ids']=['middle'];c['family_keys']+=['source_document:middle','duplicate_component:middle'];base['records']=[p,middle,c]
check('synthetic_grandparent_through_human_edit',rebind(base),'synthetic_ancestor_teacher_inapplicable')
unknown=copy.deepcopy(base);unknown['records'][0].pop('synthetic_generation');check('unknown_grandparent_through_human_edit',rebind(unknown),'unknown_ancestor_teacher_inapplicable')
human=copy.deepcopy(base);human['records'][0]['synthetic_generation']=False;check('fully_known_human_chain_not_blanket_rejected',rebind(human),None)
for value,label in [('record\u200bhidden','format'),('record\nline','control'),('cafe\u0301','NFD'),('record ','padding')]:
 b=copy.deepcopy(prior['cases'][3]['bundle']);r=b['records'][0];r['record_id']=value;check('record_id_'+label,rebind(b),'missing_or_duplicate_record_id')
# Both protection registries receive the same stable-ID checks as records.
b=copy.deepcopy(prior['cases'][3]['bundle']);b['protected_source_ids']=['protected '];check('padded_protected_source_registry',b,'missing_protected_source_registry')
b=copy.deepcopy(prior['cases'][3]['bundle']);b['protected_family_keys']=['source_document:zero\u200bwidth'];check('format_protected_family_registry',b,'missing_protected_family_registry')
out={'status':'PASS_EXACT_V2_FIX_RECHECK_NO_ADDITIONAL_CONFIRMED_ISSUES','validator_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'rechecks':len(results),'results':results,'remaining_issues_in_reviewed_changes':[],'limits':'Exact fixes and declared behavior reviewed; no real ancestry truth, semantic alias discovery, upstream registry completeness or actual release certification inferred.'}
(D/'recheck-results.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'status':out['status'],'rechecks':len(results)}))
