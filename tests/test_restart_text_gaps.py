import pytest
from slm.restart.text_gaps import find_gaps

@pytest.mark.parametrize('text,rule',[
 ('The area of the park is .','missing_quantity'),
 ('It covered a territory of  at an elevation of 750 metres.','missing_prepositional_object'),
 ('Its speed was .','missing_quantity'),
 ('The ship sighted the .','missing_named_subject'),
 ('Current population:  It is named after the river.','blank_population_field'),
 ('The town () is near a river.','empty_parenthetical'),
 ('Ehsan (; born in 1993) played cricket.','none'),
 ('He was a member of Lodge # ___.','unfilled_placeholder'),
 ('The citation for the award reads as follows: \n\nAfter the war, he returned.','unfilled_citation_transition'),
])
def test_observed_damage_patterns(text,rule):
    findings=find_gaps(text)
    if rule=='none':assert not findings
    else:assert rule in {x['rule'] for x in findings}
    for f in findings:assert text[f['start']:f['end']]==f['matched_text']

@pytest.mark.parametrize('text',[
 'Its area is 0. The population was 1,200.',
 'The ship  was built in 1915. Its speed was 12 knots.',
 'The town (formerly known as North Town) is small.',
 'Current population: 200 residents.',
 'He asked what it was.',
 'The citation for the award reads as follows:\n\n“His courage was exemplary.”',
])
def test_complete_prose_not_flagged(text):
    assert not find_gaps(text)
