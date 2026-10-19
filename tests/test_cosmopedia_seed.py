"""Reject ambiguous provenance instead of inventing a seed document identity."""
# Creator: Navneet Prabhakar
import pytest
from slm.data.cosmopedia_seed import extract

SEED = 'A synthetic source paragraph contains enough ordinary words to exercise exact excerpt lineage without pretending to be a real web document.'


def row(command='Write a synthetic unit.', punctuation='', newline='\n'):
    return dict(seed_data='fineweb', prompt='Here is an extract from a webpage:' + newline + '"' + SEED + '"' + punctuation + newline * 2 + command)


def test_shared_excerpt_under_different_prompts_and_exact_offsets():
    first, second = row(), row('Create a different synthetic story.', '.')
    a, b = extract(first), extract(second)
    assert a['proposed_exact_seed_family'] == b['proposed_exact_seed_family']
    assert a['prompt_sha256'] != b['prompt_sha256']
    assert first['prompt'][a['seed_start']:a['seed_end']] == SEED == a['seed_excerpt']
    assert first['prompt'][a['instruction_start']:] == 'Write a synthetic unit.'
    assert not a['underlying_document_id_verified']


def test_internal_quotes_and_crlf_are_preserved():
    value = row(newline='\r\n'); value['prompt'] = value['prompt'].replace('ordinary words', 'ordinary "quoted" words')
    result = extract(value)
    assert '"quoted"' in result['seed_excerpt'] and value['prompt'][result['seed_start']:result['seed_end']] == result['seed_excerpt']


@pytest.mark.parametrize('defect', ['constituent', 'header', 'boundary', 'ambiguous', 'short', 'oversize'])
def test_unknown_or_ambiguous_profiles_refused(defect):
    value = row()
    if defect == 'constituent': value['seed_data'] = 'openhermes2.5'
    elif defect == 'header': value['prompt'] = value['prompt'].replace('extract', 'unknown')
    elif defect == 'boundary': value['prompt'] = value['prompt'].replace('\n\nWrite', '\nWrite')
    elif defect == 'ambiguous': value['prompt'] += '"\n\nWrite another hidden instruction.'
    elif defect == 'short': value['prompt'] = value['prompt'].replace(SEED, 'tiny')
    else: value['prompt'] = 'x' * 40001
    with pytest.raises(ValueError): extract(value)
