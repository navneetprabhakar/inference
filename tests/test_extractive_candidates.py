"""Exact-span screening is neither semantic grading nor training admission."""
# Creator: Navneet Prabhakar
from copy import deepcopy
import pytest
from slm.common.tokenizer import train_core
from slm.data.schema import Source, make_example, digest
from slm.data.extractive_candidates import SOURCE, inspect, norm, raw_inventory


CONTEXT = ('The town of Luma is the starting point. This is a fictional passage for a '
           'language mechanics check, with enough additional words to describe a simple imaginary route.')


def fixture(**changes):
    raw = dict(instruction='Which town is the starting point?', context=CONTEXT,
               response='The town of Luma', category='closed_qa')
    raw.update(changes)
    source = Source(SOURCE, 'a'*40, 'https://example.org', 'cc-by-sa-3.0', 'b'*64, 'c'*64, ('fixture',))
    messages = [dict(role='user', content=raw['instruction']+'\n\nContext:\n'+raw['context']),
                dict(role='assistant', content=raw['response'])]
    row = make_example(source, digest(raw), 'family:fictional', messages, language='en',
                       content_category='sfw', official_split='train').to_dict()
    row['split'] = 'train'
    row['validation_results']['split_group'] = digest('fictional')
    bpe = train_core([CONTEXT, raw['instruction'], raw['response']]*3, 512)
    return row, raw, bpe


def test_span_proof_preserves_original_and_stays_non_admitting():
    row, raw, bpe = fixture(); before = deepcopy(row)
    reasons, proof = inspect(row, raw, bpe)
    assert reasons == [] and row == before
    start, end = proof['normalized_context_character_span']
    assert norm(raw['context'])[start:end] == norm(raw['response'])
    assert proof['prediction_positions'] == len(bpe.serialize(row['messages'])[0])
    assert proof['training_eligible'] is False and proof['semantic_relevance_verified'] is False


def test_exact_span_can_still_answer_the_wrong_question():
    row, raw, bpe = fixture(instruction='Which town is NOT the starting point?')
    reasons, proof = inspect(row, raw, bpe)
    assert reasons == []  # Deliberate counterexample; full review remains necessary.
    assert proof['semantic_relevance_verified'] is False


@pytest.mark.parametrize('changes,reason', [
    ({'response': 'The town of Luma in 2018'}, 'no_exact_answer_span'),
    ({'response': 'the town of Luma'}, 'no_exact_answer_span'),
    ({'category': 'creative_writing'}, 'category'),
    ({'instruction': 'What is the latest starting point?'}, 'time_sensitive_or_advice_question'),
    ({'context': 'Short context'}, 'context_length'),
    ({'response': 'Luma'}, 'answer_length'),
    ({'context': CONTEXT+' Contact test@example.org for more details.'}, 'privacy_or_structural_attention'),
])
def test_proposed_rule_reasons(changes, reason):
    row, raw, bpe = fixture(**changes)
    assert reason in inspect(row, raw, bpe)[0]


def test_whitespace_equivalence_does_not_rewrite_target():
    row, raw, bpe = fixture(response='The town\nof Luma')
    reasons, _ = inspect(row, raw, bpe)
    assert reasons == [] and row['messages'][-1]['content'] == 'The town\nof Luma'


def test_mismatched_raw_row_is_an_error_not_a_silent_skip():
    row, raw, bpe = fixture(); row['messages'][-1]['content'] += ' altered'
    with pytest.raises(ValueError, match='pinned raw row'):
        inspect(row, raw, bpe)


def test_published_exact_duplicates_are_counted_without_new_identities():
    _, raw, _ = fixture()
    other = {**raw, 'instruction': 'A different question'}
    rows, total = raw_inventory([raw, deepcopy(raw), other])
    assert total == 3 and len(rows) == 2
    assert rows[digest(raw)] == raw
