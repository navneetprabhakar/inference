#!/usr/bin/env python3
"""Bounded synthetic-prose source audit, never live generation or admission."""
# Creator: Navneet Prabhakar
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from urllib.parse import urlencode

from slm.common.tokenizer import BPE
from slm.data.acquire import fetch, register
from slm.data.schema import digest
from slm.data.staging import canonical
from slm.data.tokenized import sha

ROOT = Path('data/cosmopedia-distributed-audit-v1')
DATASET = 'HuggingFaceTB/smollm-corpus'
REVISION = '3ba9d605774198c5868892d7a8deda78031a781f'
CONFIG = 'cosmopedia-v2'
MODEL = 'mistralai/Mixtral-8x7B-Instruct-v0.1'
SEED = 'cosmopedia-source-review-20261019-v1'


def publish(path, value):
    with path.open('x') as out: out.write(canonical(value) + '\n')


def main():
    if ROOT.exists(): raise FileExistsError(ROOT)
    info_raw, _ = fetch('https://huggingface.co/api/datasets/' + DATASET)
    info = json.loads(info_raw)
    if info['sha'] != REVISION or info['cardData']['license'] != 'odc-by': raise ValueError('Exact current pinned corpus required')
    query = dict(dataset=DATASET, config=CONFIG, split='train')
    size_raw, _ = fetch('https://datasets-server.huggingface.co/size?' + urlencode(query))
    size = json.loads(size_raw)
    selected = [s for s in size['size']['splits'] if s['config'] == CONFIG and s['split'] == 'train']
    if size['partial'] is not False or len(selected) != 1: raise ValueError('Complete named-subset metadata required')
    n = selected[0]['num_rows']; offsets = [n * k // 8 for k in (1, 3, 5, 7)]
    ROOT.mkdir()
    source = register(DATASET, 'odc-by', ROOT / 'source', revision=REVISION,
        upstream_origins=['https://huggingface.co/datasets/HuggingFaceTB/cosmopedia',
                          'https://huggingface.co/' + MODEL, 'https://huggingface.co/datasets/HuggingFaceFW/fineweb'])
    (ROOT / 'dataset-info.json').write_bytes(info_raw); (ROOT / 'size-response.json').write_bytes(size_raw)
    model_raw, _ = fetch('https://huggingface.co/api/models/' + MODEL)
    model_info = json.loads(model_raw); model_revision = model_info['sha']
    card_url = f'https://huggingface.co/{MODEL}/raw/{model_revision}/README.md'
    card, _ = fetch(card_url)
    if model_info['cardData']['license'] != 'apache-2.0' or b'license: apache-2.0' not in card:
        raise ValueError('Published generator model license metadata differs')
    (ROOT / 'source/generator-info.json').write_bytes(model_raw)
    (ROOT / 'source/generator-card.txt').write_bytes(card)
    license_url = 'https://raw.githubusercontent.com/spdx/license-list-data/v3.27.0/text/Apache-2.0.txt'
    license_text, _ = fetch(license_url); (ROOT / 'source/generator-license.txt').write_bytes(license_text)
    publish(ROOT / 'source/generator-receipt.json', dict(creator='Navneet Prabhakar', model=MODEL,
        model_revision=model_revision, card_url=card_url, card_sha256=sha(ROOT / 'source/generator-card.txt'),
        model_info_sha256=sha(ROOT / 'source/generator-info.json'), license_url=license_url,
        license_sha256=sha(ROOT / 'source/generator-license.txt'), declared_model_license='apache-2.0',
        scope='Published generation-model metadata only. No teacher invocation, weights download or student initialization; no blanket output/seed rights or factual clearance. The project conversation teacher remains separate.'))
    frozen_path = Path('data/fineweb-prose-candidate-staging-v1/staged/heldout-groups.json')
    if sha(frozen_path) != json.loads((frozen_path.parent / 'manifest.json').read_text())['files'][frozen_path.name]:
        raise ValueError('Current heldout artifact differs')
    frozen = json.loads(frozen_path.read_text())
    plan = dict(creator='Navneet Prabhakar', kind='bounded-cosmopedia-distributed-audit-v1', source=asdict(source),
        config=CONFIG, offsets=offsets, rows_per_offset=16, per_page_body_byte_cap=4 * 1024**2,
        total_page_body_byte_cap=16 * 1024**2, review_per_cluster=4, review_min_characters=500,
        review_max_characters=16000, seed=SEED, script_sha256=sha(__file__),
        frozen_heldouts_sha256=sha(frozen_path), generator_receipt_sha256=sha(ROOT / 'source/generator-receipt.json'),
        family_rule='Exact full generation-prompt hash within cosmopedia-v2. seed_data is a source label, not a proven underlying document ID; shared/rephrased seeds remain unresolved.',
        selection='Four distant16-row octile-center clusters; up to4 distinct-prompt500–16000character full texts per cluster by frozen hash priority. Not representative quality estimates or assistant-role demonstrations.',
        training_approved=False)
    publish(ROOT / 'plan.json', plan)
    records = []; pages = []; seen = set(); total = 0
    for cluster, offset in enumerate(offsets):
        url = 'https://datasets-server.huggingface.co/rows?' + urlencode(dict(**query, offset=offset, length=16))
        raw, headers = fetch(url); total += len(raw)
        if total > plan['total_page_body_byte_cap']: raise ValueError('Dataset page-body cap exceeded')
        path = ROOT / f'page-{cluster:02d}.json'; path.write_bytes(raw)
        revision = next((v for k, v in headers.items() if k.lower() == 'x-revision'), None)
        body = json.loads(raw)
        if revision != REVISION or body.get('partial') or len(body['rows']) != 16: raise ValueError('Complete exact-revision page required')
        for i, entry in enumerate(body['rows']):
            row = entry['row']
            if set(row) != {'prompt', 'text', 'token_length', 'audience', 'format', 'seed_data'} or type(row['token_length']) is not int or row['token_length'] <= 0:
                raise ValueError('Exact generation schema required')
            if any(not isinstance(row[k], str) or not row[k].strip() for k in ('prompt', 'text', 'audience', 'format', 'seed_data')) or entry.get('truncated_cells') or entry['row_idx'] != offset + i:
                raise ValueError('Complete untruncated generation metadata/text required')
            fingerprint = digest(row)
            if fingerprint in seen: raise ValueError('Repeated exact source record')
            seen.add(fingerprint); group = DATASET + ':' + CONFIG + ':prompt:' + digest(row['prompt'])
            records.append(dict(cluster=cluster, global_row_index=entry['row_idx'], source_group=group,
                raw_record_sha256=fingerprint, original_frozen_partition=frozen.get(group), row=row))
        pages.append(dict(cluster=cluster, offset=offset, url=url, bytes=len(raw), sha256=sha(path), revision=revision))
        print(json.dumps(dict(cluster=cluster, rows=16, bytes=len(raw))), flush=True)
    with (ROOT / 'rows.jsonl').open('x') as out:
        for row in records: out.write(canonical(row) + '\n')
    chosen = []; families = set(); eligible_counts = {}
    for cluster in range(4):
        eligible = [r for r in records if r['cluster'] == cluster and r['original_frozen_partition'] is None
                    and 500 <= len(r['row']['text']) <= 16000]
        eligible_counts[cluster] = len(eligible); count = 0
        for row in sorted(eligible, key=lambda r: (digest([SEED, r['raw_record_sha256']]), r['raw_record_sha256'])):
            if row['source_group'] in families: continue
            families.add(row['source_group']); chosen.append(row); count += 1
            if count == 4: break
    with (ROOT / 'review.jsonl').open('x') as out:
        for i, row in enumerate(chosen): out.write(canonical(dict(index=i, **row)) + '\n')
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    report = dict(creator='Navneet Prabhakar', kind=plan['kind'], plan_sha256=sha(ROOT / 'plan.json'),
        config=CONFIG, source_revision=REVISION, upstream_rows=n, pages=pages, actual_rows=len(records),
        successful_page_body_bytes=total, raw_file_sha256=sha(ROOT / 'rows.jsonl'),
        review_file_sha256=sha(ROOT / 'review.jsonl'), review_rows=len(chosen), eligible_by_cluster=eligible_counts,
        review_characters=sum(len(r['row']['text']) for r in chosen),
        exact_prompt_families=len({r['source_group'] for r in records}),
        audiences=dict(Counter(r['row']['audience'] for r in records)), formats=dict(Counter(r['row']['format'] for r in records)),
        seed_labels=dict(Counter(r['row']['seed_data'] for r in records)),
        actual_student_bpe_text_tokens=sum(len(bpe.encode(r['row']['text'])) for r in records),
        upstream_mistral_token_lengths=sum(r['row']['token_length'] for r in records), training_approved=False,
        scope='Named synthetic-prose subset only; no fineweb-edu-dedup/python-edu download or source double-counting. Raw prompts retained for provenance, not authorized training targets. No live generation, model update, corpus admission or factual/rights guarantee.')
    publish(ROOT / 'acquisition.json', report)
    publish(Path('reports/milestone-seventy-three-cosmopedia-acquisition.json'), report)
    print(json.dumps({k: report[k] for k in ('actual_rows', 'review_rows', 'review_characters', 'audiences', 'formats', 'seed_labels', 'actual_student_bpe_text_tokens')}, indent=2))


if __name__ == '__main__': main()
