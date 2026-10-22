import pytest
from slm.restart.choice_scoring import score

def item(key='a',answer=0):return dict(id=key,correct_index=answer,subtype='agreement',continuation_token_lengths=[2,2])
def out(key='a',values=None):return dict(id=key,token_log_probabilities=values if values is not None else [[-.1,-.1,-3.],[-.4,-.4,-.4]])

def test_eos_and_entire_continuation_count_not_first_token():
    result=score([item(answer=1)],[out()])
    assert result['correct']==1 and result['items'][0]['scores']==pytest.approx([-3.2,-1.2])

@pytest.mark.parametrize('values',[
 [[-.1,-.2,-.3],[-.1,-.2,-.3]],
 [[-.1,-.2],[-.1,-.2]],
 [[float('nan'),-.1,-.1],[-1.,-1.,-1.]],
 [[float('inf'),-.1,-.1],[-1.,-1.,-1.]],
 [[.01,-.1,-.1],[-1.,-1.,-1.]],
])
def test_bad_or_tied_output_cannot_pass(values):
    result=score([item()],[out(values=values)])
    assert result['correct']==0 and result['items'][0]['failure']

def test_missing_and_execution_errors_remain_in_denominator():
    result=score([item('a'),item('b'),item('c',1)],[{'id':'a','error':'timeout'},out('c')])
    assert result['correct']==1 and result['total']==3

@pytest.mark.parametrize('outputs',[[out(),out()],[out('other')]])
def test_duplicate_and_unknown_results_invalid(outputs):
    with pytest.raises(ValueError):score([item()],outputs)

def test_length_mismatch_is_not_hidden_by_length_normalization():
    case=item();case['continuation_token_lengths']=[1,2]
    with pytest.raises(ValueError):score([case],[out()])
