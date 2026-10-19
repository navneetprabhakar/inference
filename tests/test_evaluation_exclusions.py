"""Prevent future intake from reusing evaluation requests or actual replies."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import json
import pytest
from slm.data.evaluation_exclusions import compile_inventory, EvaluationExclusions
from slm.data.tokenized import sha

REQUEST = 'Remember the purple cup and answer with its color only.'
REPLY = 'The main idea is most important in this unrelated story.'


def inventory(tmp_path):
    rows = [dict(kind='request', text=REQUEST, origin='suite/1/user'),
            dict(kind='generated_response', text=REPLY, origin='transcript/1/response')]
    value = compile_inventory(rows, {'fixture': '0' * 64})
    p = tmp_path / 'inventory.json'; p.write_text(json.dumps(value))
    return p, value


def test_prompt_and_response_are_both_checked_without_rewriting(tmp_path):
    p, _ = inventory(tmp_path); guard = EvaluationExclusions(p, sha(p))
    row = dict(text='Unrelated clean passage.', prompt='Quoted: '+REQUEST)
    before = deepcopy(row); assert guard.inspect_record(row)['blocked']; assert row == before
    row = dict(text='Quoted: '+REPLY, prompt='Independent writing instruction.')
    assert guard.inspect_record(row)['hits']['text'][0]['kinds'] == ['generated_response']


def test_normalization_boundaries_and_paraphrase_limit(tmp_path):
    p, _ = inventory(tmp_path); guard = EvaluationExclusions(p, sha(p))
    assert guard.matches('A quote: REMEMBER, the purple cup; and ANSWER with its color only!')
    assert not guard.matches(REQUEST[:-1]+'suffix')
    assert not guard.matches('Say just the shade of the violet mug.')


def test_one_normalized_text_retains_request_response_origins():
    v = compile_inventory([dict(kind='request',text=REQUEST,origin='a'),
                           dict(kind='generated_response',text=REQUEST.upper(),origin='b')], {'f':'0'*64})
    assert v['distinct_texts']==1 and v['source_records']==2
    assert v['entries'][0]['kinds']==['generated_response','request']
    assert v['entries'][0]['origins']==['a','b']


@pytest.mark.parametrize('text', ['', 'yes', '0', 'How many tickets?'])
def test_short_labels_cannot_be_global_exclusions(text):
    with pytest.raises(ValueError):
        compile_inventory([dict(kind='generated_response',text=text,origin='case')], {'f':'0'*64})


def test_external_hash_and_live_mutation_are_rejected(tmp_path):
    p, _ = inventory(tmp_path)
    with pytest.raises(ValueError,match='hash'):EvaluationExclusions(p,'0'*64)
    guard = EvaluationExclusions(p,sha(p));p.write_text(p.read_text()+' ')
    with pytest.raises(ValueError,match='changed'):guard.matches(REQUEST)


def test_rehashed_key_forgery_and_symlink_are_rejected(tmp_path):
    p, v = inventory(tmp_path);v['entries'][0]['key']='invented key';p.write_text(json.dumps(v))
    with pytest.raises(ValueError,match='entry'):EvaluationExclusions(p,sha(p))
    link=tmp_path/'alias.json';link.symlink_to(p)
    with pytest.raises(ValueError,match='regular'):EvaluationExclusions(link,sha(p))


def test_missing_field_and_unknown_kind_fail_closed(tmp_path):
    p, _ = inventory(tmp_path);guard=EvaluationExclusions(p,sha(p))
    with pytest.raises(ValueError):guard.inspect_record({'title':'No body'})
    with pytest.raises(ValueError):guard.inspect_record({'text':None})
    with pytest.raises(ValueError):compile_inventory([dict(kind='approved_training',text=REQUEST,origin='a')], {'f':'0'*64})
