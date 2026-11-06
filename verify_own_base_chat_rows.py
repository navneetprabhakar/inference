"""CPU-only synthetic checks; no datasets, checkpoints or protected cases."""
from copy import deepcopy
import hashlib
import json

from dialogue import IGNORE, _frames, assistant_prompt
from own_base_chat import policy_text
from own_base_chat_rows import build_chat_rows, TRANSFORMATION_VERSION
from tokenizer import load


def run():
    tok = load()
    source = [dict(role='system', text='  Answer exactly.\nKeep whitespace.  '),
              dict(role='user', text='  First input\n '),
              dict(role='assistant', text='First answer.'),
              dict(role='user', text='Second input'),
              dict(role='assistant', text='Second answer.')]
    frozen = deepcopy(source)
    provenance = {'publisher': 'synthetic', 'record_id': 'test-1'}
    result = build_chat_rows(tok, source, provenance=provenance)
    assert source == frozen
    assert result['histories'][0][1]['text'] == ('Task instructions:\n' + source[0]['text'] +
                                               '\n\nInput:\n' + source[1]['text'])
    assert result['metadata']['original_history'] == source
    canonical = json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    assert result['metadata']['original_history_sha256'] == hashlib.sha256(canonical).hexdigest()
    assert result['metadata']['transformation_version'] == TRANSFORMATION_VERSION
    assert result['metadata']['publisher_system_relocated'] is True
    assert result['metadata']['teacher_quality_certified'] is False
    provenance['publisher'] = 'changed'
    assert result['metadata']['provenance']['publisher'] == 'synthetic'
    targets = []
    for history, row in zip(result['histories'], result['rows']):
        assert history[0] == dict(role='system', text=policy_text())
        prompt = assistant_prompt(tok, history[:-1], reply_budget=256, context=1024)
        raw, _, _ = _frames(tok, history)
        assert raw[:len(prompt)] == prompt
        expected = raw[len(prompt):]
        actual = [label for label in row.labels if label != IGNORE]
        assert actual == expected
        assert all(label == IGNORE for label in row.labels[:len(prompt)-1])
        targets.extend(actual)
    assert result['counters']['supervised_targets'] == len(targets)
    assert sum(result['position_exposure'].values()) == len(targets)
    assert result['counters']['rows'] == 2
    # Text/target identity is retained without a publisher system.
    plain = frozen[1:]
    unchanged = build_chat_rows(tok, plain, permit_calls=False)
    assert unchanged['histories'][-1][1:] == plain
    assert unchanged['histories'][-1][0]['text'] == policy_text(False)
    assert unchanged['metadata']['publisher_system_relocated'] is False
    # Exposure bins use predicted positions, not unshifted label offsets.
    for row, counts in zip(result['rows'], result['per_row_position_exposure']):
        expected = {key: 0 for key in counts}
        for index, label in enumerate(row.labels):
            if label != IGNORE:
                for key in expected:
                    low, high = map(int, key.split('..'))
                    if low <= index + 1 <= high: expected[key] += 1
        assert expected == counts
    # Mutation of an output does not mutate caller data or other row prefixes.
    result['histories'][0][1]['text'] = 'mutated'
    result['metadata']['original_history'][0]['text'] = 'mutated'
    assert source == frozen and result['histories'][1][1]['text'] != 'mutated'
    failures = [[], [dict(role='user', text='unfinished')],
                [dict(role='assistant', text='wrong order'), dict(role='user', text='x')],
                [dict(role='system', text='x ' * 2000)] + plain,
                [dict(role='user', text='x'), dict(role='assistant', call={'name':'calculate'})],
                [dict(role='user', text='x'), dict(role='tool', text='result')],
                [dict(role='user', text='x'), dict(role='assistant', text='ok'),
                 dict(role='system', text='late'), dict(role='assistant', text='no')],
                plain + [dict(role='user', text='x ' * 2000), dict(role='assistant', text='no')],
                [dict(role='user', text='x'), dict(role='assistant', text='word ' * 300)],
                [dict(role='user', text='x', call_id='injected'), dict(role='assistant', text='ok')]]
    for history in failures:
        before = deepcopy(history)
        try: build_chat_rows(tok, history)
        except (ValueError, TypeError): pass
        else: raise AssertionError('invalid complete history accepted')
        assert history == before
    print(json.dumps(dict(state='passed', turn_rows=2, refusals=len(failures),
                          checks=['verbatim relocation and original hash', 'no-system identity',
                                  'current-turn-only exact targets without duplication',
                                  'runtime generation prefix equality', 'position exposure',
                                  'nonmutation', 'whole-history atomic refusal'],
                          gpu_operations=False, corpus_scanned=False, teacher_quality_certified=False), indent=2))


if __name__ == '__main__': run()
