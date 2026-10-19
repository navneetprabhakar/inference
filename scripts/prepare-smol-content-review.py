#!/usr/bin/env python3
"""Group the pinned train-prefix source with frozen heldouts; select unread texts."""
# Creator: Navneet Prabhakar
from collections import Counter, defaultdict
import json
from pathlib import Path
from slm.data.schema import make_example, digest
from slm.data.build import read_source, verify
from slm.data.staging import stage, canonical
from slm.data.tokenized import sha
from slm.common.tokenizer import BPE


ROOT = Path('data/smol-content-review-v2')
PARENT = Path('data/iteration-two-foundation-research-v1')
FROZEN = Path('data/iteration-two-foundation-candidates-v1/staged')
AUDIT = Path('data/smol-smoltalk-audit-v1')
SOURCE = 'HuggingFaceTB/smol-smoltalk'
TAGS = ('smol-magpie-ultra-short', 'smol-contraints', 'smollm-rewrite-30k',
        'smol-summarize-20k', 'smol-summarize-5k')
SEED = 'smol-content-review-20261019-v1'


def main():
    if ROOT.exists(): raise FileExistsError(ROOT)
    inspected = json.loads((AUDIT/'inspection.json').read_text())
    if inspected['acquisition']['rows_sha256'] != sha(AUDIT/'sample/rows.jsonl'):
        raise ValueError('Pinned train-prefix sample differs')
    source = read_source(AUDIT/'source/source.json')
    if source.revision != inspected['source']['revision']: raise ValueError('Source revision differs')
    ROOT.mkdir()
    incoming = ROOT/'input.jsonl'
    with incoming.open('x') as out:
        for i, line in enumerate((AUDIT/'sample/rows.jsonl').read_text().splitlines()):
            raw = json.loads(line)
            entry = make_example(source, digest(raw), digest(raw['messages']), raw['messages'],
                official_split='train', language='en', task='conversation')
            entry.validation_results['synthetic_origin'] = dict(
                method='pinned-smol-train-prefix-v1', raw_row=digest(raw), raw_messages=digest(raw['messages']),
                prefix_index=i, constituent=raw['source'], acquisition_sha256=sha(AUDIT/'sample/acquisition.json'),
                training_eligible=False, quality_verified=False, language_assessment='publisher_label_only')
            out.write(canonical(entry.to_dict())+'\n')
    descriptors = {read_source(p).source_id: p.resolve() for p in Path('data/audit-v1').glob('*/source/source.json')}
    descriptors['databricks/databricks-dolly-15k'] = Path('data/dolly-complete-v1/source.json').resolve()
    descriptors[SOURCE] = (AUDIT/'source/source.json').resolve()
    inputs = []
    for name, descriptor in sorted(descriptors.items()):
        path = incoming if name == SOURCE else ROOT/(name.split('/')[-1]+'-empty.jsonl')
        if name != SOURCE: path.write_text('')
        inputs.append(dict(path=str(path.resolve()), sha256=sha(path), source_record=str(descriptor), adapter='canonical'))
    limits = dict(max_input_bytes=64*1024**2, max_records=8000, max_record_bytes=1024**2,
                  max_shingles=100000, max_pair_checks=1000000, max_db_bytes=1024**3)
    specification = dict(inputs=inputs, limits=limits, seed=SEED, frozen_dataset=str(FROZEN.resolve()))
    (ROOT/'staging-spec.json').write_text(canonical(specification)+'\n')
    staged = stage(inputs, ROOT/'staged', limits=limits, seed=SEED, frozen_dataset=FROZEN)
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    rows = []; counts = Counter(); lengths = Counter(); frozen = {}; retained = {}
    for split in ('validation', 'test'):
        for p in FROZEN.glob(split+'-*.jsonl'):
            for line in p.open():
                row = json.loads(line); frozen[row['example_id']] = row
    priority = {'train': 0, 'validation': 1, 'test': 2}
    for split in ('train', 'validation', 'test'):
        for p in sorted((ROOT/'staged').glob(split+'-*.jsonl')):
            for line in p.open():
                row = json.loads(line)
                if row['example_id'] in frozen:
                    old = frozen[row['example_id']]
                    if row['messages'] != old['messages'] or priority[row['split']] < priority[old['split']]:
                        raise ValueError('Protected heldout lost or demoted')
                    retained[row['example_id']] = True
                if row['source'] == SOURCE:
                    tag = row['validation_results']['synthetic_origin']['constituent']
                    count = len(bpe.serialize(row['messages'])[0])
                    counts[tag+'|'+split] += 1
                    lengths['within_2048' if count <= 2048 else 'over_2048'] += 1
                    rows.append(row)
    if set(retained) != set(frozen): raise ValueError('Missing protected heldouts')
    buckets = defaultdict(list)
    for row in rows:
        tag = row['validation_results']['synthetic_origin']['constituent']
        if row['split'] == 'train' and tag in TAGS and len(bpe.serialize(row['messages'])[0]) <= 2048:
            buckets[tag].append(row)
    for tag in buckets:
        buckets[tag].sort(key=lambda r: digest([SEED, r['example_id']]), reverse=True)
    selected = []; groups = set()
    while len(selected) < 64 and any(buckets.values()):
        for tag in TAGS:
            while buckets[tag] and len(selected) < 64:
                row = buckets[tag].pop(); group = row['validation_results']['split_group']
                if group not in groups:
                    selected.append(row); groups.add(group); break
    if len(selected) != 64: raise ValueError('Complete group-distinct review packet required')
    with (ROOT/'sample.jsonl').open('x') as out:
        for i, row in enumerate(selected):
            out.write(canonical(dict(index=i, record=row, record_sha256=digest(row), full_text_read=False,
                                     quality_judgment=None, training_approved=False))+'\n')
    verify(ROOT/'staged')
    result = dict(creator='Navneet Prabhakar', version=1, staging=staged,
        parent_manifest_sha256=sha(PARENT/'manifest.json'), frozen_ancestor_manifest_sha256=sha(FROZEN/'manifest.json'), sample_input_sha256=sha(AUDIT/'sample/rows.jsonl'),
        staged_manifest_sha256=sha(ROOT/'staged/manifest.json'), sample_sha256=sha(ROOT/'sample.jsonl'),
        script_sha256=sha(__file__), frozen_rows_preserved=len(frozen), new_rows_by_constituent_split=dict(counts),
        new_row_context_sizes=dict(lengths), selected_train_groups=64,
        selected_constituents=dict(Counter(r['validation_results']['synthetic_origin']['constituent'] for r in selected)),
        training_eligible=False, full_text_reviews=0,
        scope='Train-prefix sample grouped against existing frozen heldouts, 64 distinct train groups selected for full text review. Metadata/canonical grouping only, not source/row/corpus SFT approval, factuality or semantic-decontamination proof. Nonselected original-source components remain ungraded.')
    (ROOT/'preparation.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
