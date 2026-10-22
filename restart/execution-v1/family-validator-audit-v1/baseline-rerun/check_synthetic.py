"""Fault-sensitive fixtures only; no actual conversations or tool training data."""
import copy
import json
from pathlib import Path
from validate import validate, canonical, sha, Refusal


def record(rid, split='train', stage='M2'):
    axes = ['source_document', 'duplicate_component']
    if stage in ['M5', 'M6', 'M7']:
        axes += ['conversation', 'template', 'teacher_seed']
    if stage in ['M6', 'M7']:
        axes += ['schema', 'workflow']
    return dict(record_id=rid, payload_utf8='synthetic fixture '+rid,
                payload_sha256=sha(('synthetic fixture '+rid).encode()),
                source_id='fixture-source:'+rid, source_snapshot_sha256='a'*64,
                stage=stage, split=split, ancestry_status='known',
                upstream_role='unpartitioned',
                synthetic_generation=True,
                ancestry_evidence='synthetic test only; no actual admitted source',
                role={'train':'training','development':'development',
                      'final':'acceptance','quarantine':'excluded'}[split],
                required_family_namespaces=axes,
                family_keys=[a+':'+rid for a in axes], parent_record_ids=[])


def bundle(records):
    b=dict(records=records, receipts={}, protected_family_keys=[], protected_source_ids=[])
    for r in records:
        r.pop('admission_receipt_sha256', None)
        receipt={'record_binding_sha256':sha(canonical(r)), 'synthetic_only':True}
        h=sha(canonical(receipt)); b['receipts'][h]=receipt
        r['admission_receipt_sha256']=h
    return b


passed=[]
def check(name, b, error=None):
    try:
        validate(b)
    except Refusal as e:
        assert str(e)==error, (name, str(e), error)
    else:
        assert error is None, (name,'did not refuse')
    passed.append(name)


check('nonempty_bound_train', bundle([record('a')]))
check('empty_not_certificate', bundle([]), 'empty_or_invalid_records')
b=bundle([record('a')]); b['records'][0]['payload_utf8']+='changed'
check('payload_tamper',b,'payload_hash_mismatch')
b=bundle([record('a')]); b['records'][0]['family_keys'].append('schema:changed')
check('family_tamper',b,'receipt_record_binding_mismatch')
b=bundle([record('a')]); b['receipts'].clear()
check('missing_receipt',b,'missing_bound_receipt')
b=bundle([record('a')]);next(iter(b['receipts'].values()))['synthetic_only']=False
check('receipt_tamper',b,'receipt_hash_mismatch')
a=record('a');a['ancestry_status']='unknown'
check('unknown_ancestry',bundle([a]),'unknown_ancestry')
a=record('a');a['family_keys']=[]
check('empty_families',bundle([a]),'empty_or_invalid_family_keys')
a=record('a');a['family_keys'].pop()
check('missing_required_family',bundle([a]),'required_family_missing')
a=record('a',stage='M7');a['required_family_namespaces'].remove('schema')
check('missing_tool_schema_axis',bundle([a]),'missing_stage_family_requirements')
a=record('a');a['role']='tokenizer_fit'
check('training_only_tokenizer',bundle([a]))
a=record('a','final');a['role']='tokenizer_fit'
check('final_tokenizer_refusal',bundle([a]),'role_split_conflict')
a,c,d=record('a'),record('c'),record('d','final')
a['family_keys'].append('template:bridge1');c['family_keys']+=['template:bridge1','workflow:bridge2'];d['family_keys'].append('workflow:bridge2')
check('transitive_multi_axis_conflict',bundle([a,c,d]),'transitive_split_conflict')
a,d=record('a'),record('d','final');d['payload_utf8']=a['payload_utf8'];d['payload_sha256']=a['payload_sha256']
check('exact_copy_cannot_escape_families',bundle([a,d]),'transitive_split_conflict')
a,d=record('a'),record('d','final');d['source_id']=a['source_id']
check('stable_source_cannot_escape_families',bundle([a,d]),'transitive_split_conflict')
b=bundle([record('a')]);b['protected_family_keys']=['source_document:a']
check('protected_train',b,'protected_component_exposure')
b=bundle([record('a','development')]);b['protected_source_ids']=['fixture-source:a']
check('protected_development',b,'protected_component_exposure')
b=bundle([record('a','final')]);b['protected_family_keys']=['source_document:a']
check('protected_final_allowed',b)
a=record('a');a['upstream_role']='heldout'
check('upstream_holdout_propagates',bundle([a]),'protected_component_exposure')
a=record('a');a['parent_record_ids']=['absent']
check('missing_parent_refuses',bundle([a]),'missing_parent_record')
a,d=record('a'),record('d');d['parent_record_ids']=['a']
check('dropped_parent_keys',bundle([a,d]),'dropped_parent_family')
d['family_keys']+=a['family_keys']
check('parent_inheritance',bundle([a,d]))
a['parent_record_ids']=['d'];a['family_keys']=d['family_keys'][:]
check('parent_cycle',bundle([a,d]),'parent_cycle')
a,d=record('a'),record('d');d['family_keys'].append('template:bridge');a['family_keys'].append('template:bridge')
b=bundle([a,d]);b['protected_source_ids']=['fixture-source:a']
check('protection_crosses_component',b,'protected_component_exposure')
a,d=record('a','quarantine'),record('d','quarantine');d['family_keys']+=a['family_keys'];d['parent_record_ids']=['a'];a['upstream_role']='excluded'
check('quarantined_derivative_keeps_protection',bundle([a,d]))
a=record('a');a['upstream_role']='unknown'
check('unknown_upstream_refuses',bundle([a]),'missing_or_unknown_upstream_role')
a=record('a');a['upstream_role']='development'
check('upstream_development_cannot_train',bundle([a]),'upstream_development_reassigned')
a=record('a','final');a['upstream_role']='excluded'
check('upstream_excluded_cannot_promote_to_final',bundle([a]),'excluded_upstream_promoted')
a=record('a',stage='M5');a['synthetic_generation']=False
a['required_family_namespaces'].remove('teacher_seed');a['family_keys'].remove('teacher_seed:a')
a['not_applicable_family_namespaces']={'teacher_seed':'Declared human original, no model-generation ancestor; evidence is synthetic fixture only.'}
check('explicit_human_no_teacher_axis',bundle([a]))
a['synthetic_generation']=True
check('synthetic_cannot_claim_teacher_inapplicable',bundle([a]),'synthetic_teacher_ancestry_missing')
a=record('a',stage='M5');a['not_applicable_family_namespaces']={'teacher_seed':'contradiction'}
check('applicable_and_inapplicable_conflict',bundle([a]),'conflicting_family_applicability')
a=record('a');a['stage']='unrecognized'
check('unknown_stage_refuses',bundle([a]),'unknown_stage')
result={'status':'PASS_SYNTHETIC_BINDING_AND_CUSTODY_CHECKS_ONLY',
        'checks':len(passed),'cases':passed,'actual_training_records':0,
        'actual_release_certified':False,'new_admitted_documents':0}
Path(__file__).with_name('synthetic-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
