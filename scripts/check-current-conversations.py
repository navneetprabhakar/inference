"""Reconstruct all recorded prompts and token outputs without regenerating replies."""
# Creator: Navneet Prabhakar
from collections import Counter
import json
from pathlib import Path
from slm.common.tokenizer import BPE, OFFSET, STRUCTURAL
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.inference.greedy import prompt_ids

ROOT = Path('data/current-model-100-conversations-v1')


def check():
    plan = json.loads((ROOT / 'plan.json').read_text())
    session = json.loads((ROOT / 'session.json').read_text())
    done = json.loads((ROOT / 'completion.json').read_text())
    rows = [json.loads(s) for s in (ROOT / 'turns.jsonl').read_text().splitlines()]
    binding = plan['terminal']
    assert sha(ROOT / 'plan.json') == session['plan_sha256'] == sha('configs/current-model-100-conversations-v1.json')
    assert done['session_sha256'] == sha(ROOT / 'session.json')
    assert done['turns_sha256'] == sha(ROOT / 'turns.jsonl')
    assert session['runner_sha256'] == sha('scripts/run-current-conversations.py')
    assert done['complete'] is True and done['conversations'] == 100 and done['turns'] == len(rows) == 300
    assert session['terminal'] == binding
    assert session['student']['model_manifest_sha256'] == binding['model_manifest_sha256'] == sha(Path(binding['model_path']) / 'manifest.json')
    bpe = BPE.load(binding['tokenizer_path'])
    assert sha(Path(binding['tokenizer_path']) / 'manifest.json') == binding['tokenizer_manifest_sha256']
    assert len(plan['conversations']) == len({c['id'] for c in plan['conversations']}) == 100
    assert len({c['turns'][0]['user'] for c in plan['conversations']}) == 100
    for index, case in enumerate(plan['conversations']):
        history = []
        for turn, request in enumerate(case['turns'], 1):
            row = rows[index * 3 + turn - 1]
            assert (row['conversation'], row['category'], row['turn'], row['user']) == (case['id'], case['category'], turn, request['user'])
            history.append(dict(role='user', content=row['user']))
            r = row['response']; ids = r['token_ids']
            assert row['context_sha256'] == digest(history)
            assert r['prompt_tokens'] == len(prompt_ids(bpe, history))
            assert r['prompt_tokens'] + plan['max_new_tokens'] <= session['student']['architecture']['max_seq_len']
            assert 0 < len(ids) == r['generated_tokens'] <= r['max_new_tokens'] == plan['max_new_tokens']
            assert all(type(t) is int and 0 <= t < bpe.vocab_size for t in ids)
            if r['stop_reason'] in ('message_end', 'eos'):
                assert ids[-1] == STRUCTURAL[r['stop_reason']]
                content = ids[:-1]
                assert all(t >= OFFSET for t in content)
            elif r['stop_reason'] == 'length':
                assert len(ids) == plan['max_new_tokens'] and all(t >= OFFSET for t in ids)
                content = ids
            else:
                assert r['stop_reason'] == 'invalid_structural'
                assert ids[-1] < OFFSET and ids[-1] not in (STRUCTURAL['message_end'], STRUCTURAL['eos'])
                content = ids[:-1]
                assert all(t >= OFFSET for t in content)
            assert r['content_tokens'] == len(content) and bpe.decode(content) == r['text']
            history.append(dict(role='assistant', content=r['text']))
    displayed = Path('docs/current-model-100-transcripts.md').read_text()
    replies = [block.split('\n```', 1)[0] for block in displayed.split('```text\n')[1:]]
    assert replies == [row['response']['text'] for row in rows]
    return dict(creator='Navneet Prabhakar', complete=True, conversations=100, turns=300,
        categories=dict(Counter(r['category'] for r in rows)),
        stop_reasons=dict(Counter(r['response']['stop_reason'] for r in rows)),
        distinct_replies=len({r['response']['text'] for r in rows}),
        generated_tokens=sum(r['response']['generated_tokens'] for r in rows),
        generation_seconds=sum(r['response']['seconds'] for r in rows),
        transcript_sha256=sha(ROOT / 'turns.jsonl'), plan_sha256=sha(ROOT / 'plan.json'),
        session_sha256=sha(ROOT / 'session.json'), completion_sha256=sha(ROOT / 'completion.json'),
        readable_transcript_sha256=sha('docs/current-model-100-transcripts.md'),
        checker_sha256=sha(__file__), scope='Recorded structure, tokenizer decoding and exact raw-history reconstruction; task quality requires direct review.')


if __name__ == '__main__':
    result = check()
    target = Path('reports/current-model-100-conversations-integrity.json')
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, indent=2))
