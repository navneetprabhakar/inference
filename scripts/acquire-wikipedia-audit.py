#!/usr/bin/env python3
"""Bounded pinned English Wikipedia audit, not corpus or license admission."""
# Creator: Navneet Prabhakar
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import re
import shutil
import urllib.error
from urllib.parse import urlencode

from slm.common.tokenizer import BPE
from slm.data.acquire import fetch
from slm.data.schema import Source, digest
from slm.data.staging import canonical
from slm.data.tokenized import sha

ROOT = Path('data/wikipedia-distributed-audit-v1')
DATASET = 'wikimedia/wikipedia'
REVISION = 'b04c8d1ceb2f5cd4588862100d08de323dccfbaa'
CONFIG = '20231101.en'
SEED = 'wikipedia-source-review-20261019-v1'


def publish(path, value):
    with path.open('x') as out: out.write(canonical(value) + '\n')


def main():
    if ROOT.exists(): raise FileExistsError(ROOT)
    raw_info, _ = fetch('https://huggingface.co/api/datasets/' + DATASET)
    info = json.loads(raw_info)
    if info['sha'] != REVISION or info['cardData']['license'] != ['cc-by-sa-3.0', 'gfdl']:
        raise ValueError('Pinned dataset revision/published license metadata differs')
    card, _ = fetch(f'https://huggingface.co/datasets/{DATASET}/raw/{REVISION}/README.md')
    declared = re.search(r'^license:\n((?:- .*\n)+)', card.decode(), re.M)
    if declared is None or declared.group(1).splitlines() != ['- cc-by-sa-3.0', '- gfdl']:
        raise ValueError('Exact published card license options required')
    params = dict(dataset=DATASET, config=CONFIG, split='train')
    size_raw, _ = fetch('https://datasets-server.huggingface.co/size?' + urlencode(params))
    size = json.loads(size_raw)
    selected = [s for s in size['size']['splits'] if s['config'] == CONFIG and s['split'] == 'train']
    if size['partial'] is not False or len(selected) != 1: raise ValueError('Complete exact-config size metadata required')
    n = selected[0]['num_rows']; offsets = [n * k // 8 for k in (1, 3, 5, 7)]
    frozen = Path('data/fineweb-prose-candidate-staging-v1/staged/heldout-groups.json')
    if sha(frozen) != json.loads((frozen.parent / 'manifest.json').read_text())['files'][frozen.name]:
        raise ValueError('Current ancestral heldout map differs')
    ROOT.mkdir(); source_dir = ROOT / 'source'; source_dir.mkdir()
    (source_dir / 'card.txt').write_bytes(card); (ROOT / 'dataset-info.json').write_bytes(raw_info)
    (ROOT / 'size-response.json').write_bytes(size_raw)
    # Preserve the card's declaration, not a claimed resolution of operative rights.
    license3 = Path('data/audit-v1/dolly/source/license.txt')
    prior = json.loads(Path('data/audit-v1/dolly/source/source.json').read_text())
    if sha(license3) != prior['license_text_sha256']: raise ValueError('Cached SPDX license evidence differs')
    shutil.copyfile(license3, source_dir / 'license-cc-by-sa-3.0.txt')
    extra = []
    for code in ('CC-BY-SA-4.0', 'GFDL-1.3-only'):
        url = f'https://raw.githubusercontent.com/spdx/license-list-data/v3.27.0/text/{code}.txt'
        raw, _ = fetch(url); path = source_dir / (code + '.txt'); path.write_bytes(raw)
        extra.append(dict(url=url, file=path.name, bytes=len(raw), sha256=sha(path)))
    legal_url = 'https://dumps.wikimedia.org/legal.html'
    try:
        raw, _ = fetch(legal_url); path = source_dir / 'current-dump-licensing.html'; path.write_bytes(raw)
        legal_access = dict(url=legal_url, status='downloaded', sha256=sha(path), bytes=len(raw))
    except urllib.error.HTTPError as error:
        legal_access = dict(url=legal_url, status='http_error', http_code=error.code,
                            scope='No bypass or substitute live-page download.')
    source = Source(DATASET, REVISION, 'https://huggingface.co/datasets/' + DATASET, 'cc-by-sa-3.0',
                    sha(source_dir / 'license-cc-by-sa-3.0.txt'), sha(source_dir / 'card.txt'),
                    ('https://dumps.wikimedia.org/', 'https://en.wikipedia.org/'))
    publish(source_dir / 'source.json', dict(**asdict(source), evidence_files=dict(card='card.txt', license='license-cc-by-sa-3.0.txt')))
    publish(source_dir / 'licensing-review.json', dict(creator='Navneet Prabhakar',
        card_declared_licenses=info['cardData']['license'], declared_primary_label='cc-by-sa-3.0',
        current_official_guide_observed='CC-BY-SA4.0 and GFDL, with exceptions; card lists3.0/GFDL.',
        supplemental_license_texts=extra, current_guide_access=legal_access,
        status='unresolved_before_training_admission', training_approved=False,
        scope='Source license_id records the pinned card declaration only. Do not infer the operative license for every document, downstream model obligations, rights clearance or training admission. Preserve article identity/URL and attribution lineage.'))
    plan = dict(creator='Navneet Prabhakar', kind='bounded-wikipedia-distributed-audit-v1', source=asdict(source),
                config=CONFIG, split='train', offsets=offsets, rows_per_offset=16,
                per_response_byte_cap=4 * 1024**2, total_page_body_byte_cap=16 * 1024**2,
                review_rows_per_cluster=4, review_min_characters=500, review_max_characters=12000,
                selection_seed=SEED, frozen_heldouts_sha256=sha(frozen), script_sha256=sha(__file__),
                group_rule='wikimedia/wikipedia:en:<article-id>; language namespaces IDs and snapshot date is separate provenance.',
                selection='Four distant16-row clusters at octile centers, not uniform random documents. Review up to4 complete500–12000character records per cluster by fixed hash priority; length-conditioned quality outcomes only.',
                training_approved=False)
    publish(ROOT / 'plan.json', plan)
    heldouts = json.loads(frozen.read_text()); records = []; pages = []; total = 0; seen = set()
    for cluster, offset in enumerate(offsets):
        url = 'https://datasets-server.huggingface.co/rows?' + urlencode(dict(**params, offset=offset, length=16))
        raw, headers = fetch(url); total += len(raw)
        if total > plan['total_page_body_byte_cap']: raise ValueError('Page body byte cap exceeded')
        path = ROOT / f'page-{cluster:02d}.json'; path.write_bytes(raw)
        revision = next((v for k, v in headers.items() if k.lower() == 'x-revision'), None)
        body = json.loads(raw)
        if revision != REVISION or body.get('partial') or len(body['rows']) != 16: raise ValueError('Exact complete pinned page required')
        for i, entry in enumerate(body['rows']):
            row = entry['row']
            if set(row) != {'id', 'url', 'title', 'text'} or any(not isinstance(v, str) for v in row.values()):
                raise ValueError('Exact article schema required')
            if entry.get('truncated_cells') or entry['row_idx'] != offset + i or not row['text'].strip() or row['id'] in seen:
                raise ValueError('Complete distinct unchanged article required')
            if not row['url'].startswith('https://en.wikipedia.org/wiki/'): raise ValueError('English article URL required')
            seen.add(row['id']); group = DATASET + ':en:' + row['id']
            records.append(dict(cluster=cluster, global_row_index=entry['row_idx'], source_group=group,
                raw_record_sha256=digest(row), config=CONFIG, original_frozen_partition=heldouts.get(group), row=row))
        pages.append(dict(cluster=cluster, offset=offset, bytes=len(raw), sha256=sha(path), revision=revision, url=url))
        print(json.dumps(dict(cluster=cluster, rows=16, bytes=len(raw))), flush=True)
    with (ROOT / 'rows.jsonl').open('x') as out:
        for row in records: out.write(canonical(row) + '\n')
    chosen = []; review_eligible = {}
    for cluster in range(4):
        eligible = [r for r in records if r['cluster'] == cluster and r['original_frozen_partition'] is None
                    and 500 <= len(r['row']['text']) <= 12000]
        review_eligible[cluster] = len(eligible)
        chosen.extend(sorted(eligible, key=lambda r: (digest([SEED, r['source_group']]), r['source_group']))[:4])
    with (ROOT / 'review.jsonl').open('x') as out:
        for i, row in enumerate(chosen): out.write(canonical(dict(index=i, **row)) + '\n')
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    report = dict(creator='Navneet Prabhakar', kind=plan['kind'], plan_sha256=sha(ROOT / 'plan.json'),
        source_revision=REVISION, config=CONFIG, upstream_rows=n, pages=pages, actual_rows=len(records),
        successful_page_body_bytes=total, row_file_sha256=sha(ROOT / 'rows.jsonl'),
        review_file_sha256=sha(ROOT / 'review.jsonl'), review_rows=len(chosen), review_eligible_by_cluster=review_eligible,
        review_characters=sum(len(r['row']['text']) for r in chosen),
        actual_student_bpe_content_tokens=sum(len(bpe.encode(r['row']['text'])) for r in records),
        source_licensing_review_sha256=sha(source_dir / 'licensing-review.json'), training_approved=False,
        scope='Bounded schema/provenance/coverage audit only; no admission or quality/accuracy/privacy guarantee. Review selection is clustered and length-conditioned. Metadata/license/protocol/HTTP overhead is outside successful page-body count.')
    publish(ROOT / 'acquisition.json', report)
    publish(Path('reports/milestone-seventy-two-wikipedia-acquisition.json'), report)
    print(json.dumps({k: report[k] for k in ('actual_rows', 'review_rows', 'review_characters', 'actual_student_bpe_content_tokens')}, indent=2))


if __name__ == '__main__': main()
