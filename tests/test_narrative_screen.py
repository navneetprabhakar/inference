# Creator: Navneet Prabhakar
import pytest
from slm.data.narrative_screen import screen
from slm.data.prose_screen import RequestGuard,windows,word_key
from slm.data.schema import digest

TEXT='A young child walked through the garden and found a small bird beside the old wooden fence. She called her mother and waited nearby. Together they watched the bird open its wings and fly into a tree. The child smiled and returned home to tell her brother about their afternoon adventure.'
G=RequestGuard(['Explain the purpose of this unseen evaluation request'])
U=RequestGuard(['A different protected upstream evaluation story prefix'])

def run(text=TEXT,scores=None,heldouts=None,judgment=None):
    if scores is None:scores=[[dict(language='en',score=.99)] for _ in windows(text)]
    return screen(text,scores,G,U,heldouts or set(),judgment)

def test_ordinary_story_without_invented_source_score():
    result=run();assert result['candidate'] and result['training_approved'] is False
    assert 'no per-row' in result['source_language_evidence']

def test_exact_heldout_and_direct_nonapprovals_cannot_pass():
    assert 'official_validation_exact' in run(heldouts={digest(word_key(TEXT))})['reasons']
    for judgment in ('exclude','defer'):assert not run(judgment=judgment)['candidate']

def test_all_windows_and_alignment_are_required():
    text=TEXT*12;scores=[[dict(language='en',score=.99)] for _ in windows(text)]
    scores[-1]=[dict(language='es',score=.99)]
    assert 'window_english_signal' in run(text,scores)['reasons']
    with pytest.raises(ValueError):run(text,scores[:-1])

def test_embedded_evaluations_and_privacy_patterns():
    for suffix,reason in [('Explain the purpose of this unseen evaluation request','prior_evaluation_text_or_id'),('A different protected upstream evaluation story prefix','upstream_evaluation_prefix'),(' Reach me at person@example.com','privacy_or_secret_pattern')]:
        assert reason in run(TEXT+' '+suffix)['reasons']

def test_short_repetition_and_encoding():
    assert 'length_scope' in run('A short story.')['reasons']
    assert 'single_word_repetition_signal' in run('word '*70)['reasons']
    assert 'encoding_or_controls' in run(TEXT+'\x01')['reasons']
