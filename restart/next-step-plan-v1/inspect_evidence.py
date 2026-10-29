"""CPU-only plan evidence; reads train payloads and saved states, never runs a model."""
import hashlib
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

import torch
from sentencepiece import SentencePieceProcessor

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def main():
    helper = PROJECT / 'restart/sol-conversation-sft-diagnostic-v1/runner.py'
    spec = importlib.util.spec_from_file_location('plan_serializer', helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sp = SentencePieceProcessor(model_file=str(module.TOK))
    train_path = PROJECT / 'restart/sol-conversation-data-1000-v1/private/train-candidates.jsonl'
    rows = [json.loads(line) for line in train_path.read_text().splitlines() if line.strip()]
    families = Counter()
    lengths, answer_lengths = [], []
    fit_targets = 0
    gold_headroom_failures = worst_headroom_failures = too_long_answers = 0
    decode_caps = {cap: Counter() for cap in [32, 48, 80]}
    bridge_families = {'grounded_extraction', 'reading_comprehension', 'clarification', 'correction', 'instructions', 'simple_explanation'}
    bridge_eligible = Counter()
    for row in rows:
        assert row['split'] == 'train'
        ids, mask, spans = module.serialize(sp, row['messages'])
        lengths.append(len(ids))
        if len(ids) > 257:
            continue
        families[row['family']] += 1
        fit_targets += int(mask.sum())
        gold_failed = worst_failed = long_answer = False
        worst_prefix = 1
        for turn, span in enumerate(spans):
            prefix = module.prompt(sp, row['messages'][:2 * turn + 1])
            assert prefix == ids[:span['start']].tolist()
            n = len(sp.encode(row['messages'][2 * turn + 1]['content']))
            answer_lengths.append(n)
            long_answer |= n + 1 > 32  # Reserve one decode step for EOS.
            gold_failed |= len(prefix) + 32 > 256
            worst_prefix += len(sp.encode('User: ' + row['messages'][2 * turn]['content'] + '\nAssistant:'))
            worst_failed |= worst_prefix + 32 > 256
            # Conservative bound if previous turns consume all 32 generated
            # content tokens and the existing history builder appends EOS.
            worst_prefix += 33
        too_long_answers += long_answer
        gold_headroom_failures += gold_failed
        worst_headroom_failures += worst_failed

        for cap, counts in decode_caps.items():
            prefix_bound = 1
            flags = dict(reference_too_long=False, gold_history_over_context=False, worst_history_over_context=False)
            for turn, span in enumerate(spans):
                answer_size = len(sp.encode(row['messages'][2 * turn + 1]['content']))
                flags['reference_too_long'] |= answer_size + 1 > cap
                flags['gold_history_over_context'] |= span['start'] + cap > 256
                prefix_bound += len(sp.encode('User: ' + row['messages'][2 * turn]['content'] + '\nAssistant:'))
                flags['worst_history_over_context'] |= prefix_bound + cap > 256
                prefix_bound += cap + 1
            counts.update({key: int(value) for key, value in flags.items()})
            if cap == 48 and len(spans) == 2 and row['family'] in bridge_families and not any(flags.values()):
                bridge_eligible[row['family']] += 1

    checkpoints = {}
    definitions = {
        'foundation': ('restart/foundation-resolution-v1/B/checkpoint.pt', 'bf45241501cee600bd618677dc1a3ae666e6f50d9c628e29e7326ee9c87d338d'),
        'short_answer': ('restart/factual-binding-v1/binding/epoch-400.pt', '62b83c558ac5d9b844494f7080c4a99e2a852c8a7dcbb90fcfec2eea997b2a3c'),
        'broader': ('restart/broader-curriculum-v1/broad/epoch-100.pt', '78c5213150ef5599dd0734db924b077c09c756ab43a6084b21f7ec8ada4d0cb3'),
    }
    for label, (relative, expected) in definitions.items():
        path = PROJECT / relative
        digest = sha(path)
        assert digest == expected
        # Local, hash-verified project checkpoints. CPU deserialization only.
        state = torch.load(path, map_location='cpu', weights_only=False)
        states = list(state['optimizer']['state'].values())
        steps = sorted({int(item['step']) for item in states})
        checkpoints[label] = dict(
            path=relative, sha256=digest, optimizer_step=state['optimizer_step'],
            optimizer_tensor_steps=steps, state_entries=len(states),
            all_moments_finite=all(bool(torch.isfinite(item[k]).all()) for item in states for k in ['exp_avg', 'exp_avg_sq']),
            nonzero_first_moment_entries=sum(bool(torch.count_nonzero(item['exp_avg'])) for item in states),
            nonzero_second_moment_entries=sum(bool(torch.count_nonzero(item['exp_avg_sq'])) for item in states),
            rng_state_present='mlx_rng_state' in state,
            stored_group_learning_rates=[g['lr'] for g in state['optimizer']['param_groups']],
        )
        assert steps == [state['optimizer_step']]
        del state, states

    norm = lambda text: re.findall(r'\w+', text.casefold())
    result = dict(
        status='CPU_ONLY_PLANNING_INSPECTION', model_forwards=0, optimizer_updates=0,
        teacher_calls=0, heldout_payloads_read=False, training_data_admitted=0,
        checkpoints=checkpoints,
        teacher_train=dict(
            path=str(train_path.relative_to(PROJECT)), sha256=sha(train_path),
            candidates=len(rows), fit_records=sum(x <= 257 for x in lengths),
            fit_assistant_eos_targets=fit_targets, fit_families=dict(sorted(families.items())),
            fit_records_reference_answer_plus_eos_exceeds_32=too_long_answers,
            fit_records_gold_history_plus_32_exceeds_256=gold_headroom_failures,
            fit_records_worst_generated_history_plus_32_exceeds_256=worst_headroom_failures,
            max_fit_answer_content_tokens=max(answer_lengths),
            decoder_cap_checks={str(cap): dict(counts) for cap, counts in decode_caps.items()},
            bridge_two_turn_cap48_structural_eligibility=dict(sorted(bridge_eligible.items())),
            meaning='Headroom counts are checks against candidate decoder caps, not quality exclusions or observed student failures. Worst-case count assumes capped previous replies plus appended EOS.'),
        scorer_counterexample=dict(reference='09:10', malformed='09 10', legacy_normalization_accepts=norm('09:10') == norm('09 10')),
        source_hashes={str(p.relative_to(PROJECT)): sha(p) for p in [Path(__file__), helper, PROJECT/'restart/foundation-stage3-v1/engine.py', PROJECT/'restart/foundation-stage3-v1/engine_support.py', module.TOK]},
    )
    output = HERE / 'evidence.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    torch.set_num_threads(2)
    main()
