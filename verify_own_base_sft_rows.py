"""Synthetic mask and framing checks; no datasets, model or GPU."""
from dialogue import IGNORE, _frames, training_row
from own_base_sft_rows import last_turn_row, validate_reply_reservations
from tokenizer import load


def rejected(action):
    try:
        action()
    except ValueError:
        return
    raise AssertionError('expected a refusal')


def main():
    tok = load()
    call = dict(name='calculate', arguments=dict(op='add', a=3, b=4))
    history = [dict(role='system', text='Current turn permits calculator use.'),
               dict(role='user', text='Remember the label amber.'),
               dict(role='assistant', text='The label is amber.'),
               dict(role='user', text='Add three and four.'),
               dict(role='assistant', call=call, call_id='c1'),
               dict(role='tool', record=dict(call_id='c1', name='calculate',
                    arguments=call['arguments'], ok=True, data={'result': 7})),
               dict(role='assistant', text='The result is 7.')]
    full = training_row(tok, history)
    current = last_turn_row(tok, history)
    prefix, _, _ = _frames(tok, history[:3])
    cut = len(prefix)-1
    assert full.inputs == current.inputs
    assert any(v != IGNORE for v in full.labels[:cut])
    assert all(v == IGNORE for v in current.labels[:cut])
    assert current.labels[cut:] == full.labels[cut:]
    lengths = validate_reply_reservations(tok, history)
    expected = sum(r['reply_tokens'] for r in lengths if r['message_index'] >= 3)
    assert current.target_count == expected
    assert len(lengths) == 3 and all(r['prefix_tokens']+256 <= 1024 for r in lengths)
    single = [dict(role='user', text='Hello'), dict(role='assistant', text='Hello there.')]
    assert last_turn_row(tok, single).labels == training_row(tok, single).labels
    old_changed = [dict(m) for m in history]
    old_changed[2] = dict(role='assistant', text='Earlier unscored context has changed substantially.')
    assert [x for x in last_turn_row(tok, old_changed).labels if x != IGNORE] == \
           [x for x in current.labels if x != IGNORE]
    rejected(lambda: last_turn_row(tok, history[:-1]))
    rejected(lambda: last_turn_row(tok, history, reply_budget=2))
    long_prefix = [dict(role='user', text='detail '*800), dict(role='assistant', text='OK.')]
    assert len(training_row(tok, long_prefix).inputs) < 1024
    rejected(lambda: last_turn_row(tok, long_prefix))
    broken = [dict(m) for m in history]
    broken[5] = dict(role='tool', record=dict(history[5]['record'], call_id='wrong'))
    rejected(lambda: last_turn_row(tok, broken))
    print('PASS: current-turn mask, all current call/final targets, exact inference framing, prior-context independence and four refusals; no model/data/GPU')


if __name__ == '__main__':
    main()
