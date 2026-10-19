#!/usr/bin/env python3
"""Actual canonical/source/heldout audit plus full portable-token reconstruction."""
# Creator: Navneet Prabhakar
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path

from slm.data.prose_research import open_research, require
from slm.data.prose_research_tokens import verify_tokens
from slm.data.review_stream import open_checked
from slm.data.schema import digest
from slm.data.staging import metadata
from slm.data.tokenized import sha

ROOT = Path('data/prose-research-preparation-v1')


def lines(path): return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    release, tokens = ROOT / 'release', ROOT / 'tokens'
    policy_file = Path('configs/prose-foundation-research-admission-v1.json'); policy_hash = sha(policy_file)
    result, protocol = metadata(ROOT / 'result.json'), metadata(ROOT / 'protocol.json')
    require(result['protocol_sha256'] == sha(ROOT / 'protocol.json') and result['policy_sha256'] == policy_hash, 'Actual protocol/policy differs')
    for label, filename in (('reader', 'prose_research.py'), ('builder', 'prose_research_tokens.py')):
        require(sha(Path('src/slm/data') / filename) == protocol[label + '_sha256'] == sha(ROOT / ('executed-' + filename)), 'Executed source snapshot differs')
    require(sha('scripts/prepare-prose-research.py') == protocol['script_sha256'], 'Actual preparation wrapper differs')
    staged = Path('data/fineweb-prose-candidate-staging-v1/staged')
    originals = {row['example_id']: row for split in ('train', 'validation', 'test')
                 for path in staged.glob(split + '-*.jsonl') for row in lines(path)}
    known = [*lines(Path('data/prose-train-review-v1/direct-judgments.jsonl')),
             *lines(Path('data/fineweb-prose-distributed-audit-v1/direct-judgments.jsonl'))]
    blocked = {d['source_group'] for d in known if d['judgment'] != 'consider'}
    counts = Counter(); read = 0
    for split in ('train', 'validation', 'test'):
        for row in lines(release / (split + '-000000.jsonl')):
            before = originals[row['example_id']]; actual = deepcopy(row)
            receipt = actual['validation_results'].pop('prose_research_admission')
            require(actual == before and digest(before) == receipt['original_record_sha256'], 'Original canonical record changed')
            require(row['parent_group_id'] not in blocked, 'Observed nonapproval entered release')
            counts[split] += 1
            if split == 'train': read += receipt['individually_read']
    original_heldouts = metadata('data/smol-content-review-v2/staged/heldout-groups.json')
    heldouts = metadata(release / 'ancestor-heldouts.json')
    require(all(heldouts.get(key) == split for key, split in original_heldouts.items()), 'Ancestral global partition changed')
    require(sha(release / 'manifest.json') == result['release_manifest_sha256'] and sha(tokens / 'manifest.json') == result['token_manifest_sha256'], 'Actual release/token identity differs')
    try:
        with open_checked(release): pass
    except ValueError:
        legacy_refused = True
    else: raise ValueError('Legacy reader must still refuse schema6')
    with open_research(release, policy_hash) as checked:
        require(len(checked) == counts['train'], 'Actual train-only reader count differs')
    reconstructed = verify_tokens(tokens, release, 'data/iteration-two-foundation-tokenizers-v1/vocab-16384', policy_hash)
    require(reconstructed == result['actual_reconstruction'], 'Actual reconstruction receipt differs')
    report = dict(creator='Navneet Prabhakar', kind='actual-prose-preparation-check-v1', passed=True,
        checker_sha256=sha(__file__), release_manifest_sha256=sha(release / 'manifest.json'),
        token_manifest_sha256=sha(tokens / 'manifest.json'), exact_original_rows=dict(counts),
        directly_read_train=read, unread_train=counts['train'] - read,
        protected_ancestral_families=len(original_heldouts), observed_nonapproval_groups_absent=len(blocked),
        legacy_reader_refused=legacy_refused, reconstruction=reconstructed, model_updates=0,
        training_recipe_ready=False,
        scope='All864 canonical originals exact except explicit admission receipt; full token/mask/metadata/span reconstruction. Prior global grouping is trusted through its pinned checked origin, not independently rerun. No model or broad corpus acceptance.')
    Path('reports/milestone-seventy-one-actual-check.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__': main()
