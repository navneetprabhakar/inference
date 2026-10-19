#!/usr/bin/env python3
"""Reopen the actual source audit; no network, admission or student updates."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
from urllib.parse import urlsplit

import pyarrow as pa
import pyarrow.parquet as pq
from slm.common.tokenizer import BPE
from slm.data.schema import digest
from slm.data.tokenized import sha


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def read(path):
    return json.loads(Path(path).read_text())


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def main():
    root = Path('data/fineweb-prose-distributed-audit-v1')
    plan, acquisition, review = (read(root / name) for name in
                                ('plan.json', 'acquisition.json', 'review-report.json'))
    require(sha('scripts/acquire-prose-learning-audit.py') == plan['script_sha256'], 'Acquisition source changed')
    require(sha(root / 'plan.json') == acquisition['plan_sha256'], 'Plan changed')
    heldouts = Path(plan['frozen_heldouts_file'])
    require(sha(heldouts) == plan['frozen_heldouts_sha256'], 'Ancestral heldouts changed')
    require(read(heldouts.parent / 'manifest.json')['files'][heldouts.name] == sha(heldouts), 'Heldout manifest differs')
    frozen = read(heldouts)
    parent = Path('data/audit-v1/fineweb-edu')
    for name, field in (('card.txt', 'card_sha256'), ('license.txt', 'license_text_sha256')):
        require(sha(parent / 'source' / name) == plan['source'][field], 'Source evidence changed')
    require(sha(parent / 'sample/rows.jsonl') == plan['prior_prefix_sha256'], 'Prior prefix changed')
    records = []
    for page in acquisition['pages']:
        path = root / f"page-{page['cluster']:02d}.json"
        require(sha(path) == page['sha256'] and path.stat().st_size == page['bytes'], 'Page bytes differ')
        require(page['bytes'] <= plan['per_response_byte_cap'], 'Page cap exceeded')
        require(page['revision'] == plan['source']['revision'], 'Recorded response revision differs')
        body = read(path)
        require(not body.get('partial') and len(body['rows']) == 16, 'Incomplete page')
        for i, entry in enumerate(body['rows']):
            row = entry['row']
            require(not entry.get('truncated_cells') and entry['row_idx'] == page['offset'] + i, 'Row truncated/reordered')
            group = plan['source']['source_id'] + ':' + row['id']
            records.append(dict(cluster=page['cluster'], global_row_index=entry['row_idx'],
                                source_group=group, raw_record_sha256=digest(row), row=row,
                                original_frozen_partition=frozen.get(group)))
    require(records == lines(root / 'rows.jsonl') and len(records) == 64, 'Actual records differ')
    require(len({r['source_group'] for r in records}) == 64, 'Duplicate groups')
    require(sha(root / 'rows.jsonl') == acquisition['row_file_sha256'], 'Record file changed')
    chosen = []
    for cluster in range(4):
        available = [r for r in records if r['cluster'] == cluster and r['original_frozen_partition'] is None]
        chosen.extend(sorted(available, key=lambda r: (digest([plan['selection_seed'], r['source_group']]), r['source_group']))[:4])
    require([dict(index=i, **r) for i, r in enumerate(chosen)] == lines(root / 'review.jsonl'), 'Review selection changed')
    require(sha(root / 'review.jsonl') == acquisition['review_file_sha256'] == review['review_file_sha256'], 'Review hash differs')
    judgments = lines(root / 'direct-judgments.jsonl')
    require(len(judgments) == 16 and sha(root / 'direct-judgments.jsonl') == review['judgment_file_sha256'], 'Judgment journal differs')
    for i, (row, decision) in enumerate(zip(chosen, judgments)):
        require(decision['index'] == i and decision['source_group'] == row['source_group'] and
                decision['raw_record_sha256'] == row['raw_record_sha256'], 'Judgment binding differs')
        require(decision['review_file_sha256'] == sha(root / 'review.jsonl') and decision['full_text_read'] is True, 'Incomplete reading declaration')
        require(decision['judgment'] in ('consider', 'defer', 'exclude') and bool(decision['reason']), 'Missing decision')
        for field in ('human_attestation', 'training_approved', 'factual_accuracy_verified', 'underlying_document_rights_verified'):
            require(decision[field] is False, 'Unsupported clearance')
    require(dict(Counter(d['judgment'] for d in judgments)) == review['outcomes'], 'Outcome counts differ')
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    require(sum(len(bpe.encode(r['row']['text'])) for r in records) == acquisition['actual_student_bpe_content_tokens'], 'Student token count differs')
    considered = [i for i, d in enumerate(judgments) if d['judgment'] == 'consider']
    require(considered == review['considered_indices'] and sum(len(bpe.encode(chosen[i]['row']['text'])) for i in considered) == review['considered_actual_bpe_tokens'], 'Considered tokens differ')
    require(dict(Counter(r['row']['dump'] for r in records)) == acquisition['crawl_counts'], 'Crawl coverage differs')
    require(len({urlsplit(r['row']['url']).hostname for r in records}) == acquisition['hosts'], 'Host count differs')
    require(sum(r['original_frozen_partition'] is not None for r in records) == acquisition['frozen_heldout_rows_preserved'], 'Heldouts differ')
    require(sum(p['bytes'] for p in acquisition['pages']) == acquisition['raw_response_bytes'] <= plan['total_response_byte_cap'], 'Byte cap differs')
    probe = Path('data/fineweb-parquet-transport-probe-v1')
    metadata, trailer = read(probe / 'metadata-probe.json'), read(probe / 'trailer-probe.json')
    raw, tail = (probe / 'footer-metadata.bin').read_bytes(), (probe / 'footer-trailer.bin').read_bytes()
    require(sha(probe / 'footer-metadata.bin') == metadata['footer_metadata_sha256'] and len(raw) == metadata['actual_metadata_response_bytes'], 'Footer changed')
    require(sha(probe / 'footer-trailer.bin') == trailer['trailer_sha256'] and tail[-4:] == b'PAR1' and int.from_bytes(tail[:4], 'little') == len(raw), 'Trailer differs')
    parsed = pq.read_metadata(pa.BufferReader(b'PAR1' + raw + tail))
    require(parsed.num_rows == metadata['metadata_rows'] and parsed.num_row_groups == metadata['row_groups'], 'Metadata parse differs')
    for name, actual in (('prose-acquisition', acquisition), ('prose-review', review), ('parquet-metadata', metadata)):
        require(read(f'reports/milestone-sixty-seven-{name}.json') == actual, 'Published report differs')
    print(json.dumps(dict(creator='Navneet Prabhakar', kind='actual-prose-audit-check-v1', passed=True,
                         checker_sha256=sha(__file__), rows=64, judgments=16, footer_rows=parsed.num_rows,
                         training_approved=False, scope='Recomputed actual audit bindings/counts and local footer parse; not an independent subjective judgment, live HTTP revalidation, corpus admission or row-group reader test.'), indent=2))


if __name__ == '__main__':
    main()
