import pytest
from slm.restart.research_gates import grammar,grounded

def fixtures(subtypes,n,choices=2):
    return [dict(id=str(i),subtype=subtypes[i//n],correct_index=0,continuation_token_lengths=[1]*choices) for i in range(n*len(subtypes))]

def outputs(items,correct):
    result=[]
    for i,x in enumerate(items):
        values=[[-1.,-1.] for _ in x['continuation_token_lengths']]
        values[0 if i in correct else 1]=[-.1,-.1]
        result.append(dict(id=x['id'],token_log_probabilities=values))
    return result

def test_grammar_subtype_floor_cannot_be_hidden_by_total():
    items=fixtures(['agreement','tense','pronoun','determiner'],50)
    assert not grammar(items,outputs(items,set(range(20,200))))['passed']  # 180 overall, 30 in first group
    selected=set(range(45))|set(range(50,95))|set(range(100,145))|set(range(150,195))
    assert grammar(items,outputs(items,selected))['passed']

def test_grounding_gain_includes_exact_boundary_without_float_rounding():
    items=fixtures(['explicit_fact','temporal_reference'],50,4)
    actual=outputs(items,set(range(40))|set(range(50,85)))
    control=outputs(items,set(range(60)))
    assert grounded(items,actual,control,control)['passed']
    assert not grounded(items,actual,outputs(items,set(range(61))),control)['passed']

def test_missing_control_does_not_manufacture_gain():
    items=fixtures(['explicit_fact','temporal_reference'],50,4);actual=outputs(items,set(range(100)))
    r=grounded(items,actual,[],outputs(items,set()))
    assert not r['passed'] and not r['controls_valid']

def test_wrong_denominator_is_rejected():
    with pytest.raises(ValueError):grammar([],[])
    with pytest.raises(ValueError):grounded([],[],[],[])
