"""Plain terminal interface to the unchanged own-model serving and offline broker."""
import argparse
import hashlib
import json
import math
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, help='Explicit immutable bundle; otherwise use the reviewed local selection')
    parser.add_argument('--selection', type=Path, default=root/'reports/ownbase-budget50-v1/local-selection.json')
    parser.add_argument('--device', choices=['auto', 'mps', 'cpu', 'cuda'], default='auto')
    parser.add_argument('--no-tools', action='store_true')
    parser.add_argument('--raw', action='store_true', help='Include complete broker/model evidence as JSON')
    parser.add_argument('--reply-budget', type=int, default=256)
    parser.add_argument('--repetition-penalty', type=float, default=1.3)
    args = parser.parse_args()
    if not 1 <= args.reply_budget <= 512:
        parser.error('Reply budget must be 1..512 tokens')
    if not math.isfinite(args.repetition_penalty) or args.repetition_penalty < 1:
        parser.error('Repetition penalty must be finite and at least 1')
    tokenizer_sha = 'ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'
    if args.checkpoint is None:
        if not args.selection.is_file():
            parser.error('Local checkpoint selection is pending. Use --checkpoint to explicitly run an existing bundle.')
        selected = json.loads(args.selection.read_text())
        if selected.get('status') != 'selected_and_locally_verified':
            parser.error('The default checkpoint has not completed local verification')
        checkpoint = root/selected['checkpoint']
        actual = hashlib.sha256((checkpoint/'manifest.json').read_bytes()).hexdigest()
        if actual != selected['manifest_sha256']:
            parser.error('Selected checkpoint manifest changed')
    else:
        checkpoint = args.checkpoint.expanduser().resolve()
    import torch
    from cloud_training.nano_serve import BrokerChat, generate_action, load_own_bundle
    torch.set_num_threads(4)
    device = args.device
    if device == 'auto':
        device = 'mps' if torch.backends.mps.is_available() else 'cuda' if torch.cuda.is_available() else 'cpu'
    model, tokenizer, metadata = load_own_bundle(
        root/'runs/nanochat-source', checkpoint, root/'runs/ownbase-v2-data/tokenizer',
        tokenizer_sha256=tokenizer_sha, device=device)
    chat = BrokerChat(tokenizer,
        lambda ids, n: generate_action(model, tokenizer, ids, n, repetition_penalty=args.repetition_penalty),
        context=model.config.sequence_len, reply_budget=args.reply_budget)
    enabled = not args.no_tools
    print(f'Experimental own model · {device.upper()} · {model.config.sequence_len}-token context')
    print(f'Checkpoint: {checkpoint.name}. /reset starts fresh; /tools on|off; /quit exits.')
    print('Offline calculate and convert tools are '+('enabled.' if enabled else 'disabled.'))
    while True:
        try:
            text = input('you> ')
        except (EOFError, KeyboardInterrupt):
            print(); break
        if text == '/quit':
            break
        if text == '/reset':
            chat.reset(); print('Session reset.'); continue
        if text in ('/tools on', '/tools off'):
            enabled = text.endswith('on'); print('Tools '+('enabled.' if enabled else 'disabled.')); continue
        if not text.strip():
            continue
        try:
            result = chat.turn(text, policy={'permit_calls':enabled, 'allowed_names':['calculate','convert'] if enabled else []})
        except KeyboardInterrupt:
            chat.reset(); print('\nInterrupted; session reset.'); continue
        if args.raw:
            print(json.dumps(result, ensure_ascii=False))
            continue
        for event in result['events']:
            if event['kind'] == 'broker_decision':
                record = event['record']
                if event['decision']['dispatched']:
                    value = record['data']['result'] if record['ok'] else record['error']
                    print(f"[{record['name']}] {json.dumps(record.get('arguments', {}), ensure_ascii=False)} → {value}")
        if result['status'] == 'complete':
            print('model> '+result['assistant_text'])
        else:
            print(f"Model response incomplete: {result['error_code']}.")
            if result.get('reset_required'):
                print('Use /reset before another request.')


if __name__ == '__main__':
    main()
