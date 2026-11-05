"""Gold-history training-fit diagnostic, explicitly not a conversation benchmark."""
import argparse
import fcntl
import hashlib
import json
import time
from pathlib import Path

import mlx.core as mx
from tokenizers import Tokenizer
from benchmark_mlx import Model
from inference_guard import violation
from train_local import health
from sft_common import ROOT, configure_memory, encode_episode, generate, masked_loss, memory_stats


def main(args):
    goal = ROOT / 'runs/eight-hour-improvement-v1'
    deadline = json.loads((goal / 'authorization.json').read_text())['deadline_unix']
    source, cp, output = Path(args.input), Path(args.checkpoint), Path(args.output)
    if not (cp / 'model.safetensors').exists():
        cp = cp / json.loads((cp / 'latest.json').read_text())['directory']
    if output.exists():
        raise RuntimeError('Preserve existing diagnostic; use a new output path')
    inputs = json.loads(source.read_text())
    base = {**health(), **memory_stats()}

    def guard():
        if time.time() >= deadline or (goal / 'STOP').exists():
            raise RuntimeError('Goal deadline or STOP reached')
        reason = violation({**health(), **memory_stats()}, base)
        if reason:
            raise RuntimeError(reason)

    with (goal / '.training.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        guard()
        configure_memory()
        tok = Tokenizer.from_file(str(ROOT / 'data/sft-v3/tokenizer.json'))
        model = Model(768, 12, 16384)
        model.load_weights(str(cp / 'model.safetensors'))
        model.set_dtype(mx.bfloat16)
        mx.eval(model.parameters())
        results = []
        for row in inputs['records']:
            guard()
            ids, mask, n = encode_episode(tok, row['messages'])
            loss = masked_loss(model, mx.array(ids[None, :n]), mx.array(mask[None, :n-1]))
            mx.eval(loss)
            history, replies = [], []
            for message in row['messages']:
                if message['role'] == 'assistant':
                    guard()
                    generated = generate(model, tok, history, penalty=1.2, seed=20261102, cap=96)
                    replies.append({'gold_target': message['content'], 'student': generated,
                                    'exact_match': generated['output'] == message['content']})
                history.append(message)
            results.append({'id': row['id'], 'group': row['training_group'],
                            'assistant_nll': float(loss), 'replies': replies})
        output.write_text(json.dumps({'kind': 'training_fit_diagnostic_NOT_heldout_or_free_conversation',
                                     'history': 'Gold training messages before each assistant position; prevents error propagation solely for diagnosis.',
                                     'checkpoint': str(cp),
                                     'checkpoint_sha256': hashlib.sha256((cp/'model.safetensors').read_bytes()).hexdigest(),
                                     'input_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                                     'results': results}, indent=2) + '\n')
        print(json.dumps({'records': len(results), 'output': str(output)}))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    p.add_argument('--checkpoint', required=True)
    p.add_argument('--output', required=True)
    main(p.parse_args())
