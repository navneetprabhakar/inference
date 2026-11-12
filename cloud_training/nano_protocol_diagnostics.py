"""Read-only token-level SFT diagnostics on an immutable own-model bundle.

Purposive short train/dev samples test protocol learning, not overall quality.
No optimizer, checkpoint writes, or answer repair occurs. An optional exposed
conversation suite uses the actual offline fixture broker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def source_group(row):
    names = sorted({message['tool_call']['name'] for message in row['messages'] if 'tool_call' in message})
    return row.get('diagnostic_source', 'unspecified')+('/'+','.join(names) if names else '/text')


def length_spread(rows, samples):
    ordered = sorted(rows, key=lambda row:row['sequence_tokens'])
    count = min(samples, len(ordered))
    return [ordered[index*(len(ordered)-1)//max(1,count-1)] for index in range(count)]


def run(args):
    from cloud_training.nano_serve import load_own_bundle, generate_action
    from cloud_training.nano_chat_format import encode_conversation, parse_generated
    from cloud_training.nano_sft import load_manifest
    import torch

    checkpoint = Path(args.checkpoint).resolve()
    output = Path(args.output).resolve()
    if output == checkpoint or checkpoint in output.parents or output.exists():
        raise ValueError('Output must be a new file outside the immutable checkpoint')
    manifest = load_manifest(args.manifest, args.tokenizer_sha)
    model, tok, _ = load_own_bundle(args.repo, checkpoint, args.tokenizer,
        tokenizer_sha256=args.tokenizer_sha, device=args.device)
    model.requires_grad_(False)
    torch.set_num_threads(4)
    import nanochat.flash_attention as attention
    from nanochat.common import COMPUTE_DTYPE
    attention.USE_FA3 = False
    if args.kernel_path:
        from kernels import get_local_kernel
        attention._fa3 = get_local_kernel(Path(args.kernel_path), 'flash_attn3').flash_attn_interface
        attention.HAS_FA3 = True

    report = {
        'status': 'running', 'device': args.device,
        'weight_dtype': str(next(model.parameters()).dtype), 'compute_dtype': str(COMPUTE_DTYPE),
        'diagnostic_module_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'checkpoint_manifest_sha256': hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest(),
        'dataset_manifest_sha256': manifest['_sha256'],
        'selection': 'Length-spread complete conversations per source/tool-name group; purposive, not representative',
        'usable_model_claim': False, 'records': [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)

    def publish():
        temporary = output.with_suffix('.tmp')
        temporary.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
        temporary.replace(output)

    publish()
    for split in ('train', 'validation'):
        rows = [json.loads(line) for line in Path(manifest[split]['_file']).open()]
        groups = sorted({source_group(row) for row in rows})
        for source in groups:
            candidates = [row for row in rows if source_group(row) == source
                          and row.get('sequence_tokens', args.max_positions+1) <= args.max_positions]
            for index, row in enumerate(length_spread(candidates, args.samples)):
                rendered = encode_conversation(tok, row['messages'], policies=row.get('policies'))
                ids = rendered['ids']
                x = torch.tensor([ids[:-1]], device=args.device)
                with torch.inference_mode():
                    logits = model(x)[0].cpu()
                record = {'split': split, 'source': source, 'id': row['id'], 'tokens': len(ids), 'spans': []}
                if args.kernel_path and split == 'train' and source.startswith('tools/') and index == 0:
                    try:
                        attention.USE_FA3 = True
                        with torch.inference_mode():
                            other = model(x)[0].cpu()
                    finally:
                        attention.USE_FA3 = False
                    record['attention_parity'] = {
                        'max_abs_logit_difference': float((other-logits).abs().max()),
                        'top1_agreement': float((other.argmax(-1)==logits.argmax(-1)).float().mean()),
                    }
                for span in rendered['spans']:
                    if not span['supervised']:
                        continue
                    start, end = span['start'], span['end']
                    values = logits[start-1:end-1]
                    labels = torch.tensor(ids[start:end])
                    reference = values.gather(1, labels[:, None])
                    ranks = 1+(values > reference).sum(1)
                    log_prob = values.log_softmax(-1).gather(1, labels[:, None]).squeeze(1)
                    record['spans'].append({
                        'kind': span['kind'], 'tokens': end-start,
                        'ce': float(-log_prob.mean()), 'top1': float((ranks==1).float().mean()),
                        'first_reference_rank': int(ranks[0]),
                        'first_reference_probability': float(log_prob[0].exp()),
                    })
                if source.startswith('tools/') and index == 0:
                    start = next(span['start'] for span in rendered['spans'] if span['supervised'])
                    prediction = generate_action(model, tok, ids[:start], 64)
                    record['first_action_text'] = tok.decode(prediction)
                    record['parsed'] = parse_generated(tok, prediction, reply_budget=64)
                report['records'].append(record)
                publish()
                print(split, source, index, [(s['kind'], round(s['ce'], 3), s['first_reference_rank'])
                                             for s in record['spans']], flush=True)
    report['status'] = 'protocol_complete'
    if args.suite:
        import time
        from cloud_training.nano_quality import run_suite
        from cloud_training.nano_serve import BrokerChat
        suite = json.loads(Path(args.suite).read_text())
        report['conversation_assessments'] = {}
        for budget in (128, 512):
            factory = lambda: BrokerChat(tok, lambda ids, n: generate_action(model, tok, ids, n),
                                         reply_budget=budget, context=model.config.sequence_len)
            report['conversation_assessments'][str(budget)] = run_suite(
                factory, suite, deadline=time.monotonic()+300)
            publish()
    report['status'] = 'complete'
    publish()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'checkpoint', 'tokenizer', 'tokenizer-sha', 'manifest', 'output'):
        parser.add_argument('--'+name, required=True)
    parser.add_argument('--device', choices=('cpu', 'mps', 'cuda'), default='cuda')
    parser.add_argument('--kernel-path')
    parser.add_argument('--suite', help='Optional exposed suite; assess raw generation at128 and512 tokens')
    parser.add_argument('--max-positions', type=int, default=700)
    parser.add_argument('--samples', type=int, default=4)
    args = parser.parse_args()
    if not 1 <= args.samples <= 16 or not 2 <= args.max_positions <= 2048:
        parser.error('Bounded samples1..16 and positions2..2048 required')
    run(args)


if __name__ == '__main__':
    main()
