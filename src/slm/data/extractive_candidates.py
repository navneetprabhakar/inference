"""Measure an extractive SFT candidate slice; never admit or rewrite examples."""
# Creator: Navneet Prabhakar
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata
from slm.common.tokenizer import BPE
from slm.data.schema import digest
from slm.data.quality_audit import signals
from slm.data.review_stream import open_checked
from slm.data.tokenized import sha
from slm.data.dialogue_screen import SCOPE, IDENTITY, PLACEHOLDER


SOURCE = 'databricks/databricks-dolly-15k'
TEMPORAL = re.compile(r'(?i)\b(?:current|currently|latest|today|now|recent|this year|best|should i|advice|recommend|how old)\b')
SEED = 'extractive-sft-candidate-review-20261019-v1'
RULE = dict(version=1, source=SOURCE, categories=['closed_qa', 'information_extraction'],
    min_context_words=20, max_context_words=600, min_answer_words=3, max_answer_words=80,
    max_prediction_positions=1024, max_answer_fraction=.8, normalization='NFC-and-collapse-whitespace-case-sensitive',
    temporal_question_pattern=TEMPORAL.pattern, scope_pattern=SCOPE.pattern,
    identity_pattern=IDENTITY.pattern, placeholder_pattern=PLACEHOLDER.pattern,
    prior_nonapproval_whole_group_exclusion=True, one_candidate_per_group=True,
    raw_duplicate_handling='collapse-identical-records-and-report-counts',
    training_eligible=False, semantic_relevance_verified=False)


def norm(value):
    return ' '.join(unicodedata.normalize('NFC', value).split())


def raw_inventory(records):
    rows = {}
    total = 0
    for row in records:
        total += 1
        key = digest(row)
        if key in rows and rows[key] != row:
            raise ValueError('Raw identity collision')
        rows[key] = row
    return rows, total


def inspect(record, raw, bpe):
    expected_prompt = raw['instruction'] + ('\n\nContext:\n'+raw['context'] if raw['context'] else '')
    expected = [dict(role='user', content=unicodedata.normalize('NFC', expected_prompt).strip()),
                dict(role='assistant', content=unicodedata.normalize('NFC', raw['response']).strip())]
    if record['messages'] != expected:
        raise ValueError('Canonical text differs from pinned raw row')
    reasons = []
    context, answer = norm(raw['context']), norm(raw['response'])
    if raw['category'] not in RULE['categories']: reasons.append('category')
    if not RULE['min_context_words'] <= len(context.split()) <= RULE['max_context_words']: reasons.append('context_length')
    if not RULE['min_answer_words'] <= len(answer.split()) <= RULE['max_answer_words']: reasons.append('answer_length')
    start = context.find(answer) if answer else -1
    if start < 0: reasons.append('no_exact_answer_span')
    if context and len(answer)/len(context) > RULE['max_answer_fraction']: reasons.append('near_whole_context_copy')
    if TEMPORAL.search(raw['instruction']): reasons.append('time_sensitive_or_advice_question')
    text = '\n'.join(m['content'] for m in record['messages'])
    if SCOPE.search(text) or IDENTITY.search(text) or PLACEHOLDER.search(text): reasons.append('scope_or_identity_attention')
    s = signals(record)
    if s['privacy_findings'] or s['structural_or_cleaner_attention']: reasons.append('privacy_or_structural_attention')
    x, _, mask = bpe.serialize(record['messages'])
    if len(x) > RULE['max_prediction_positions']: reasons.append('context_exceeds_no_truncation_limit')
    return reasons, dict(normalized_context_sha256=digest(context), normalized_answer_sha256=digest(answer),
        normalized_context_character_span=[start, start+len(answer)] if start >= 0 else None,
        prediction_positions=len(x), assistant_targets=sum(mask), raw_category=raw['category'],
        record_sha256=digest(record), raw_record_sha256=digest(raw),
        training_eligible=False, semantic_relevance_verified=False)


def prepare(parent, raw_file, acquisition_file, prior_review, tokenizer, output):
    parent, raw_file, acquisition_file, prior_review, tokenizer, output = map(Path,
        (parent, raw_file, acquisition_file, prior_review, tokenizer, output))
    if output.exists(): raise FileExistsError(output)
    acquisition = json.loads(acquisition_file.read_text())
    if acquisition['source_id'] != SOURCE or sha(raw_file) != acquisition['published_sha256']:
        raise ValueError('Pinned raw Dolly source differs')
    with raw_file.open() as handle:
        raw_rows, raw_count = raw_inventory(map(json.loads, handle))
    review = json.loads(prior_review.read_text())
    if (review['dataset_manifest_sha256'] != sha(parent/'manifest.json')
            or review['review_mode'] != 'delegated_expert' or review['human_attestation'] is not False):
        raise ValueError('Prior explicit judgments must bind this exact parent')
    bpe = BPE.load(tokenizer); excluded = Counter(); buckets = {}; examined = Counter()
    with open_checked(parent) as index:
        blocked = set()
        for key, entry in review['examples'].items():
            original = index.db.execute('SELECT data FROM approved WHERE eid=?', (key,)).fetchone()
            if (original is None or json.loads(original[0]) != entry['record']
                    or digest(entry['record']) != entry['record_sha256']):
                raise ValueError('Prior reviewed text differs from parent')
            if entry['decision']['approved'] is not True:
                blocked.add(entry['record']['validation_results']['split_group'])
        for text, in index.db.execute('SELECT data FROM approved ORDER BY eid'):
            record = json.loads(text)
            if record['source'] != SOURCE: continue
            if record['source_revision'] != acquisition['source_revision']:
                raise ValueError('Raw and canonical revisions differ')
            examined[record['split']] += 1
            raw = raw_rows[record['example_id'].removeprefix(SOURCE+':')]
            reasons, proof = inspect(record, raw, bpe)
            group = record['validation_results']['split_group']
            if group in blocked: reasons.append('prior_nonapproved_group')
            if reasons:
                excluded.update(reasons); continue
            item = dict(record=record, proof=proof)
            if group in buckets and buckets[group]['record']['split'] != record['split']:
                raise ValueError('Candidate split group crosses partitions')
            if group not in buckets or digest([SEED, record['example_id']]) < digest([SEED, buckets[group]['record']['example_id']]):
                buckets[group] = item
    candidates = sorted(buckets.values(), key=lambda x: x['record']['example_id'])
    strata = defaultdict(list)
    for item in candidates:
        if item['record']['split'] == 'train':
            length = item['proof']['prediction_positions']
            strata[next(c for c in (128, 256, 512, 1024) if length <= c)].append(item)
    for key in strata:
        strata[key].sort(key=lambda x: digest([SEED, 'sample', x['record']['example_id']]), reverse=True)
    sample = []
    while len(sample) < 64 and any(strata.values()):
        for key in sorted(strata):
            if strata[key] and len(sample) < 64: sample.append(strata[key].pop())
    counts = Counter(); positions = Counter(); targets = Counter()
    for item in candidates:
        split = item['record']['split']; counts[split] += 1
        positions[split] += item['proof']['prediction_positions']; targets[split] += item['proof']['assistant_targets']
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.extractive-candidates-', dir=output.parent))
    try:
        for name, rows in [('candidates.jsonl', candidates), ('sample.jsonl', sample)]:
            with (temp/name).open('x') as out:
                for i, item in enumerate(rows): out.write(json.dumps(dict(index=i, **item), sort_keys=True, ensure_ascii=False)+'\n')
        report = dict(creator='Navneet Prabhakar', version=1, rule=RULE, rule_sha256=digest(RULE),
            implementation_sha256=sha(__file__), parent_manifest_sha256=sha(parent/'manifest.json'),
            raw_sha256=sha(raw_file), prior_review_sha256=sha(prior_review), tokenizer_manifest_sha256=sha(tokenizer/'manifest.json'),
            raw_records=raw_count, raw_distinct_record_digests=len(raw_rows), raw_exact_duplicate_records=raw_count-len(raw_rows),
            examined_by_split=dict(examined), overlapping_exclusion_counts=dict(excluded),
            retained_distinct_groups=len(candidates), candidate_rows_by_split=dict(counts),
            candidate_prediction_positions_by_split=dict(positions), candidate_assistant_targets_by_split=dict(targets),
            train_only_review_sample_rows=len(sample), sample_seed=SEED,
            candidates_sha256=sha(temp/'candidates.jsonl'), sample_sha256=sha(temp/'sample.jsonl'),
            training_eligible=False, new_model_updates=0,
            scope='Candidate measurement only. Exact normalized spans do not prove question relevance or real-world truth. Original text/groups/splits unchanged, one candidate per group, prior nonapprovals excluded. Existing foundation exposure is not new unique content. No source/corpus SFT admission, teacher/cloud action or model score.')
        (temp/'report.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
        manifest = dict(version=1, kind='non-admitting-extractive-sft-candidates-v1', release='sample_only',
                        files={p.name: sha(p) for p in temp.iterdir()})
        (temp/'manifest.json').write_text(json.dumps(manifest, indent=2, sort_keys=True)+'\n')
        temp.rename(output)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True); raise
    return report


def main():
    p = argparse.ArgumentParser()
    for name in ('parent', 'raw', 'acquisition', 'prior-review', 'tokenizer', 'output'):
        p.add_argument('--'+name, required=True)
    a = p.parse_args()
    print(json.dumps(prepare(a.parent, a.raw, a.acquisition, a.prior_review, a.tokenizer, a.output), indent=2))


if __name__ == '__main__':
    main()
