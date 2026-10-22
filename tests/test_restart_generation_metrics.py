import pytest
from slm.restart.generation_metrics import diagnostics,grade,copy_match,copy_gate,DIMENSIONS

def test_repetition_and_short_eos_are_observable():
    d=diagnostics('The little bird flew. '*3,ended_with_eos=True)
    assert d['fourgram_failure'] and d['threefold_sentence_failure'] and d['early_eos_failure']
    assert not d['requested_length_ok']

def test_empty_output_is_not_acceptable_even_with_perfect_rubric():
    assert not grade('',ended_with_eos=True,scores=dict.fromkeys(DIMENSIONS,2),premise_contradiction=False)['acceptable']

def test_rubric_cannot_hide_zero_or_premise_contradiction():
    text=' '.join('word'+str(i) for i in range(90))+'.'
    scores=dict.fromkeys(DIMENSIONS,2)
    assert grade(text,ended_with_eos=True,scores=scores,premise_contradiction=False)['acceptable']
    scores['entity_reference']=0
    assert not grade(text,ended_with_eos=True,scores=scores,premise_contradiction=False)['acceptable']
    scores['entity_reference']=2
    assert not grade(text,ended_with_eos=True,scores=scores,premise_contradiction=True)['acceptable']

def test_copy_requires_exact_full_reference_not_partial_or_later_match():
    ref=list(range(10,74))
    assert copy_match(ref+[90],ref)['exact_next_64_copy']
    assert copy_match(ref[:63],ref)['reference_prefix_match_tokens']==63
    assert not copy_match([99]+ref,ref)['exact_next_64_copy']

def test_copy_stop_and_final_gate_have_distinct_frozen_conditions():
    def rows(n):return [{'exact_next_64_copy':i<n} for i in range(100)]
    r=copy_gate(rows(6),rows(2));assert not r['final_gate_pass'] and not r['automatic_copy_stop']
    assert copy_gate(rows(6),rows(0))['automatic_copy_stop']
    assert copy_gate(rows(5),rows(0))['final_gate_pass']
    with pytest.raises(ValueError):copy_gate([{}]*100,rows(0))
