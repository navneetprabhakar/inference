#!/usr/bin/env python3
"""Prepare a small explicit SFT review packet; never approve from metadata."""
# Creator: Navneet Prabhakar
from collections import Counter, defaultdict
import json
from pathlib import Path
import unicodedata
from slm.common.tokenizer import BPE
from slm.data.review_stream import open_checked
from slm.data.schema import digest
from slm.data.tokenized import sha


ROOT = Path('data/iteration-three-sft-review-v1')
PARENT = Path('data/iteration-two-foundation-research-v1')
TOKENIZER = Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
PRIOR = Path('data/delegated-dialogue-review-v2/decisions.json')
SEED = 'iteration-three-explicit-short-sft-review-20261019-v1'


def normalized(text):
    return unicodedata.normalize('NFC', text).strip()


def main():
    if ROOT.exists():
        raise FileExistsError(ROOT)
    sources = json.loads((PARENT/'sources.json').read_text())
    prior = json.loads(PRIOR.read_text())
    if any(prior['source_reviews'][k]['source_record'] != v for k, v in sources.items()):
        raise ValueError('Prior source records differ')
    bpe = BPE.load(TOKENIZER)
    buckets = defaultdict(list)
    with open_checked(PARENT) as index:
        for text, in index.db.execute('SELECT data FROM approved ORDER BY eid'):
            row = json.loads(text)
            if row['source'] not in ('OpenAssistant/oasst2', 'databricks/databricks-dolly-15k'):
                continue
            messages = row['messages']
            if (messages[-1]['role'] != 'assistant' or len(messages) > 4
                    or any(m['role'] not in ('user', 'assistant') for m in messages)
                    or sum(len(m['content'].encode()) for m in messages) > 700):
                continue
            x, _, mask = bpe.serialize(messages)
            if not 16 <= sum(mask) <= 192 or len(x) > 256:
                continue
            # Interview facts and time-change variants are kept out of this packet.
            content = ' '.join(m['content'].casefold() for m in messages)
            if any(v in content for v in ('mira', 'tara', 'apple', 'meeting', 'caveman', 'hello')):
                continue
            if row['source'] == 'OpenAssistant/oasst2':
                nodes = row['validation_results'].get('dialogue_candidate', {}).get('raw_nodes', [])
                if (len(nodes) != len(messages) or any(n.get('synthetic') is not False
                        or n.get('model_name') or n.get('review_result') is not True
                        or n.get('deleted') or n.get('lang') != 'en' for n in nodes)):
                    continue
            buckets[row['source'], row['split']].append(row)
    selected = []
    groups = set()
    for source in sorted(('OpenAssistant/oasst2', 'databricks/databricks-dolly-15k')):
        for split, size in [('train', 24), ('validation', 4), ('test', 4)]:
            rows = sorted(buckets[source, split], key=lambda r: digest([SEED, r['example_id']]))
            chosen = []
            for row in rows:
                group = row['validation_results']['split_group']
                if group not in groups:
                    groups.add(group)
                    chosen.append(row)
                if len(chosen) == size:
                    break
            if len(chosen) != size:
                raise ValueError('Insufficient distinct groups for frozen packet')
            selected.extend(chosen)
    raw_oasst = Path('data/iteration-two-oasst2-snapshot-v1/trees.jsonl')
    acquisition = json.loads(raw_oasst.with_name('acquisition.json').read_text())
    if sha(raw_oasst) != acquisition['decoded_sha256']:
        raise ValueError('Pinned raw OASST export differs')
    needed = {k for r in selected if r['source'] == 'OpenAssistant/oasst2' for k in r['lineage']}
    nodes = {}
    def walk(node):
        if node['message_id'] in needed:
            if node['message_id'] in nodes:
                raise ValueError('Duplicate selected raw identity')
            nodes[node['message_id']] = node
        for child in node.get('replies', []):
            walk(child)
    for line in raw_oasst.open():
        walk(json.loads(line)['prompt'])
    raw_dolly = Path('data/dolly-complete-v1/rows.jsonl')
    dolly_acquisition = json.loads(raw_dolly.with_name('acquisition.json').read_text())
    # The canonical row identity is the original raw row digest.
    dolly = {digest(r): r for r in map(json.loads, raw_dolly.open())}
    receipts = []
    entries = {}
    for i, row in enumerate(selected):
        if row['source'] == 'OpenAssistant/oasst2':
            path = [nodes[k] for k in row['lineage']]
            for j, (node, message) in enumerate(zip(path, row['messages'])):
                if (node['parent_id'] != (path[j-1]['message_id'] if j else None)
                        or ('user' if node['role'] == 'prompter' else 'assistant') != message['role']
                        or normalized(node['text']) != message['content']):
                    raise ValueError('OASST raw path/text differs')
            raw_binding = digest(path)
        else:
            original = dolly[row['example_id'].split(':', 1)[1]]
            prompt = original['instruction'] + ('\n\nContext:\n'+original['context'] if original['context'] else '')
            if row['messages'] != [dict(role='user', content=normalized(prompt)),
                                   dict(role='assistant', content=normalized(original['response']))]:
                raise ValueError('Dolly original row/text differs')
            raw_binding = digest(original)
        decision = dict(approved=None, english_verified=None, privacy_verified=None, quality_verified=None,
                        content_category=None, upstream_partition=row['official_split'],
                        partition_evidence='Retain checked curated split and original official partition; no split moves.',
                        note='Pending full text review; metadata is not SFT approval.')
        entries[row['example_id']] = dict(record=row, record_sha256=digest(row), decision=decision)
        receipts.append(dict(index=i, example_id=row['example_id'], record_sha256=digest(row),
                             raw_binding_sha256=raw_binding, full_text_read=False))
    ROOT.mkdir()
    packet = dict(version=1, dataset_manifest_sha256=sha(PARENT/'manifest.json'), reviewer='delegated_expert',
                  review_mode='delegated_expert', human_attestation=False,
                  review_authorization=dict(version=1, authorized_by='Navneet Prabhakar',
                    instruction='this is a simple problem statement, you can review as expert',
                    scope='explicit_rows_only', dataset_manifest_sha256=sha(PARENT/'manifest.json'), recorded_on='2026-10-19'),
                  source_reviews=prior['source_reviews'], examples=entries)
    (ROOT/'pending.json').write_text(json.dumps(packet, indent=2, sort_keys=True, ensure_ascii=False)+'\n')
    (ROOT/'raw-receipts.json').write_text(json.dumps(receipts, indent=2, sort_keys=True)+'\n')
    with (ROOT/'readable.jsonl').open('x') as out:
        for i, row in enumerate(selected):
            out.write(json.dumps(dict(index=i, example_id=row['example_id'], source=row['source'], split=row['split'],
                                      messages=row['messages']), ensure_ascii=False)+'\n')
    report = dict(creator='Navneet Prabhakar', version=1, seed=SEED, rows=len(selected), distinct_groups=len(groups),
                  selected_counts=dict(Counter(r['source']+'|'+r['split'] for r in selected)),
                  source_review_file_sha256=sha(PRIOR), parent_manifest_sha256=sha(PARENT/'manifest.json'),
                  raw_oasst_sha256=sha(raw_oasst), raw_dolly_sha256=sha(raw_dolly),
                  pending_sha256=sha(ROOT/'pending.json'), readable_sha256=sha(ROOT/'readable.jsonl'),
                  raw_receipts_sha256=sha(ROOT/'raw-receipts.json'), script_sha256=sha(__file__),
                  approved_rows=0, full_text_read=0, human_attestation=False,
                  scope='Purposive short whole-dialogue packet, 32 per source, distinct checked groups and original splits. Raw path/text matching and reused exact source-review evidence only; no quality approval, neural update or new teacher/cloud call.')
    (ROOT/'preparation.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
