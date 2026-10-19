"""Publisher ratings are fail-closed selection signals, never admission."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import pytest
from slm.data.oasst_sft_screen import RULE, node_flags, rating, measure


def valid_node(assistant=True):
    labels = {name: dict(count=2, value=0.) for name in RULE['zero_flags']}
    labels.update(quality=dict(count=2, value=.75), helpfulness=dict(count=2, value=.75))
    return dict(lang='en', deleted=False, review_result=True, synthetic=False, model_name=None,
                text='A complete rated message.', role='assistant' if assistant else 'prompter', rank=0, labels=labels)


def test_threshold_boundary_is_only_a_candidate_signal():
    assert not node_flags(valid_node(), True)
    assert RULE['training_eligible'] is False


@pytest.mark.parametrize('value', [None, {}, {'count': True, 'value': .9},
                                  {'count': 2, 'value': True}, {'count': 2, 'value': float('nan')},
                                  {'count': 2, 'value': 1.1}, {'count': 0, 'value': .9}])
def test_bad_rating_is_missing(value):
    node = valid_node()
    node['labels']['quality'] = value
    assert rating(node, 'quality') is None
    assert 'missing_assistant_rating' in node_flags(node, True)


@pytest.mark.parametrize('labels', [None, [], 'unrated'])
def test_bad_label_container_is_not_positive_evidence(labels):
    node = valid_node()
    node['labels'] = labels
    assert 'missing_flag_rating' in node_flags(node, True)


def test_good_quality_does_not_override_failed_task_or_missing_flag():
    node = valid_node()
    node['labels']['quality']['value'] = 1.
    node['labels']['fails_task']['value'] = .01
    assert 'nonzero_flag_rating' in node_flags(node, True)
    del node['labels']['pii']
    assert 'missing_flag_rating' in node_flags(node, True)


@pytest.mark.parametrize('rank', [None, True, 1, -1])
def test_rank_not_zero_integer_is_refused(rank):
    node = valid_node()
    node['rank'] = rank
    assert 'not_top_ranked_assistant' in node_flags(node, True)


def test_unrated_or_low_helpfulness_is_not_replaced_by_quality():
    node = valid_node()
    node['labels']['helpfulness']['count'] = 1
    assert 'missing_assistant_rating' in node_flags(node, True)
    node['labels']['helpfulness'] = dict(count=2, value=.749)
    assert 'low_assistant_rating' in node_flags(node, True)


def test_user_does_not_require_assistant_quality_or_rank():
    node = valid_node(False)
    for key in ('quality', 'helpfulness', 'fails_task'):
        del node['labels'][key]
    node['rank'] = None
    assert not node_flags(node, False)
    assert 'raw_role' in node_flags(node, True)


@pytest.mark.parametrize('field,value', [('lang', 'es'), ('synthetic', True), ('deleted', True),
                                        ('review_result', False), ('model_name', 'unknown')])
def test_ratings_do_not_override_origin_eligibility(field, value):
    node = valid_node()
    node[field] = value
    assert node_flags(node, True)


def test_rating_check_does_not_mutate_raw_metadata():
    node = valid_node()
    before = deepcopy(node)
    node_flags(node, True)
    assert node == before


def test_existing_output_is_refused_before_reading_inputs(tmp_path):
    with pytest.raises(FileExistsError):
        measure('missing', 'missing', 'missing', 'missing', tmp_path, source_record='missing')
