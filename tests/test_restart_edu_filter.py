from slm.restart.edu_filter import transform

def row(text,**kw):return dict(text=text,url='https://example.org/article',language='en',language_score=.99,score=4.5)|kw

def test_exact_trailing_repair_only_at_tail():
    text='\n'.join([f'The {i}th paragraph describes a different observation in the experiment.' for i in range(20)])+'\nTake a look:'
    cleaned,reasons,edits=transform(row(text))
    assert cleaned==text.rsplit('\n',1)[0] and len(edits)==1
    mid='Take a look:\n'+text.rsplit('\n',1)[0]
    assert transform(row(mid))[0]==mid

def test_profile_and_concatenation_rejected():
    _,reasons,_=transform(row('Part of the book: A\nPart of the book: B',url='https://example.org/profiles/12'))
    assert 'index_or_profile_url' in reasons and 'concatenated_book_blurbs' in reasons

def test_source_threshold_and_corruption_are_explicit():
    _,reasons,_=transform(row('Broken \ufffd text',score=3.,language_score=.8))
    assert {'educational_score_below_4','language_metadata','encoding_or_control'}<=set(reasons)
