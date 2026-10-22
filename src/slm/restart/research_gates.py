"""Frozen M1 choice-task thresholds; no capability claim beyond this research set."""
from collections import Counter
from .choice_scoring import score


def grammar(items,outputs):
    if len(items)!=200 or any(len(x['continuation_token_lengths'])!=2 for x in items) or Counter(x['subtype'] for x in items)!=dict.fromkeys(['agreement','tense','pronoun','determiner'],50):
        raise ValueError('Grammar requires the frozen 200-item, four-subtype denominator')
    result=score(items,outputs)
    passed=result['correct']>=180 and all(g['correct']>=42 for g in result['by_subtype'].values())
    return {'passed':passed,'result':result,'thresholds':{'overall':180,'each_subtype':42}}


def grounded(items,outputs,empty_outputs,shuffled_outputs):
    if len(items)!=100 or any(len(x['continuation_token_lengths'])!=4 for x in items) or Counter(x['subtype'] for x in items)!={'explicit_fact':50,'temporal_reference':50}:
        raise ValueError('Grounded requires the frozen 100-item, two-subtype denominator')
    actual=score(items,outputs);empty=score(items,empty_outputs);shuffled=score(items,shuffled_outputs)
    # A failed control execution must never manufacture a grounding advantage.
    controls_valid=all(x['failure'] in (None,'tie') for result in (empty,shuffled) for x in result['items'])
    gains={k:actual['correct']-r['correct'] for k,r in [('empty',empty),('shuffled',shuffled)]}
    passed=(controls_valid and actual['correct']>=75
            and all(g['correct']>=35 for g in actual['by_subtype'].values())
            and min(gains.values())>=15)
    return {'passed':passed,'controls_valid':controls_valid,'correct_count_gains':gains,
            'actual':actual,'empty':empty,'shuffled':shuffled,
            'thresholds':{'overall':75,'each_subtype':35,'gain_each_control':15}}
