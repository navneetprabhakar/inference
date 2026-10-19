#!/usr/bin/env python3
"""Interactive JSON-line interviewer for the actual first-iteration checkpoint."""
# Creator: Navneet Prabhakar
from pathlib import Path
import json
import sys
from slm.inference.greedy import GreedyModel
from slm.data.tokenized import sha


def main():
    root = Path('data/context-research-run-v1')
    run = json.loads((root/'run.json').read_text())
    report = json.loads((root/'report.json').read_text())
    scored = json.loads(Path('reports/milestone-forty-two-heldout-smoke.json').read_text())
    if report['status'] != 'data_exhausted_before_target' or scored['run_report_sha256'] != sha(root/'report.json'):
        raise ValueError('Completed, scored iteration-one checkpoint required')
    protocol_path = Path('configs/iteration-one-conversation-assessment-v1.json')
    protocol = json.loads(protocol_path.read_text())
    out = Path('data/iteration-one-conversation-assessment-v1')
    if out.exists():
        raise FileExistsError(out)
    model_path = Path(report['latest_checkpoint'])/'state/model'
    if sha(model_path/'manifest.json') != scored['model_manifest_sha256']:
        raise ValueError('Conversation checkpoint differs from the scored model')
    model = GreedyModel(model_path, run['spec']['tokenizer'], 'mlx', 'default',
                        expected_tokenizer_hash=run['logical_plan']['tokenizer_hash'],
                        embedding_implementation=run['logical_plan']['recipe']['embedding_implementation'])
    out.mkdir()
    header = dict(creator='Navneet Prabhakar', protocol_sha256=sha(protocol_path), script_sha256=sha(__file__),
                  student=model.identity, run_report_sha256=sha(root/'report.json'),
                  review_mode='delegated_expert', human_attestation=False, training_approved=False)
    (out/'session.json').write_text(json.dumps(header, indent=2, sort_keys=True)+'\n')
    print(json.dumps(dict(status='ready', transcript=str(out/'turns.jsonl'))), flush=True)
    history = []
    with (out/'turns.jsonl').open('x') as f:
        for number, line in enumerate(sys.stdin, 1):
            if number > protocol['max_turns']:
                raise ValueError('Conversation turn budget exceeded')
            request = json.loads(line)
            if set(request) != {'user'} or not isinstance(request['user'], str) or not request['user'].strip():
                raise ValueError('One nonempty user string required')
            if number == 1 and request['user'] != protocol['initial_prompt']:
                raise ValueError('Initial prompt differs from fixed protocol')
            history.append(dict(role='user', content=request['user']))
            response = model.generate(history, protocol['max_new_tokens'])
            row = dict(turn=number, user=request['user'], response=response)
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False)+'\n'); f.flush()
            history.append(dict(role='assistant', content=response['text']))
            print(json.dumps(row, ensure_ascii=False), flush=True)
            if number == protocol['max_turns']:
                print(json.dumps(dict(status='complete', turns=number)), flush=True)
                break


if __name__ == '__main__':
    main()
