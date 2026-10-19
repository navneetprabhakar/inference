"""Independent boundary/count checks for the data-only conditioning diagnosis."""
# Creator: Navneet Prabhakar
import numpy as np
import pytest
from slm.common.tokenizer import BPE, STRUCTURAL
from slm.eval.foundation_conditioning import FIELDS, document, summarize, verify_batches


class Bytes:
    serialize = BPE.serialize

    def encode(self, text):
        return [n+10 for n in text.encode()]


def test_exact_training_inference_prefix_and_target_roles():
    counts = np.zeros((1, len(FIELDS)), dtype=np.int64)
    tokens, checks = document(Bytes(), [dict(role='user', content='Q'),
                                      dict(role='assistant', content='AB')], 0, 32, counts)
    assert tokens == [0, 5, 91, 3, 6, 75, 76, 3, 1]
    assert checks == 1
    r = summarize(counts)
    assert r['prediction_positions'] == 8
    assert r['targets'] == dict(assistant_content=2, user_content=1, system_content=0,
                                tool_content=0, structural=5, assistant_with_full_last_user=2,
                                assistant_with_full_document_prefix=2,
                                assistant_with_role_visible=2, assistant_without_prior_user=0,
                                document_start_targets=0)


def test_boundary_retains_role_but_loses_user_and_excludes_next_window_role():
    # With context four: targets 1..4 see inputs 0..3, 5..8 see inputs 4..7,
    # and target 9 sees inputs starting at 8. Assistant role is at position 4.
    counts = np.zeros((3, len(FIELDS)), dtype=np.int64)
    tokens, _ = document(Bytes(), [dict(role='user', content='Q'),
                                  dict(role='assistant', content='ABCDE')], 0, 4, counts)
    assert len(tokens) == 12
    r = summarize(counts)['targets']
    assert r['assistant_content'] == 5
    assert r['assistant_with_full_last_user'] == 0
    assert r['assistant_with_full_document_prefix'] == 0
    assert r['assistant_with_role_visible'] == 4
    assert counts[1, FIELDS.index('assistant_content')] == 4
    assert counts[2, FIELDS.index('assistant_content')] == 1


def test_later_user_just_before_window_is_lost_despite_visible_assistant_role():
    counts = np.zeros((5, len(FIELDS)), dtype=np.int64)
    messages = [dict(role='user', content='Q'), dict(role='assistant', content='A'),
                dict(role='user', content='B'), dict(role='assistant', content='C')]
    _, checks = document(Bytes(), messages, 0, 8, counts)
    t = summarize(counts)['targets']
    # First assistant at q5 has full document; second user role q7 is outside
    # the q11 target's input window beginning at q8.
    assert checks == 2
    assert t['assistant_with_full_document_prefix'] == 1
    assert t['assistant_with_full_last_user'] == 1
    assert t['assistant_with_role_visible'] == 2


def test_later_user_at_window_start_survives_without_document_prefix():
    counts = np.zeros((2, len(FIELDS)), dtype=np.int64)
    _, checks = document(Bytes(), [dict(role='user', content='Q'),
                                  dict(role='assistant', content='AB'),
                                  dict(role='user', content='B'),
                                  dict(role='assistant', content='C')], 0, 8, counts)
    t = summarize(counts)['targets']
    assert checks == 2
    assert t['assistant_content'] == 3
    assert t['assistant_with_full_document_prefix'] == 2
    assert t['assistant_with_full_last_user'] == 3
    assert t['assistant_with_role_visible'] == 3


def test_second_document_bos_is_a_cross_document_prediction_target():
    counts = np.zeros((2, len(FIELDS)), dtype=np.int64)
    a, _ = document(Bytes(), [dict(role='user', content='Q'), dict(role='assistant', content='A')], 0, 8, counts)
    b, _ = document(Bytes(), [dict(role='user', content='X'), dict(role='assistant', content='B')], len(a), 8, counts)
    r = summarize(counts)
    assert r['prediction_positions'] == len(a)+len(b)-1
    assert r['targets']['document_start_targets'] == 1
    assert r['targets']['assistant_with_full_document_prefix'] == 2
    stream = np.asarray(a+b)
    data = [(stream[i:min(i+8, len(stream)-1)][None, :], stream[i+1:i+9][None, :], np.ones((1, min(8, len(stream)-1-i))))
            for i in range(0, len(stream)-1, 8)]
    verify_batches(data, stream, counts)
    x, y, mask = data[0]
    data[0] = (x, y+1, mask)
    with pytest.raises(ValueError, match='prepared tokens'):
        verify_batches(data, stream, counts)


def test_assistant_without_user_not_counted_as_conditioned():
    counts = np.zeros((1, len(FIELDS)), dtype=np.int64)
    _, checks = document(Bytes(), [dict(role='assistant', content='A')], 0, 16, counts)
    t = summarize(counts)['targets']
    assert checks == 0 and t['assistant_without_prior_user'] == 1
    assert t['assistant_with_full_last_user'] == 0


def test_framing_or_mask_corruption_is_not_accepted():
    class Altered(Bytes):
        def serialize(self, *args, **kwargs):
            x, y, m = super().serialize(*args, **kwargs)
            x[0] = STRUCTURAL['eos']
            return x, y, m
    counts = np.zeros((1, len(FIELDS)), dtype=np.int64)
    with pytest.raises(ValueError, match='prefix differs'):
        document(Altered(), [dict(role='user', content='Q'), dict(role='assistant', content='A')], 0, 16, counts)
    stream = np.array([0, 5, 91, 3, 6, 75, 3, 1])
    counts[0, 0] = 7
    with pytest.raises(ValueError, match='prepared tokens or masks'):
        verify_batches([(stream[:-1][None, :], stream[1:][None, :], np.zeros((1, 7)))], stream, counts)
