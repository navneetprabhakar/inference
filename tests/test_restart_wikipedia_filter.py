from slm.restart.wikipedia_filter import transform

def row(text, **kwargs):
    return {'id':'123','url':'https://en.wikipedia.org/wiki/Example','title':'Example','text':text,**kwargs}

def test_boundary_preserves_exact_source_and_attribution():
    source='A readable first paragraph.\n\nA second paragraph.\n\nReferences \nImported text attribution.\n\nCategories'
    text, reasons, edits, removed=transform(row(source))
    assert text=='A readable first paragraph.\n\nA second paragraph.'
    assert text+removed==source
    assert 'Imported text attribution.' in removed
    assert edits[0]['heading']=='References'

def test_heading_word_inside_sentence_does_not_cut():
    source='References to this building are numerous.\nThe building has a long history.'
    text,_,edits,removed=transform(row(source))
    assert text==source and not edits and not removed

def test_stubs_and_disambiguation_are_not_prose():
    assert 'word_length_outside_150_1800' in transform(row('A small town.'))[1]
    assert 'disambiguation' in transform(row('Example may refer to:\nA place.'))[1]
    assert 'list_page' in transform(row('Several items.',title='List of places'))[1]

def test_source_identity_and_visible_corruption_fail_closed():
    reasons=transform(row('A broken {{template}}.\nA second line.',id='',url='https://example.org/wiki/Example'))[1]
    assert {'unexpected_page_url','missing_page_identity','markup_or_formula_residue'}<=set(reasons)

def test_trailing_category_is_not_silently_rewritten():
    source='A paragraph about a building.\n\nBuildings in Wales'
    text,reasons,_,removed=transform(row(source))
    assert text==source and not removed
    assert 'unfinished_or_category_ending' in reasons

def test_empty_rejected_without_fabricated_text():
    assert transform(row(None))==(None,['empty'],[],'')
