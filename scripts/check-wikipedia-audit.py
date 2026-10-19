#!/usr/bin/env python3
"""Reopen the bounded actual Wikipedia source audit; never admit training data."""
# Creator: Navneet Prabhakar
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path

from slm.common.tokenizer import BPE
from slm.data.build import read_source
from slm.data.schema import digest
from slm.data.staging import canonical, metadata
from slm.data.tokenized import sha

ROOT = Path('data/wikipedia-distributed-audit-v1')


def lines(path): return [json.loads(line) for line in path.read_text().splitlines()]


def require(condition, reason):
    if not condition: raise ValueError(reason)


def main():
    plan, acquired, review = (metadata(ROOT / name) for name in ('plan.json', 'acquisition.json', 'review-report.json'))
    require(sha(ROOT / 'plan.json') == acquired['plan_sha256'], 'Acquisition plan differs')
    require(sha('scripts/acquire-wikipedia-audit.py') == plan['script_sha256'], 'Acquisition implementation differs')
    source = read_source(ROOT / 'source/source.json')
    require(json.loads(canonical(asdict(source))) == plan['source'], 'Pinned source differs')
    require(source.revision == acquired['source_revision'] and source.review_status == 'sample_only', 'Source revision/status differs')
    info = metadata(ROOT / 'dataset-info.json')
    require(info['sha'] == source.revision and info['cardData']['license'] == ['cc-by-sa-3.0', 'gfdl'], 'Declared metadata differs')
    sizes = metadata(ROOT / 'size-response.json')
    selected = [s for s in sizes['size']['splits'] if s['config'] == plan['config'] and s['split'] == 'train']
    require(sizes['partial'] is False and len(selected) == 1, 'Complete size metadata required')
    n = selected[0]['num_rows']
    require(n == acquired['upstream_rows'] and plan['offsets'] == [n * k // 8 for k in (1, 3, 5, 7)], 'Offsets differ')
    frozen_path = Path('data/fineweb-prose-candidate-staging-v1/staged/heldout-groups.json')
    require(sha(frozen_path) == plan['frozen_heldouts_sha256'], 'Ancestral heldouts changed')
    frozen = metadata(frozen_path)
    reconstructed = []
    require(len(acquired['pages']) == 4, 'Four exact pages required')
    for cluster, page in enumerate(acquired['pages']):
        path = ROOT / f'page-{cluster:02d}.json'; body = metadata(path)
        require(page['cluster'] == cluster and page['offset'] == plan['offsets'][cluster] and sha(path) == page['sha256']
                and path.stat().st_size == page['bytes'] <= plan['per_response_byte_cap']
                and page['revision'] == source.revision and not body.get('partial') and len(body['rows']) == 16,
                'Complete pinned page binding differs')
        for i, entry in enumerate(body['rows']):
            row = entry['row']; group = source.source_id + ':en:' + row['id']
            require(entry['row_idx'] == page['offset'] + i and not entry.get('truncated_cells')
                    and set(row) == {'id', 'url', 'title', 'text'} and all(isinstance(v, str) for v in row.values())
                    and row['text'].strip() and row['url'].startswith('https://en.wikipedia.org/wiki/'), 'Article shape/order/completeness differs')
            reconstructed.append(dict(cluster=cluster, global_row_index=entry['row_idx'], source_group=group,
                raw_record_sha256=digest(row), config=plan['config'], original_frozen_partition=frozen.get(group), row=row))
    require(reconstructed == lines(ROOT / 'rows.jsonl') and len({r['source_group'] for r in reconstructed}) == 64, 'Actual raw records differ')
    require(sha(ROOT / 'rows.jsonl') == acquired['row_file_sha256'], 'Raw file hash differs')
    require(sum(p['bytes'] for p in acquired['pages']) == acquired['successful_page_body_bytes'] <= plan['total_page_body_byte_cap'], 'Page body budget differs')
    chosen = []; eligible_counts = {}
    for cluster in range(4):
        eligible = [r for r in reconstructed if r['cluster'] == cluster and r['original_frozen_partition'] is None
                    and plan['review_min_characters'] <= len(r['row']['text']) <= plan['review_max_characters']]
        eligible_counts[str(cluster)] = len(eligible)
        chosen.extend(sorted(eligible, key=lambda r: (digest([plan['selection_seed'], r['source_group']]), r['source_group']))[:4])
    require(eligible_counts == acquired['review_eligible_by_cluster'] and
            [dict(index=i, **r) for i, r in enumerate(chosen)] == lines(ROOT / 'review.jsonl'), 'Length-conditioned review selection differs')
    require(sha(ROOT / 'review.jsonl') == acquired['review_file_sha256'] == review['review_file_sha256'], 'Review file differs')
    journal = lines(ROOT / 'direct-judgments.jsonl')
    require(len(journal) == len(chosen) == review['full_documents_read'] == 16 and sha(ROOT / 'direct-judgments.jsonl') == review['journal_sha256'], 'Direct journal differs')
    for i, (row, decision) in enumerate(zip(chosen, journal)):
        require(decision['index'] == i and decision['source_group'] == row['source_group'] and decision['raw_record_sha256'] == row['raw_record_sha256']
                and decision['review_file_sha256'] == sha(ROOT / 'review.jsonl') and decision['full_text_read'] is True
                and decision['review_mode'] == 'delegated_expert' and decision['judgment'] in ('consider', 'exclude', 'defer')
                and len(decision['reason'].strip()) > 40, 'Review meaning/binding differs')
        require(all(decision[k] is False for k in ('human_attestation', 'training_approved', 'factual_accuracy_verified', 'underlying_document_rights_verified')), 'Unsupported verification flag')
    require(dict(Counter(d['judgment'] for d in journal)) == review['outcomes'], 'Review counts differ')
    require(sum(len(r['row']['text']) for r in chosen) == acquired['review_characters'] == review['characters_read'], 'Complete character count differs')
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    require(sum(len(bpe.encode(r['row']['text'])) for r in reconstructed) == acquired['actual_student_bpe_content_tokens'], 'Student BPE count differs')
    licensing = metadata(ROOT / 'source/licensing-review.json')
    require(sha(ROOT / 'source/licensing-review.json') == acquired['source_licensing_review_sha256'] == review['licensing_review_sha256']
            and licensing['status'] == 'unresolved_before_training_admission' and licensing['training_approved'] is False, 'Licensing status/binding differs')
    for extra in licensing['supplemental_license_texts']:
        require(sha(ROOT / 'source' / extra['file']) == extra['sha256'], 'Supplemental license text differs')
    if licensing['current_guide_access']['status'] == 'downloaded':
        require(sha(ROOT / 'source/current-dump-licensing.html') == licensing['current_guide_access']['sha256'], 'Current primary guide differs')
    require(metadata(Path('reports/milestone-seventy-two-wikipedia-acquisition.json')) == acquired and
            metadata(Path('reports/milestone-seventy-two-wikipedia-review.json')) == review, 'Published reports differ')
    result = dict(creator='Navneet Prabhakar', kind='actual-wikipedia-source-audit-check-v1', passed=True,
        checker_sha256=sha(__file__), rows=64, complete_reviews=16, review_outcomes=review['outcomes'],
        article_characters_read=review['characters_read'], successful_page_body_bytes=acquired['successful_page_body_bytes'],
        training_approved=False, source_status='sample_only',
        scope='Actual page/source/selection/journal/BPE/license evidence bindings recomputed. Not independent subjective/factual/legal certification, a representative quality comparison or corpus admission.')
    Path('reports/milestone-seventy-two-audit-check.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
