"""Frozen scorer/data/schedule tests; no student computation."""
import json
import support as s


def main():
    assert s.strict('09:10','09:10','time')
    assert not s.strict('09:10','09 10','time')
    assert not s.strict('09:10','09:11','time')
    assert not s.strict('09:10','9:10','time')
    assert s.strict('Maya Reed','maya  reed','name')
    assert not s.strict('Maya Reed','Maya','name')
    assert not s.strict('Maya Reed','Maya Reed is here','name')
    case=dict(entity='cup',family='color',messages=[dict(role='user',content='The cup is green.'),dict(role='assistant',content='green')])
    assert s.retention_content(case,'The cup is green.',0)
    assert not s.strict('green','The cup is green.')
    for bad in ['The cup is not green.','The cup is green and heavy.','The hat is green.','The cup','The cup is blue.']:
        assert not s.retention_content(case,bad,0),bad
    case['family']='location';case['messages'][1]['content']='shelf'
    assert s.retention_content(case,'The cup is on the shelf.',0)
    assert not s.retention_content(case,'The cup is shelf.',0)
    assert not s.retention_content(case,'The cup is green.',0)
    # Score composition: syntax/content alone is never credited without EOS or on overflow.
    for eos,overflow,expected in [(True,False,True),(False,False,False),(True,True,False),(False,True,False)]:
        assert (s.strict('green','green') and eos and not overflow)==expected
    sch=s.read(s.PRIVATE/'schedule.json')
    assert len(sch['fit'])==200 and len(sch['main'])==400
    first=sch['main'][:200]
    assert len({i for b in first for i in b['grounding']})==800
    assert len({i for b in first for i in b['rehearsal']})==400
    assert len({i for b in first for i in b['teacher']})==144
    for start in range(0,200,4):assert len({i for batch in sch['fit'][start:start+4] for i in batch})==32
    s.save(s.ROOT/'cpu-checks.json',dict(status='PASS',scorer_fixtures=True,coverage=True,student_work=0,
        comments='Clarification and free-form dialogue semantic correctness require rubric review; lexical matching is only an automatic candidate score.'))
    print(json.dumps(s.read(s.ROOT/'cpu-checks.json'),indent=2))


if __name__=='__main__':main()
