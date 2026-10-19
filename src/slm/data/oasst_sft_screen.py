"""Measure human-rating SFT candidates without granting training admission."""
# Creator: Navneet Prabhakar
from collections import Counter
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import shutil
import tempfile

from slm.common.tokenizer import BPE
from slm.data.curation import normalize
from slm.data.build import read_source
from slm.data.dialogue_candidates import node_reason
from slm.data.review_stream import open_checked
from slm.data.schema import digest
from slm.data.staging import canonical
from slm.data.tokenized import sha, stamp

SOURCE = 'OpenAssistant/oasst2'
RULE = dict(version=1, kind='oasst-rated-sft-candidates-v1', training_eligible=False,
            context_limit=2048, minimum_assistant_targets=16,
            assistant_rank=0, assistant_quality=.75, assistant_helpfulness=.75,
            minimum_rating_count=2, zero_flags=['spam', 'fails_task', 'lang_mismatch', 'pii',
                                             'not_appropriate', 'hate_speech', 'sexual_content'],
            zero_flag_minimum_count=1, one_path_per_split_group=True,
            selection='Most assistant turns, then highest minimum assistant quality, then seeded digest.',
            scope='Publisher annotations are subjective selection proxies, not correctness, rights or SFT approval.')
SEED = 'oasst-rated-sft-candidates-20261019-v1'


def rating(node, name):
    labels = node.get('labels')
    value = labels.get(name) if isinstance(labels, dict) else None
    if not isinstance(value, dict):
        return None
    count, score = value.get('count'), value.get('value')
    if (type(count) is not int or count < 1 or type(score) not in (int, float)
            or not math.isfinite(score) or not 0 <= score <= 1):
        return None
    return count, score


def node_flags(node, assistant):
    reasons = set()
    reason = node_reason(node)
    if reason:
        reasons.add(reason)
    if node.get('role') != ('assistant' if assistant else 'prompter'):
        reasons.add('raw_role')
    for name in RULE['zero_flags']:
        if name == 'fails_task' and not assistant:
            continue
        value = rating(node, name)
        if value is None or value[0] < RULE['zero_flag_minimum_count']:
            reasons.add('missing_flag_rating')
        elif value[1] != 0:
            reasons.add('nonzero_flag_rating')
    if assistant:
        if type(node.get('rank')) is not int or node['rank'] != RULE['assistant_rank']:
            reasons.add('not_top_ranked_assistant')
        for name in ('quality', 'helpfulness'):
            value = rating(node, name)
            if value is None or value[0] < RULE['minimum_rating_count']:
                reasons.add('missing_assistant_rating')
            elif value[1] < RULE['assistant_'+name]:
                reasons.add('low_assistant_rating')
    return reasons


def measure(parent, snapshot, prior_review, tokenizer, output, *, source_record):
    parent, snapshot, prior_review, tokenizer, output = map(Path, (parent, snapshot, prior_review, tokenizer, output))
    if output.exists():
        raise FileExistsError(output)
    source_record = Path(source_record)
    acquisition = json.loads((snapshot/'acquisition.json').read_text())
    raw_path = snapshot/'trees.jsonl'
    if (acquisition['source_id'] != SOURCE or raw_path.stat().st_size > 512*1024**2
            or sha(raw_path) != acquisition['decoded_sha256']):
        raise ValueError('Pinned complete source identity differs')
    prior = json.loads(prior_review.read_text())
    if (prior.get('human_attestation') is not False or prior.get('review_mode') != 'delegated_expert'
            or prior['dataset_manifest_sha256'] != sha(parent/'manifest.json')):
        raise ValueError('Prior explicit review lineage differs')
    blocked = {e['record']['validation_results']['split_group'] for e in prior['examples'].values()
               if e['decision']['approved'] is not True}
    guards = {p: stamp(p) for p in (raw_path, snapshot/'acquisition.json', snapshot/'source.json', source_record, prior_review,
                                    parent/'manifest.json', tokenizer/'manifest.json', Path(__file__))}
    records = []
    with open_checked(parent) as checked:
        sources = json.loads((parent/'sources.json').read_text())
        source = sources[SOURCE]
        if (source['revision'] != acquisition['source_revision'] or source['license_id'] != 'apache-2.0'
                or sha(source_record) != acquisition['source_descriptor_sha256']
                or digest(read_source(source_record).__dict__) != digest(source)
                or digest(read_source(snapshot/'source.json').__dict__) != digest(source)):
            raise ValueError('Source revision/evidence differs')
        for text, in checked.db.execute('SELECT data FROM approved ORDER BY eid'):
            record = json.loads(text)
            if record['source'] == SOURCE:
                records.append(record)
    if len(records) > 30000:
        raise ValueError('Candidate population exceeds bound')
    needed = {key for record in records for key in record['lineage']}
    nodes = {}
    trees = total_nodes = 0
    with raw_path.open('rb') as stream:
        while line := stream.readline(8*1024**2+1):
            if len(line) > 8*1024**2:
                raise ValueError('Tree byte bound exceeded')
            tree = json.loads(line)
            trees += 1
            stack = [tree['prompt']]
            while stack:
                node = stack.pop()
                total_nodes += 1
                if node['message_id'] in needed:
                    if node['message_id'] in nodes:
                        raise ValueError('Duplicate selected raw node')
                    # Retain only fields needed for provenance/rating checks, never user IDs.
                    nodes[node['message_id']] = {k: deepcopy(node.get(k)) for k in
                        ('message_id', 'parent_id', 'text', 'role', 'lang', 'deleted', 'review_result',
                         'synthetic', 'model_name', 'rank', 'labels')}
                stack.extend(node['replies'])
    if (trees != acquisition['trees'] or total_nodes != acquisition['messages'] or set(nodes) != needed):
        raise ValueError('Complete source/node coverage differs')
    bpe = BPE.load(tokenizer)
    candidates = {}
    counts = Counter()
    screened = []
    for record in records:
        reasons = set()
        group = record['validation_results']['split_group']
        if group in blocked:
            reasons.add('prior_nonapproval_group')
        minimum_quality = 1.0
        for i, (key, message) in enumerate(zip(record['lineage'], record['messages'])):
            node = nodes[key]
            if (normalize(node['text']) != message['content']
                    or node['parent_id'] != (record['lineage'][i-1] if i else None)):
                raise ValueError('Canonical raw path differs')
            reasons.update(node_flags(node, assistant=message['role'] == 'assistant'))
            if message['role'] == 'assistant' and rating(node, 'quality') is not None:
                minimum_quality = min(minimum_quality, rating(node, 'quality')[1])
        if len(record['lineage']) != len(record['messages']):
            raise ValueError('Incomplete raw path binding')
        x, _, mask = bpe.serialize(record['messages'])
        if len(x) > RULE['context_limit']:
            reasons.add('over_context_no_truncation')
        if sum(mask) < RULE['minimum_assistant_targets']:
            reasons.add('too_few_assistant_targets')
        counts.update(reasons)
        receipt = dict(example_id=record['example_id'], record_sha256=digest(record), split=record['split'],
                       split_group=group, reasons=sorted(reasons), hypothetical_prediction_positions=len(x),
                       hypothetical_assistant_targets=sum(mask), training_eligible=False)
        screened.append(receipt)
        if reasons:
            continue
        order = (-sum(m['role'] == 'assistant' for m in record['messages']), -minimum_quality,
                 digest([SEED, record['example_id']]))
        existing = candidates.get(group)
        if existing is None or order < existing[0]:
            candidates[group] = order, record, receipt
    selected = sorted(candidates.values(), key=lambda value: digest([SEED, value[1]['example_id']]))
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix='.rated-sft-screen-', dir=output.parent))
    try:
        totals = Counter()
        turns = Counter()
        with (temp/'candidates.jsonl').open('w') as out:
            for _, record, receipt in selected:
                out.write(canonical(record)+'\n')
                split = record['split']
                totals[split+'_rows'] += 1
                totals[split+'_positions'] += receipt['hypothetical_prediction_positions']
                totals[split+'_assistant_targets'] += receipt['hypothetical_assistant_targets']
                turns[split+'|'+str(len(record['messages'])//2)] += 1
        with (temp/'screening.jsonl').open('w') as out:
            for record in screened:
                out.write(canonical(record)+'\n')
        sample = [record for _, record, _ in selected if record['split'] == 'train'][:64]
        with (temp/'sample.jsonl').open('w') as out:
            for i, record in enumerate(sample):
                out.write(canonical(dict(index=i, record=record, record_sha256=digest(record),
                                         full_text_read=False, judgment=None, training_approved=False))+'\n')
        if any(stamp(p) != before for p, before in guards.items()):
            raise ValueError('Frozen input changed')
        result = dict(creator='Navneet Prabhakar', kind=RULE['kind'], rule=RULE,
            parent_manifest_sha256=sha(parent/'manifest.json'), raw_sha256=sha(raw_path),
            acquisition_sha256=sha(snapshot/'acquisition.json'), prior_review_sha256=sha(prior_review),
            source_descriptor_sha256=sha(source_record), snapshot_source_descriptor_sha256=sha(snapshot/'source.json'),
            tokenizer_manifest_sha256=sha(tokenizer/'manifest.json'), implementation_sha256=sha(__file__),
            examined_paths=len(records), unique_raw_nodes=len(nodes), blocked_prior_groups=len(blocked),
            overlapping_reason_counts=dict(counts), candidate_counts=dict(totals), turns=dict(turns),
            pending_train_review_rows=len(sample), full_text_reviews=0, training_eligible=False,
            seed=SEED, limitations='Subset of the existing bounded foundation research pool; this does not approve conversation SFT or transfer foundation approval. Ratings are subjective proxies, not semantic correctness. Rejections apply to paths except known prior group nonapprovals; selected output has one intact path per existing group. No truncation, new source download, teacher generation or model updates.')
        (temp/'report.json').write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
        manifest = dict(version=1, release='sample_only', files={p.name: sha(p) for p in sorted(temp.iterdir())})
        (temp/'manifest.json').write_text(canonical(manifest)+'\n')
        os.rename(temp, output)
        return result
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'snapshot', 'prior-review', 'tokenizer', 'output', 'source-record'):
        parser.add_argument('--'+name, required=True)
    args = parser.parse_args()
    print(json.dumps(measure(args.parent, args.snapshot, args.prior_review, args.tokenizer, args.output,
                             source_record=args.source_record), indent=2))


if __name__ == '__main__':
    main()
