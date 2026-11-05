"""Replay teacher fixtures and check encoding limits; never certify semantic quality."""
import argparse
import hashlib
import json
from pathlib import Path
from tokenizers import Tokenizer
from sft_common import ROOT, encode_episode, execute, parse_call


def audit(paths):
    tok = Tokenizer.from_file(str(ROOT / 'data/sft-v3/tokenizer.json'))
    problems, hashes = [], {}
    count = fixtures = 0
    for path in paths:
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            count += 1
            messages = row['messages']
            pending = None
            for index, message in enumerate(messages):
                role, content = message['role'], message['content']
                prefix = {'id': row['id'], 'message_index': index}
                if pending is not None and role != 'tool':
                    problems.append({**prefix, 'error': 'call_not_followed_by_tool_result'})
                    pending = None
                if role == 'assistant' and content.strip().startswith('<|tool_call|>'):
                    try:
                        pending = execute(parse_call(content))
                    except Exception as exc:
                        problems.append({**prefix, 'error': 'invalid_call', 'detail': str(exc)})
                elif role == 'tool':
                    fixtures += 1
                    try:
                        result = json.loads(content)
                    except json.JSONDecodeError:
                        result = None
                    if pending is None or result != pending:
                        problems.append({**prefix, 'error': 'fixture_result_mismatch', 'actual': result, 'expected': pending})
                    pending = None
            if pending is not None:
                problems.append({'id': row['id'], 'error': 'unresolved_tool_call'})
            if encode_episode(tok, messages) is None:
                problems.append({'id': row['id'], 'error': 'episode_exceeds_training_context_or_no_supervision'})
    return {'records': count, 'fixture_results_checked': fixtures, 'errors': problems,
            'source_hashes': hashes, 'semantic_review_certified': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('data', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(sorted(args.data.glob('batch-*.jsonl')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'source_hashes'}, indent=2))
    raise SystemExit(bool(result['errors']))
