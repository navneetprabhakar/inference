#!/usr/bin/env python3
"""Publish/prepare the exact finite prose ingredient; no gradient or launch."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path

from slm.data.prose_research import release
from slm.data.prose_research_tokens import build_tokens, verify_tokens
from slm.data.prose_screen import RequestGuard
from slm.data.staging import canonical, metadata
from slm.data.tokenized import sha
from slm.eval.cases import candidate_suite
from slm.eval.tool_cases import tool_cases

ROOT = Path('data/prose-research-preparation-v1')
STAGED = Path('data/fineweb-prose-candidate-staging-v1/staged')
REVIEW = Path('data/prose-train-review-v1')
PRIOR = Path('data/fineweb-prose-distributed-audit-v1')
SCREEN = Path('data/fineweb-prose-screen-v1')
POLICY = Path('configs/prose-foundation-research-admission-v1.json')
TOKENIZER = Path('data/iteration-two-foundation-tokenizers-v1/vocab-16384')


def publish(path, value):
    with path.open('x') as out: out.write(canonical(value) + '\n')


def main():
    if ROOT.exists(): raise FileExistsError(ROOT)
    policy_hash = sha(POLICY)
    requests = [m['content'] for c in candidate_suite()['cases'] for m in c['messages'] if m['role'] == 'user']
    requests.extend(m['content'] for c in tool_cases() for m in c['history'] if m['role'] == 'user')
    for path in metadata(SCREEN / 'plan.json')['input_bindings']:
        if path.endswith('/turns.jsonl'):
            requests.extend(json.loads(line)['user'] for line in Path(path).read_text().splitlines())
    guard = RequestGuard(requests)
    if guard.fingerprint != metadata(SCREEN / 'plan.json')['protected_request_fingerprint']:
        raise ValueError('Exact originally screened protected requests required')
    ROOT.mkdir(); inputs = ROOT / 'inputs'; inputs.mkdir()
    publish(inputs / 'protected-requests.json', list(guard.requests))
    source = metadata('data/audit-v1/fineweb-edu/source/source.json')
    source['evidence_files'] = dict(card='source-card.txt', license='source-license.txt')
    publish(inputs / 'source.json', source)
    evidence = dict(zip(('membership.json', 'direct-judgments.jsonl', 'review-report.json', 'review-packet.jsonl', 'reference-receipt.json'),
                        (REVIEW / 'retained-membership.json', REVIEW / 'direct-judgments.jsonl', REVIEW / 'review-report.json', REVIEW / 'review.jsonl', REVIEW / 'references/receipt.json')))
    evidence.update({'screen-plan.json': SCREEN / 'plan.json', 'screen-report.json': SCREEN / 'report.json',
        'raw-prefix.jsonl': Path('data/fineweb-parquet-rowgroup-audit-v1/rows.jsonl'),
        'raw-distributed.jsonl': PRIOR / 'rows.jsonl', 'prior-judgments.jsonl': PRIOR / 'direct-judgments.jsonl',
        'prior-review-packet.jsonl': PRIOR / 'review.jsonl', 'staged-manifest.json': STAGED / 'manifest.json',
        'ancestor-heldouts.json': STAGED / 'heldout-groups.json', 'protected-requests.json': inputs / 'protected-requests.json',
        'source.json': inputs / 'source.json', 'source-card.txt': Path('data/audit-v1/fineweb-edu/source/card.txt'),
        'source-license.txt': Path('data/audit-v1/fineweb-edu/source/license.txt'),
        'commoncrawl-terms.html': Path('data/main-learning-budget-research-v1/commoncrawl-terms.html')})
    protocol = dict(creator='Navneet Prabhakar', kind='finite-prose-release-and-preparation-v1',
        policy_sha256=policy_hash, tokenizer_manifest_sha256=sha(TOKENIZER / 'manifest.json'),
        reader_sha256=sha('src/slm/data/prose_research.py'), builder_sha256=sha('src/slm/data/prose_research_tokens.py'),
        script_sha256=sha(__file__), evidence={name: dict(path=str(path.resolve()), sha256=sha(path)) for name, path in evidence.items()},
        context_length=1024, shard_positions=262144, max_positions=2000000, model_updates=0)
    publish(ROOT / 'protocol.json', protocol)
    for name in ('prose_research.py', 'prose_research_tokens.py'):
        (ROOT / ('executed-' + name)).write_bytes((Path('src/slm/data') / name).read_bytes())
    published = release(STAGED, POLICY, evidence, ROOT / 'release')
    prepared = build_tokens(ROOT / 'release', TOKENIZER, ROOT / 'tokens', policy_hash,
        context_length=1024, shard_positions=262144, max_positions=2000000)
    checked = verify_tokens(ROOT / 'tokens', ROOT / 'release', TOKENIZER, policy_hash)
    result = dict(creator='Navneet Prabhakar', protocol_sha256=sha(ROOT / 'protocol.json'),
        policy_sha256=policy_hash, release_manifest_sha256=sha(ROOT / 'release/manifest.json'),
        token_manifest_sha256=sha(ROOT / 'tokens/manifest.json'), publication=published, preparation=prepared,
        actual_reconstruction=checked, model_updates=0, training_recipe_ready=False,
        scope='Actual exact local prose research ingredient prepared; no main-learning launch, gradient, teacher, cloud or paid activity.')
    publish(ROOT / 'result.json', result)
    publish(Path('reports/milestone-seventy-one-prose-preparation.json'), result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
