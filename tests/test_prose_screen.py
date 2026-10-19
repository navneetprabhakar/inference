"""Ensure raw prose cannot bypass window, history or evaluation isolation."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import pytest
from slm.data.prose_screen import RequestGuard, screen, windows

PROMPT = 'Choose the second option and return only its identifier.'


def example():
    return dict(text=' '.join('term' + str(i) for i in range(200)),
                language='en', language_score=0.99)


def assess(row, **kwargs):
    scores = [[dict(language='en', score=0.99)] for _ in windows(row['text'])]
    return screen(row, scores, RequestGuard([PROMPT]), **kwargs)


def test_candidate_is_not_verification_and_input_not_mutated():
    row = example(); before = deepcopy(row)
    result = assess(row)
    assert result['candidate'] and not result['training_approved'] and not result['privacy_verified']
    assert not result['factual_accuracy_verified'] and result['content_category'] == 'unreviewed'
    assert row == before


def test_embedded_normalized_request_and_reserved_identifiers():
    row = example()
    row['text'] += '\nA quoted task: CHOOSE, the SECOND option; and return ONLY its IDENTIFIER!\nMore prose.'
    result = assess(row)
    assert 'protected_evaluation_request_or_id' in result['reasons'] and result['protected_request_hashes']
    row = example(); row['text'] += '\n eval-tools-v1/catalog/7'
    assert 'protected_evaluation_request_or_id' in assess(row)['reasons']


def test_word_boundaries_and_unseen_paraphrase_limit():
    guard = RequestGuard([PROMPT])
    assert not guard.matches('Choose the second option and return only its identifiersuffix.')
    assert not guard.matches('Give back just the identifier for option number two.')


def test_foreign_tail_and_incomplete_window_coverage():
    row = example(); parts = windows(row['text'])
    assert len(parts) >= 2
    scores = [[dict(language='en', score=0.99)] for _ in parts]
    scores[-1] = [dict(language='pt', score=0.99)]
    result = screen(row, scores, RequestGuard([PROMPT]))
    assert 'window_english_signal' in result['reasons']
    with pytest.raises(ValueError, match='coverage'):
        screen(row, scores[:-1], RequestGuard([PROMPT]))


@pytest.mark.parametrize('partition', ['validation', 'test'])
def test_heldouts_never_become_candidates(partition):
    result = assess(example(), frozen_partition=partition)
    assert not result['candidate'] and result['original_frozen_partition'] == partition


@pytest.mark.parametrize('decision', ['exclude', 'defer'])
def test_observed_nonapproval_is_not_erased_by_automatic_signals(decision):
    assert 'prior_direct_' + decision in assess(example(), known_judgment=decision)['reasons']


def test_privacy_patterns_are_quarantine_signals_not_certainty():
    row = example(); row['text'] += '\nContact public@example.org for details.'
    result = assess(row)
    assert not result['candidate'] and result['privacy_pattern_counts']['email'] == 1
    assert not result['privacy_verified']


def test_boilerplate_and_source_signal():
    row = example(); row['text'] += '\n' + '\n'.join(['Repeated navigation link'] * 20)
    assert 'duplicate_line_signal' in assess(row)['reasons']
    row = example(); row['language_score'] = float('nan')
    assert 'source_english_signal' in assess(row)['reasons']
