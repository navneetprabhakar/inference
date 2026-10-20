"""Read-only full membership and family/pool audit of the actual English release."""
# Creator: Navneet Prabhakar
import hashlib
import json
from pathlib import Path
import sqlite3
from collections import Counter
from slm.data.english_eligibility import reasons
from slm.data.stream_hash import sha
from slm.common.tokenizer import BPE

ROOT = Path('data/english-recovery-corpus-v1')
OUTPUT = Path('data/english-release-audit-v1')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    with Path(path).open() as stream:
        for line in stream:
            yield json.loads(line)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    require(not OUTPUT.exists(), 'Retain original release-audit attempt')
    policy = read(ROOT/'admission.json'); manifest = read(ROOT/'manifest.json')
    require(policy['training_approved'] is True and policy['human_attestation'] is False
            and policy['content_category'] == 'unreviewed', 'Exact finite private policy required')
    require(manifest['policy_sha256'] == sha(ROOT/'admission.json'), 'Admission hash differs')
    for name, expected in policy['inputs'].items():
        require(sha(name) == expected, 'Pinned admission dependency differs: '+name)
    for name, expected in manifest['files'].items():
        require(sha(ROOT/name) == expected, 'Released file differs: '+name)
    roots = []
    for sid, row in enumerate(lines('data/english-global-components-v1/roots.jsonl')):
        require(row['sid'] == sid, 'Canonical full component source order required')
        roots.append(row['root'])
    require(len(roots) == 235779, 'Full grouping source coverage required')
    components = {r['root']: r for r in lines('data/english-global-components-v1/components.jsonl')}
    denied = {roots[sid] for sid in policy['nonapproval_source_sids']}
    connection = sqlite3.connect('file:'+str(Path('data/global-exact-families-v2/families.sqlite').resolve())+'?mode=ro', uri=True)
    chosen = {}; inspected = 0
    # Rebuild canonical component representatives from the entire immutable input.
    for sid, data, candidate, fixed, blocked, source in connection.execute(
            'SELECT sid,data,candidate,fixed,blocked,ingredient FROM records ORDER BY sid'):
        inspected += 1
        if not candidate or source not in ('general', 'narrative'):
            continue
        raw = json.loads(data); group = components[roots[sid]]
        if fixed or blocked or group['heldout_priority'] or group['blocked'] or roots[sid] in denied or reasons(raw):
            continue
        key = digest(['finite-english-research-v1', raw['id']])
        row = dict(sid=sid, example_id=raw['id'], parent_group_id=group['group_id'],
                   split_group=group['group_id'], source=source, text=raw['texts']['content'],
                   content_sha256=digest(raw['texts']['content']), original_content_tokens=raw['tokens'],
                   reference=raw['reference'])
        draw = int(digest(['english-recovery-split-v1', row['split_group']])[:12], 16) % 10000
        row['split'] = 'validation' if draw < 100 else 'test' if draw < 200 else 'train'
        prior = chosen.get(roots[sid])
        if prior is None or key < prior[0]:
            chosen[roots[sid]] = (key, sid, digest(row))
    connection.close()
    expected = {sid: fingerprint for _, sid, fingerprint in chosen.values()}
    actual = {}; groups = set(); population = Counter(); validation = []
    for split in ('train', 'validation', 'test'):
        for row in lines(ROOT/(split+'.jsonl')):
            sid = row['sid']
            require(sid not in actual and row['split'] == split and expected.get(sid) == digest(row),
                    'Full source membership, original bytes, provenance or split differs')
            require(row['split_group'] not in groups, 'Family occurs in multiple release rows/splits')
            groups.add(row['split_group']); actual[sid] = row; population[split, row['source']] += 1
            if split == 'validation':
                validation.append(row)
    require(set(actual) == set(expected), 'Finite release membership coverage differs')
    pool_ids = set(); pool_groups = set(); pools = {}
    for name in ('preliminary', 'reserved-replay', 'general', 'narrative'):
        count = positions = 0
        for row in lines(ROOT/name/'lineage.jsonl'):
            sid = row['source_sid']; raw = actual.get(sid)
            require(raw is not None and raw['split'] == 'train', 'Heldout/nonmember entered training pool')
            require(sid not in pool_ids and row['split_group'] not in pool_groups,
                    'Preliminary, retention and main families overlap')
            for key in ('example_id', 'parent_group_id', 'split_group', 'source', 'split', 'content_sha256'):
                require(row[key] == raw[key], 'Pool lineage source identity differs')
            require(name not in ('general', 'narrative') or raw['source'] == name, 'Main pool source differs')
            n = raw['original_content_tokens'] + 1
            contribution = n - int(count == 0)
            require((row['encoded_positions'], row['prediction_positions'], row['supervised_positions'],
                     row['prediction_offset_start'], row['prediction_offset_end'])
                    == (n, contribution, contribution, positions, positions+contribution),
                    'Full source/EOS pool position accounting differs')
            pool_ids.add(sid); pool_groups.add(row['split_group']); count += 1; positions += contribution
        require(positions == read(ROOT/name/'manifest.json')['processed_tokens'], 'Pool manifest total differs')
        pools[name] = dict(records=count, one_pass_positions=positions)
    require(pool_ids == {sid for sid, row in actual.items() if row['split'] == 'train'},
            'Training pool partition is incomplete')
    dev = list(lines(ROOT/'development.jsonl')); expected_dev = []
    for source, count in [('general', 200), ('narrative', 300)]:
        expected_dev.extend(sorted((r for r in validation if r['source'] == source),
                                  key=lambda r: digest(['language-dev-v1', r['example_id']]))[:count])
    require(dev == expected_dev and len(dev) == 500, 'Fixed family-disjoint development selection differs')
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    prefixes = []
    for source in ('general', 'narrative'):
        for row in [r for r in dev if r['source'] == source][:50]:
            prefixes.append(dict(example_id=row['example_id'], source=source,
                                 prefix_tokens=bpe.encode(row['text'])[:48], reference_text=row['text']))
    require(read(ROOT/'generation-prefixes.json') == prefixes, 'Original source generation prefixes differ')
    result = dict(creator='Navneet Prabhakar', complete=True, source_records_checked=inspected,
                  exact_admitted_records=len(actual), unique_admitted_families=len(groups),
                  full_original_source_and_provenance_match=True, original_component_flags_preserved=True,
                  family_disjoint_release_splits=True, disjoint_complete_training_pool_partition=True,
                  pools=pools, development_documents=500, generation_prefixes=100,
                  scope='Independent complete canonical membership/lineage/pool/dev audit, using the fixed eligibility predicate. No new content judgment or independent rerun of numeric token reconstruction; the frozen preparer performed that reconstruction.',
                  human_attestation=False, model_improvement_established=False,
                  inputs={str(p):sha(p) for p in [__file__, ROOT/'manifest.json', ROOT/'admission.json',
                                                ROOT/'preparation.json', 'data/english-global-components-v1/report.json']})
    OUTPUT.mkdir()
    for path in [OUTPUT/'report.json', Path('reports/english-release-audit.json')]:
        path.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
