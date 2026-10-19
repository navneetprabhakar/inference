#!/usr/bin/env python3
"""Check actual raw/prompt/review/seed-span evidence without model execution."""
# Creator: Navneet Prabhakar
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
from slm.common.tokenizer import BPE
from slm.data.build import read_source
from slm.data.cosmopedia_seed import extract
from slm.data.schema import digest
from slm.data.staging import canonical, metadata
from slm.data.tokenized import sha

ROOT = Path('data/cosmopedia-distributed-audit-v1')


def lines(path): return [json.loads(line) for line in path.read_text().splitlines()]


def require(value, reason):
    if not value: raise ValueError(reason)


def check_journal(sample, journal, expected):
    require(len(sample) == len(journal), 'Full review journal required')
    for i, (row, decision) in enumerate(zip(sample, journal)):
        require(decision['index'] == i and decision['source_group'] == row['source_group']
                and decision['raw_record_sha256'] == row['raw_record_sha256'] and decision['review_file_sha256'] == expected
                and decision['full_generated_text_read'] is True and decision['full_prompt_read'] is True
                and decision['judgment'] in ('consider', 'exclude', 'defer') and len(decision['reason'].strip()) > 40,
                'Review meaning or identity differs')
        require(all(decision[k] is False for k in ('human_attestation', 'training_approved', 'factual_accuracy_verified',
                    'underlying_document_rights_verified', 'assistant_demonstration_approved')), 'Unsupported verification flag')


def main():
    plan, acquired, review = (metadata(ROOT / n) for n in ('plan.json', 'acquisition.json', 'review-report.json'))
    source = read_source(ROOT / 'source/source.json')
    require(json.loads(canonical(asdict(source))) == plan['source'] and source.review_status == 'sample_only', 'Source/card/license differs')
    require(sha(ROOT / 'plan.json') == acquired['plan_sha256'] and sha('scripts/acquire-cosmopedia-audit.py') == plan['script_sha256'], 'Executed plan/source differs')
    require(metadata(ROOT / 'dataset-info.json')['sha'] == source.revision == acquired['source_revision'], 'Source revision differs')
    sizes = metadata(ROOT / 'size-response.json')
    selected_size = [s for s in sizes['size']['splits'] if s['config'] == plan['config'] and s['split'] == 'train']
    require(sizes['partial'] is False and len(selected_size) == 1 and selected_size[0]['num_rows'] == acquired['upstream_rows']
            and plan['offsets'] == [acquired['upstream_rows'] * k // 8 for k in (1, 3, 5, 7)], 'Size/offset metadata differs')
    generator = metadata(ROOT / 'source/generator-receipt.json')
    require(sha(ROOT / 'source/generator-receipt.json') == plan['generator_receipt_sha256'], 'Generator receipt differs')
    for name, field in (('generator-card.txt', 'card_sha256'), ('generator-info.json', 'model_info_sha256'), ('generator-license.txt', 'license_sha256')):
        require(sha(ROOT / 'source' / name) == generator[field], 'Generator evidence differs')
    require(metadata(ROOT / 'source/generator-info.json')['sha'] == generator['model_revision'] and generator['declared_model_license'] == 'apache-2.0', 'Generator identity/license differs')
    frozen = metadata('data/fineweb-prose-candidate-staging-v1/staged/heldout-groups.json')
    require(sha('data/fineweb-prose-candidate-staging-v1/staged/heldout-groups.json') == plan['frozen_heldouts_sha256'], 'Ancestral map differs')
    rebuilt = []
    require(len(acquired['pages']) == 4, 'Four complete pages required')
    for cluster, page in enumerate(acquired['pages']):
        path = ROOT / f'page-{cluster:02d}.json'; body = metadata(path)
        require(sha(path) == page['sha256'] and path.stat().st_size == page['bytes'] <= plan['per_page_body_byte_cap']
                and page['offset'] == plan['offsets'][cluster] and page['revision'] == source.revision
                and len(body['rows']) == 16 and not body.get('partial'), 'Exact page binding differs')
        for i, entry in enumerate(body['rows']):
            row = entry['row']; group = source.source_id + ':cosmopedia-v2:prompt:' + digest(row['prompt'])
            require(entry['row_idx'] == page['offset'] + i and not entry.get('truncated_cells'), 'Truncated/reordered record')
            require(set(row) == {'prompt', 'text', 'token_length', 'audience', 'format', 'seed_data'}
                    and type(row['token_length']) is int and row['token_length'] > 0
                    and all(isinstance(row[k], str) and row[k].strip() for k in ('prompt', 'text', 'audience', 'format', 'seed_data')), 'Raw record schema differs')
            rebuilt.append(dict(cluster=cluster, global_row_index=entry['row_idx'], source_group=group,
                raw_record_sha256=digest(row), original_frozen_partition=frozen.get(group), row=row))
    require(rebuilt == lines(ROOT / 'rows.jsonl') and sha(ROOT / 'rows.jsonl') == acquired['raw_file_sha256'], 'Actual raw file differs')
    require(len({r['raw_record_sha256'] for r in rebuilt}) == acquired['actual_rows'] == 64
            and sum(p['bytes'] for p in acquired['pages']) == acquired['successful_page_body_bytes'] <= plan['total_page_body_byte_cap'], 'Record/body count differs')
    chosen = []; families = set()
    for cluster in range(4):
        eligible = [r for r in rebuilt if r['cluster'] == cluster and r['original_frozen_partition'] is None and 500 <= len(r['row']['text']) <= 16000]
        count = 0
        for row in sorted(eligible, key=lambda r: (digest([plan['seed'], r['raw_record_sha256']]), r['raw_record_sha256'])):
            if row['source_group'] in families: continue
            families.add(row['source_group']); chosen.append(row); count += 1
            if count == 4: break
    require([dict(index=i, **r) for i, r in enumerate(chosen)] == lines(ROOT / 'review.jsonl'), 'Original selection differs')
    require(sha(ROOT / 'review.jsonl') == acquired['review_file_sha256'] == review['review_file_sha256']
            and sha(ROOT / 'direct-judgments.jsonl') == review['journal_sha256'], 'Review bytes differ')
    journal = lines(ROOT / 'direct-judgments.jsonl'); check_journal(chosen, journal, sha(ROOT / 'review.jsonl'))
    require(dict(Counter(d['judgment'] for d in journal)) == review['outcomes'], 'Original outcomes differ')
    require(sum(len(r['row']['text']) for r in chosen) == acquired['review_characters'] == review['generated_characters_read']
            and sum(len(r['row']['prompt']) for r in chosen) == review['prompt_characters_read'], 'Full original reading counts differ')
    require(sha(ROOT / 'sintering-reference.json') == review['specific_reference_sha256'] == journal[9]['specific_reference_receipt_sha256'], 'Specific primary evidence differs')
    supplemental = metadata(ROOT / 'narrative-supplement-plan.json'); sub_report = review['supplement']
    require(sha(ROOT / 'narrative-supplement-plan.json') == sub_report['plan_sha256']
            and sha(ROOT / 'narrative-supplement.jsonl') == sub_report['sample_sha256']
            and sha(ROOT / 'narrative-supplement-judgments.jsonl') == sub_report['journal_sha256'], 'Supplement evidence differs')
    eligible = [r for r in rebuilt if r['row']['format'] == 'story' and r['source_group'] not in families and 500 <= len(r['row']['text']) <= 16000]
    selected = sorted(eligible, key=lambda r: digest([supplemental['seed'], r['raw_record_sha256']]))[:2]
    require([dict(index=i, **r) for i, r in enumerate(selected)] == lines(ROOT / 'narrative-supplement.jsonl'), 'Posthoc selection differs')
    sub_journal = lines(ROOT / 'narrative-supplement-judgments.jsonl'); check_journal(selected, sub_journal, sub_report['sample_sha256'])
    require(dict(Counter(d['judgment'] for d in sub_journal)) == sub_report['outcomes'], 'Supplement outcomes differ')
    spans = lines(ROOT / 'seed-span-analysis.jsonl'); span_report = metadata(ROOT / 'seed-analysis-report.json')
    require(sha('src/slm/data/cosmopedia_seed.py') == span_report['source_sha256'] and sha(ROOT / 'seed-span-analysis.jsonl') == span_report['analysis_file_sha256'], 'Seed implementation/evidence differs')
    fineweb = [r for r in rebuilt if r['row']['seed_data'] == 'fineweb']
    require(len(spans) == len(fineweb) == 50, 'Complete known-profile coverage required')
    for row, actual in zip(fineweb, spans):
        expected = dict(raw_record_sha256=row['raw_record_sha256'], original_prompt_family=row['source_group'], parsed=True, **extract(row['row']))
        require(actual == expected and row['row']['prompt'][actual['seed_start']:actual['seed_end']] == actual['seed_excerpt'], 'Exact source span differs')
    bpe = BPE.load('data/iteration-two-foundation-tokenizers-v1/vocab-16384')
    require(sum(len(bpe.encode(r['row']['text'])) for r in rebuilt) == acquired['actual_student_bpe_text_tokens'], 'Actual BPE count differs')
    for name, field in (('audiences', 'audience'), ('formats', 'format'), ('seed_labels', 'seed_data')):
        require(dict(Counter(r['row'][field] for r in rebuilt)) == acquired[name], 'Raw metadata counts differ')
    require(sum(r['row']['token_length'] for r in rebuilt) == acquired['upstream_mistral_token_lengths'], 'Upstream token metadata differs')
    require(metadata(Path('reports/milestone-seventy-three-cosmopedia-review.json')) == review
            and metadata(Path('reports/milestone-seventy-three-cosmopedia-acquisition.json')) == acquired
            and metadata(Path('reports/milestone-seventy-three-seed-analysis.json')) == span_report, 'Published reports differ')
    result = dict(creator='Navneet Prabhakar', kind='actual-cosmopedia-source-audit-check-v1', passed=True,
        checker_sha256=sha(__file__), raw_rows=64, original_complete_prompt_text_reviews=16,
        original_outcomes=review['outcomes'], posthoc_complete_story_reviews=2, posthoc_outcomes=sub_report['outcomes'],
        exact_seed_spans_reconstructed=50, training_approved=False,
        scope='Actual source/page/selection/journal/generator/BPE/excerpt evidence checked. No independent subjective/factual/legal certification, latent document/semantic overlap proof or corpus admission.')
    Path('reports/milestone-seventy-three-audit-check.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
