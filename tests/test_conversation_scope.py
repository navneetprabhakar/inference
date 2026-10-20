# Creator: Navneet Prabhakar
from slm.data.conversation_scope import constraints,scope

def test_constraints_refuse_real_failure_shapes():
    assert 'exact_ending' in constraints('Finish your response with this exact phrase "done".','done"')
    assert 'explicit_count' in constraints('Your response should contain exactly 3 bullet points.','* one\n* two')
    assert not constraints('Your response should contain exactly 2 bullet points.','* one\n* two')

def test_summary_pronoun_and_fabricated_numeric_exclusion():
    r=dict(source='smol-summarize-20k',messages=[dict(role='system',content='without using second or third person pronouns'),dict(role='user',content='Mary will call at noon.'),dict(role='assistant',content='She will call at 3.')])
    assert set(scope(r))=={'summary_prohibited_pronoun','introduced_number'}
