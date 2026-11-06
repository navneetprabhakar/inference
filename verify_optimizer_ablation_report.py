"""Small deterministic decision tests; no production model or GPU access."""
from copy import deepcopy
from optimizer_ablation_report import BRANCHES, POINTS, analyze, repetitive


def row(tokens, loss, correct=True, text='A child walked home before the rain began.'):
    return dict(trained_tokens=tokens, mean_ce=loss, document_losses=[loss]*4,
                diagnostics=dict(pairs=[dict(correct=correct)], completions=[dict(generated=text)]))


def run():
    history = [row(0, 5.)] + [row(t, 4.) for t in POINTS]
    data = {name: deepcopy(history) for name in BRANCHES}
    assert analyze(data)['selected_optimizer_recipe'] == 'preserve-095'
    for r in data['reset-scaled'][1:]:
        r['mean_ce'] = 3.95
        r['document_losses'] = [3.95]*4
    result = analyze(data)
    assert result['selected_optimizer_recipe'] == 'reset-scaled' and not result['usable_assistant']
    bad = deepcopy(data)
    bad['reset-scaled'][-1]['diagnostics']['pairs'][0]['correct'] = False
    assert analyze(bad)['selected_optimizer_recipe'] == 'preserve-095'
    bad = deepcopy(data)
    bad['reset-scaled'][-1]['diagnostics']['completions'][0]['generated'] = 'go to the park '*4
    assert analyze(bad)['selected_optimizer_recipe'] == 'preserve-095'
    bad = deepcopy(data)
    bad['reset-scaled'][1] = row(POINTS[0], 4.)
    assert analyze(bad)['selected_optimizer_recipe'] == 'preserve-095'
    for mutate in [lambda x: x.pop('reset-095'), lambda x: x['reset-scaled'].pop(),
                   lambda x: x['reset-scaled'].append(x['reset-scaled'][-1]),
                   lambda x: x['reset-scaled'].__setitem__(0, row(0, 5.1)),
                   lambda x: x['reset-scaled'][-1].__setitem__('mean_ce', 1.)]:
        bad = deepcopy(data)
        mutate(bad)
        try:
            analyze(bad)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid comparison accepted')
    assert repetitive('GO to the park go to the park go to the park')
    assert not repetitive('go to the park go to the park')
    print('PASS optimizer comparison: conditional selection, baseline identity, missing/duplicate evidence, context/repetition regressions, no quality certification')


if __name__ == '__main__':
    run()
