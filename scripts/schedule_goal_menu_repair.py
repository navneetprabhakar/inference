"""Encode and audit a future curriculum without launching training."""
import argparse
import hashlib
import json
import random
from collections import defaultdict

import numpy as np
from tokenizers import Tokenizer
from sft_common import ROOT, encode_episode
from goal_training_records import encode_training_row


def main(args):
    source = ROOT / args.source
    out = ROOT / args.output
    for admission in [source / 'ADMISSION.json', source / 'admission.json']:
        if admission.exists() and json.loads(admission.read_text()).get('training_allowed') is False:
            raise ValueError('Source is explicitly quarantined: '+str(admission))
    out.mkdir(exist_ok=False)
    rows = [json.loads(s) for s in (source/'records.jsonl').read_text().splitlines()]
    manifest = json.loads((source/'manifest.json').read_text())
    for name, digest in manifest['files'].items():
        assert hashlib.sha256((source/name).read_bytes()).hexdigest() == digest
    shares = json.loads(args.mix)
    assert all(v > 0 for v in shares.values()) and abs(sum(shares.values()) - 1) < 1e-9
    tok = Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'))
    ids, masks, lengths, counts = [], [], [], []
    groups = defaultdict(list)
    for i, row in enumerate(rows):
        if args.prompt_format == 'plain_roles_v1':
            if row.get('objective') == 'causal_lm':
                raise ValueError('Plain-role experiment does not allow causal replay')
            from goal_plain_roles import encode_episode as encode_plain
            encoded = encode_plain(tok, row['messages'])
        else:
            encoded = encode_training_row(tok, row, allow_replay=args.allow_causal_replay)
        if encoded is None:
            raise ValueError('Record does not fit context: '+row['id'])
        token, mask, n = encoded
        ids.append(token); masks.append(mask); lengths.append(n); counts.append(int(mask.sum()))
        groups[row['training_group']].append(i)
    assert set(groups) == set(shares)
    rng = random.Random(args.seed)
    bags, emitted, order, inputs = {}, {g: 0 for g in groups}, [], 0
    while inputs < args.tokens:
        group = min(groups, key=lambda g: emitted[g] / shares[g])
        if not bags.get(group):
            bags[group] = groups[group].copy()
            rng.shuffle(bags[group])
        i = bags[group].pop()
        order.append(i); inputs += lengths[i] - 1; emitted[group] += counts[i]
    batches = []
    for start in range(0, len(order), 64):
        block = sorted(order[start:start+64], key=lambda i: lengths[i])
        batches.extend(block[j:j+args.batch_size] for j in range(0, len(block), args.batch_size) if len(block[j:j+args.batch_size]) == args.batch_size)
    coefficients, actual, pending = defaultdict(float), defaultdict(int), defaultdict(int)
    input_count = updates = pending_count = 0
    for batch in batches:
        for i in batch:
            g = rows[i]['training_group']
            pending[g] += counts[i]; actual[g] += counts[i]
            pending_count += counts[i]; input_count += lengths[i] - 1
        if pending_count >= 512 or input_count >= args.stage_tokens:
            for g, n in pending.items():
                coefficients[g] += n / pending_count
            updates += 1; pending.clear(); pending_count = 0
        if input_count >= args.stage_tokens:
            break
    audit = {'batch_size': args.batch_size, 'supervised_tokens_per_update': 512, 'first_stage_input_tokens': input_count, 'optimizer_updates': updates,
             'supervised_token_shares': {g: actual[g]/sum(actual.values()) for g in groups},
             'average_normalized_update_loss_coefficients': {g: coefficients[g]/updates for g in groups}}
    audit['maximum_share_deviation'] = max(abs(audit['supervised_token_shares'][g] - audit['average_normalized_update_loss_coefficients'][g]) for g in groups)
    assert audit['maximum_share_deviation'] < .03
    (out/'records.jsonl').write_bytes((source/'records.jsonl').read_bytes())
    np.savez_compressed(out/'episodes.npz', ids=np.stack(ids), mask=np.stack(masks), length=np.array(lengths, np.int32))
    (out/'order.json').write_text(json.dumps({'order': order, 'seed': args.seed}) + '\n')
    (out/'optimization-mix-audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    result = {'state': 'prepared_not_launched', 'records': len(rows),
              'source': str(source.relative_to(ROOT)), 'seed': args.seed,
              'desired_supervised_token_mix': shares, 'scheduled_input_tokens': inputs,
              'source_manifest_sha256': hashlib.sha256((source/'manifest.json').read_bytes()).hexdigest(),
              'causal_replay_opt_in': args.allow_causal_replay,
              'prompt_format': args.prompt_format,
              'group_records': {g: len(v) for g, v in groups.items()},
              'files': {name: hashlib.sha256((out/name).read_bytes()).hexdigest()
                        for name in ['records.jsonl', 'episodes.npz', 'order.json']}}
    (out/'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'records': len(rows), 'audit': audit}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', default='data/eight-hour-menu-repair-v1')
    p.add_argument('--output', default='data/eight-hour-menu-repair-scheduled-v2')
    p.add_argument('--mix', default='{"reviewed_natural":0.6,"fresh_authored":0.1,"grounded_qa":0.1,"positive_tools":0.15,"tool_boundaries":0.05}')
    p.add_argument('--seed', type=int, default=2026110342)
    p.add_argument('--tokens', type=int, default=4_000_000)
    p.add_argument('--batch-size', type=int, choices=[2,4,8], default=2)
    p.add_argument('--stage-tokens', type=int, default=1_000_000)
    p.add_argument('--allow-causal-replay', action='store_true')
    p.add_argument('--prompt-format', choices=['special_roles_v1','plain_roles_v1'], default='special_roles_v1')
    args = p.parse_args()
    assert 0 < args.stage_tokens <= args.tokens
    main(args)
