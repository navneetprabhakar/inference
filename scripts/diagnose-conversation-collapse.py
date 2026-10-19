"""Bounded read-only checkpoint comparison and training-response attribution."""
# Creator: Navneet Prabhakar
import gc
import json
import os
import fcntl
import re
from difflib import SequenceMatcher
from contextlib import ExitStack
from pathlib import Path
from slm.data.schema import digest
from slm.data.tokenized import sha
from slm.inference.greedy import GreedyModel

PLAN = Path('configs/conversation-collapse-diagnostic-v1.json')
OUT = Path('data/conversation-collapse-diagnostic-v1')


def read(p):
    return json.loads(Path(p).read_text())


def save(p, v):
    p.write_text(json.dumps(v, indent=2, sort_keys=True) + '\n')


def main():
    plan = read(PLAN)
    if OUT.exists():
        raise FileExistsError('Preserve attempt; no automatic replay')
    for file, expected in plan['inputs_sha256'].items():
        if sha(file) != expected:
            raise ValueError('Frozen input changed: ' + file)
    with ExitStack() as stack:
        for name in plan['execution_locks']:
            lock = stack.enter_context(Path(name).open('a'))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        OUT.mkdir()
        save(OUT / 'plan.json', plan)
        source = read(plan['control_protocol'])
        single = [r for r in source['train'] if len(r['messages']) == 2]
        assert len(single) == 10
        answers = [(r['example_id'], m['content']) for r in source['train']
                   for m in r['messages'] if m['role'] == 'assistant']
        transcript = [json.loads(s) for s in Path(plan['transcript']).read_text().splitlines()]
        attribution = []
        for row in transcript:
            words = re.findall(r'\w+', row['response']['text'].casefold())
            matches = []
            for identity, answer in answers:
                target = re.findall(r'\w+', answer.casefold())
                match = SequenceMatcher(None, words, target, autojunk=False).find_longest_match()
                if match.size >= 12:
                    matches.append(dict(example_id=identity, contiguous_words=match.size,
                        response_word_start=match.a, source_word_start=match.b))
            attribution.append(dict(conversation=row['conversation'], turn=row['turn'],
                response_sha256=digest(row['response']['text']), matches=matches))
        save(OUT / 'response-attribution.json', attribution)
        with (OUT / 'measurements.jsonl').open('x') as stream:
            def emit(value):
                stream.write(json.dumps(value, allow_nan=False) + '\n')
                stream.flush(); os.fsync(stream.fileno())
            for branch, binding in plan['models'].items():
                model = GreedyModel(binding['model_path'], binding['tokenizer_path'], 'mlx', 'default',
                    expected_tokenizer_hash=binding['tokenizer_manifest_sha256'],
                    embedding_implementation=binding['embedding_implementation'])
                assert model.identity['model_manifest_sha256'] == binding['model_manifest_sha256']
                for i, row in enumerate(single):
                    messages = row['messages']; other = single[(i + 1) % len(single)]['messages']
                    correct = model.reference_loss(messages[:-1], messages[-1]['content'])
                    rotated = model.reference_loss(other[:-1], messages[-1]['content'])
                    emit(dict(branch=branch, kind='source_conditioning', example_id=row['example_id'],
                        correct_prompt=messages[0]['content'], rotated_prompt=other[0]['content'],
                        reference=messages[-1]['content'], correct=correct, rotated=rotated))
                for case in plan['generation_cases']:
                    response = model.generate([dict(role='user', content=case['user'])], 64)
                    emit(dict(branch=branch, kind='same_prompt_generation', case=case['id'],
                        user=case['user'], criterion=case['success_criterion'], response=response))
                save(OUT / (branch + '-identity.json'), model.identity)
                print(json.dumps(dict(branch=branch, complete=True)), flush=True)
                del model
                gc.collect()
                import mlx.core as mx
                mx.clear_cache()
        for file, expected in plan['inputs_sha256'].items():
            assert sha(file) == expected
        save(OUT / 'completion.json', dict(creator='Navneet Prabhakar', complete=True,
            plan_sha256=sha(PLAN), runner_sha256=sha(__file__),
            measurements_sha256=sha(OUT / 'measurements.jsonl'),
            attribution_sha256=sha(OUT / 'response-attribution.json'),
            source_reference_scores=60, new_generations=30, maximum_generated_tokens=1920,
            model_updates=0, teacher_calls=0, cloud_spend=0))


if __name__ == '__main__':
    main()
