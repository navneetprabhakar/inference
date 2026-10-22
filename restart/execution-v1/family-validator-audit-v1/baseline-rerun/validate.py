"""Offline lineage/split binding validator. Does not admit records or execute ML."""
import hashlib
import json
from collections import defaultdict


class Refusal(ValueError):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def pin(value):
    return isinstance(value, str) and len(value) == 64 and all(
        c in '0123456789abcdef' for c in value)


def refuse(condition, reason):
    if not condition:
        raise Refusal(reason)


def validate(bundle):
    """Validate exact supplied payload/receipt bindings and transitive custody.

    Required family names are explicit per record, never inferred from text.
    A protected namespace/key blocks its entire connected component from train
    and development; tokenizer_fit is a train-only role. Real upstream source
    integrity and truth of ancestry declarations require separate audits.
    """
    records = bundle.get('records')
    refuse(isinstance(records, list) and bool(records), 'empty_or_invalid_records')
    receipts = bundle.get('receipts')
    refuse(isinstance(receipts, dict), 'missing_receipts')
    protected = bundle.get('protected_family_keys')
    protected_sources = bundle.get('protected_source_ids')
    refuse(isinstance(protected, list) and all(nonempty(x) for x in protected),
           'missing_protected_family_registry')
    refuse(isinstance(protected_sources, list) and all(nonempty(x) for x in protected_sources),
           'missing_protected_source_registry')
    ids, parents, key_owner = {}, {}, {}
    exact_owner, source_owner = {}, {}
    indexed = {}

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    def union(a, b):
        parents[root(a)] = root(b)

    # Payload and canonical receipt bindings precede union/split judgments.
    for r in records:
        refuse(isinstance(r, dict), 'record_not_object')
        rid = r.get('record_id')
        refuse(nonempty(rid) and rid not in ids, 'missing_or_duplicate_record_id')
        ids[rid] = r
        parents[rid] = rid
        for field in ['source_id', 'stage', 'ancestry_evidence']:
            refuse(nonempty(r.get(field)), 'missing_' + field)
        refuse(r['stage'] in ['M'+str(i) for i in range(9)], 'unknown_stage')
        refuse(r.get('ancestry_status') == 'known', 'unknown_ancestry')
        refuse(r.get('upstream_role') in ['train', 'development', 'final',
                                         'heldout', 'excluded', 'unpartitioned'],
               'missing_or_unknown_upstream_role')
        refuse(isinstance(r.get('payload_utf8'), str), 'missing_exact_payload')
        refuse(pin(r.get('payload_sha256')) and
               sha(r['payload_utf8'].encode('utf-8', errors='strict')) == r['payload_sha256'],
               'payload_hash_mismatch')
        refuse(pin(r.get('source_snapshot_sha256')), 'missing_source_snapshot_pin')
        refuse(r.get('split') in ['train', 'development', 'final', 'quarantine'], 'invalid_split')
        refuse(r.get('role') in ['training', 'tokenizer_fit', 'development', 'acceptance', 'excluded'],
               'invalid_role')
        allowed = {'train': {'training', 'tokenizer_fit'},
                   'development': {'development'}, 'final': {'acceptance'},
                   'quarantine': {'excluded'}}
        refuse(r['role'] in allowed[r['split']], 'role_split_conflict')
        keys, required = r.get('family_keys'), r.get('required_family_namespaces')
        refuse(isinstance(keys, list) and bool(keys) and len(set(keys)) == len(keys)
               and all(nonempty(k) and ':' in k and all(k.split(':', 1)) for k in keys),
               'empty_or_invalid_family_keys')
        namespaces = {k.split(':', 1)[0] for k in keys}
        refuse(isinstance(required, list) and bool(required)
               and all(nonempty(n) for n in required), 'missing_family_requirements')
        refuse('source_document' in required and 'duplicate_component' in required,
               'missing_base_family_requirements')
        refuse(set(required) <= namespaces, 'required_family_missing')
        # Later-stage ancestry must include all relevant task generation axes.
        if r['stage'] in ['M5', 'M6', 'M7']:
            axes = {'conversation', 'template', 'teacher_seed'}
            if r['stage'] in ['M6', 'M7']:
                axes |= {'schema', 'workflow'}
            absent = r.get('not_applicable_family_namespaces', {})
            refuse(isinstance(absent, dict) and set(absent) <= {'template', 'teacher_seed'}
                   and all(nonempty(x) for x in absent.values()), 'invalid_nonapplicable_family_evidence')
            refuse(not (set(absent) & (namespaces | set(required))),
                   'conflicting_family_applicability')
            refuse(isinstance(r.get('synthetic_generation'), bool), 'missing_generation_provenance')
            refuse(not (r['synthetic_generation'] and 'teacher_seed' in absent),
                   'synthetic_teacher_ancestry_missing')
            refuse(axes <= set(required) | set(absent), 'missing_stage_family_requirements')
        lineage = r.get('parent_record_ids')
        refuse(isinstance(lineage, list) and len(set(lineage)) == len(lineage)
               and all(nonempty(x) and x != rid for x in lineage), 'invalid_parents')
        receipt_pin = r.get('admission_receipt_sha256')
        refuse(pin(receipt_pin) and receipt_pin in receipts, 'missing_bound_receipt')
        receipt = receipts[receipt_pin]
        refuse(isinstance(receipt, dict) and sha(canonical(receipt)) == receipt_pin,
               'receipt_hash_mismatch')
        # Receipt pins all record fields except its own digest, including families.
        bound = {k: v for k, v in r.items() if k != 'admission_receipt_sha256'}
        refuse(receipt.get('record_binding_sha256') == sha(canonical(bound)),
               'receipt_record_binding_mismatch')
        indexed[rid] = set(keys)
        # Exact payload copies and stable upstream document IDs cannot evade
        # custody by inventing different explicit family labels.
        for owner, identity in [(exact_owner, r['payload_sha256']),
                                (source_owner, r['source_id'])]:
            if identity in owner:
                union(rid, owner[identity])
            else:
                owner[identity] = rid
        for key in keys:
            if key in key_owner:
                union(rid, key_owner[key])
            else:
                key_owner[key] = rid
    # Parent versions must be present to prove inherited protection/families.
    for rid, r in ids.items():
        for parent in r['parent_record_ids']:
            refuse(parent in ids, 'missing_parent_record')
            refuse(indexed[parent] <= indexed[rid], 'dropped_parent_family')
            union(rid, parent)
    visiting, done = set(), set()

    def visit(rid):
        refuse(rid not in visiting, 'parent_cycle')
        if rid in done:
            return
        visiting.add(rid)
        for parent in ids[rid]['parent_record_ids']:
            visit(parent)
        visiting.remove(rid)
        done.add(rid)

    for rid in ids:
        visit(rid)
    components = defaultdict(list)
    for rid in ids:
        components[root(rid)].append(ids[rid])
    for members in components.values():
        splits = {r['split'] for r in members}
        refuse(len(splits) == 1, 'transitive_split_conflict')
        sensitive = any(set(r['family_keys']) & set(protected)
                        or r['source_id'] in protected_sources
                        or r.get('upstream_role') in ['heldout', 'final', 'excluded']
                        for r in members)
        refuse(not sensitive or splits <= {'final', 'quarantine'},
               'protected_component_exposure')
        refuse(not any(r['upstream_role'] == 'excluded' for r in members)
               or splits == {'quarantine'}, 'excluded_upstream_promoted')
        refuse(not any(r['upstream_role'] == 'development' for r in members)
               or splits <= {'development', 'quarantine'}, 'upstream_development_reassigned')
    return {'status': 'SUPPLIED_BINDINGS_AND_COMPONENT_SPLITS_PASS',
            'records': len(records), 'components': len(components),
            'new_admitted_documents': 0,
            'scope': 'No source-content/rights/ancestry-truth or actual evaluation-release certification.'}
