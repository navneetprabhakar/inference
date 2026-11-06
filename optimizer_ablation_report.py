"""Describe a completed optimizer screen; never certify assistant quality."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re
import statistics

BRANCHES = ('preserve-095', 'reset-095', 'reset-scaled')
TARGET = 19_996_672
POINTS = (10_002_432, 15_007_744, TARGET)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def repetitive(text):
    words = re.findall(r'\w+|[^\w\s]', text.casefold())
    return any(n >= 3 for n in Counter(tuple(words[i:i+4]) for i in range(len(words)-3)).values())


def pairs(row):
    return sum(bool(p['correct']) for p in row['diagnostics']['pairs'])


def loop_count(row):
    return sum(repetitive(p['generated']) for p in row['diagnostics']['completions'])


def difference(candidate, control):
    a, b = candidate['document_losses'], control['document_losses']
    if len(a) != len(b) or len(a) < 2:
        raise ValueError('mismatched validation windows')
    delta = [x-y for x, y in zip(a, b)]
    if not all(math.isfinite(x) for x in delta):
        raise ValueError('nonfinite validation difference')
    return dict(change_nats=statistics.mean(delta),
                descriptive_paired_se=statistics.stdev(delta)/math.sqrt(len(delta)))


def analyze(histories):
    if set(histories) != set(BRANCHES):
        raise ValueError('all three branches required')
    tables = {}
    for name, history in histories.items():
        table = {r['trained_tokens']: r for r in history}
        if len(table) != len(history) or not {0, *POINTS} <= table.keys():
            raise ValueError('missing or duplicate comparison checkpoints')
        for row in history:
            loss = row['document_losses']
            if not loss or not all(math.isfinite(x) for x in loss):
                raise ValueError('invalid validation losses')
            if abs(statistics.mean(loss)-row['mean_ce']) > 1e-8:
                raise ValueError('stored mean differs from document losses')
        tables[name] = table
    control = tables['preserve-095']
    for name in BRANCHES[1:]:
        a, b = tables[name][0]['document_losses'], control[0]['document_losses']
        if len(a) != len(b) or max(abs(x-y) for x, y in zip(a, b)) > 1e-5:
            raise ValueError('branches do not share the same baseline evaluation')
    comparisons, qualified = {}, []
    for name in BRANCHES[1:]:
        rows, passes = [], True
        for tokens in POINTS:
            candidate, reference = tables[name][tokens], control[tokens]
            change = difference(candidate, reference)
            gain = -change['change_nats']
            qualifies = (gain >= .02 and gain > 2*change['descriptive_paired_se']
                         and pairs(candidate) >= pairs(reference))
            rows.append(dict(trained_tokens=tokens, **change, candidate_pairs=pairs(candidate),
                             control_pairs=pairs(reference), passes_screen=qualifies))
            passes = passes and qualifies
        loops, control_loops = loop_count(tables[name][TARGET]), loop_count(control[TARGET])
        passes = passes and loops <= control_loops
        comparisons[name] = dict(checkpoints=rows, endpoint_repetition_flags=loops,
                                 control_endpoint_repetition_flags=control_loops, qualifies=passes)
        if passes:
            qualified.append(name)
    selected = min(qualified, key=lambda name: tables[name][TARGET]['mean_ce']) if qualified else 'preserve-095'
    beta_comparison = [dict(trained_tokens=t, **difference(tables['reset-scaled'][t], tables['reset-095'][t])) for t in POINTS]
    return dict(state='screen-completed', usable_assistant=False, selected_optimizer_recipe=selected,
                selection_scope='Conditional optimizer screen with a common learning-rate restart; not a language or assistant release.',
                no_candidate_qualified=not qualified, comparisons=comparisons,
                scaled_vs_reset095_descriptive=beta_comparison,
                caveats=['Document errors may correlate by domain; paired SE is descriptive, not an independent-domain confidence interval.',
                         'Single training seed, fixed data order and short horizon; not evidence of a global optimum.',
                         'Repeated four-gram flags are a deterministic heuristic, not a fluency or relevance judgment.',
                         'Conversation and actual tool-result grounding remain unevaluated in this screen.'],
                curves={name: [dict(trained_tokens=r['trained_tokens'], mean_ce=r['mean_ce'],
                                   strict_pairs=pairs(r), repetition_flags=loop_count(r)) for r in histories[name]] for name in BRANCHES})


def read_run(run):
    import torch
    from optimizer_ablation_train import verify_parent, validate_spec
    from gpt2 import Config
    run = Path(run).resolve()
    ledger = json.loads((run/'campaign.json').read_bytes())
    signature = ledger.pop('sha256')
    if hashlib.sha256(canonical(ledger)).hexdigest() != signature:
        raise ValueError('campaign checksum mismatch')
    frozen = json.loads((run/'campaign-spec.json').read_bytes())
    if frozen != ledger['spec']:
        raise ValueError('immutable campaign differs from ledger')
    spec = frozen['identity']['protocol']
    validate_spec(spec, Config(), 'mps')
    parent = verify_parent(spec)
    del parent
    if (ledger['state'] != 'completed' or ledger['trained_tokens'] != TARGET
            or ledger['reserved_tokens'] != TARGET or spec['target_tokens'] != TARGET):
        raise ValueError('incomplete or unequal training exposure')
    entry = ledger['checkpoints'][0]
    if not re.fullmatch(r'step-\d+-[0-9a-f]{64}\.pt', entry['file']):
        raise ValueError('invalid checkpoint name')
    file = run/entry['file']
    if (entry != json.loads((run/'latest.json').read_bytes())[0]
            or entry['file'] not in json.loads((run/'protected.json').read_bytes())
            or file.is_symlink() or file.stat().st_size != entry['bytes'] or digest(file) != entry['sha256']):
        raise ValueError('endpoint artifact is not verified and protected')
    payload = torch.load(file, map_location='cpu', weights_only=True, mmap=True)
    if (payload['identity'] != frozen['identity'] or payload['campaign_id'] != ledger['campaign_id']
            or payload['spec_sha256'] != hashlib.sha256(canonical(frozen)).hexdigest()
            or payload['trained_tokens'] != TARGET):
        raise ValueError('endpoint belongs to a different campaign')
    history = payload['history']
    if history != json.loads((run/'validation.json').read_bytes()):
        raise ValueError('external validation history differs from verified endpoint')
    del payload
    if [r['trained_tokens'] for r in history] != [0, 1_007_616, 5_005_312, *POINTS]:
        raise ValueError('incomplete fixed evaluation schedule')
    for row in history:
        if len(row['document_losses']) != 256 or len(row['diagnostics']['pairs']) != 32 or len(row['diagnostics']['completions']) != 32:
            raise ValueError('unexpected fixed evaluation inventory')
    return spec, history, dict(run=str(run), checkpoint=entry, ledger_sha256=digest(run/'campaign.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs=3, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    histories, receipts, common = {}, {}, None
    common_keys = ('parent', 'source_offset', 'target_tokens', 'length', 'microbatch', 'targets_per_update',
                   'seed', 'bf16', 'corpus', 'manifest_sha256', 'validation_blocks_sha256',
                   'diagnostics_sha256', 'scheduler', 'protocol_sha256', 'code_sha256')
    for run in args.runs:
        spec, history, receipt = read_run(run)
        identity = {k: spec[k] for k in common_keys}
        if common is not None and identity != common:
            raise ValueError('branches differ outside the intended optimizer intervention')
        common = identity
        name = spec['branch']
        if name in histories:
            raise ValueError('duplicate branch')
        histories[name], receipts[name] = history, receipt
    result = analyze(histories)
    result.update(receipts=receipts, common=common, report_code_sha256=digest(__file__))
    from base_supervise import write
    write(args.output.resolve(), result)
    print(json.dumps({k: result[k] for k in ('state', 'selected_optimizer_recipe', 'usable_assistant')}))


if __name__ == '__main__':
    main()
