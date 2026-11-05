"""One-shot fit on hash-cleared rows; promote only after preregistered checks."""
from collections import Counter
import json
from pathlib import Path

from tools import FixtureSession
from trace_readback_curriculum import DIR
from trace_readback_head import Head, digest, fit, render
from trace_readback_holdout import TEST

APPROVED_SHA = '1b7625bed962e65e781a9f9aced180605bf9f75619380a99b9fd3d1e923c14b0'
PROTOCOL_SHA = '0efecfd6ff7467cc75e3a48627ad59cfffa13278a8df9b2380d9a0b54f2ef650'
HOLDOUT_SHA = '4103f9b2064bb59899d4fbd3574d537fa8816945e5232b6e5abecb6a06da3642'


def save(path, obj):
    path.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n')


def event(session,name,args,fixture=None):
    call = {'name':name,'arguments':args}
    session.start_turn(permit_calls=True, fixture_for=call if fixture else None,fixture=fixture)
    return session.propose(json.dumps(call),assistant_call_boundary=True)


def render_checks():
    s = FixtureSession()
    first = event(s,'calculate',{'a':8,'b':2,'op':'multiply'},{'result':-37})
    second = event(s,'convert',{'value':2,'from':'kg','to':'g'},{'result':0})
    third = event(s,'calculate',{'a':1,'b':0,'op':'divide'})
    fourth = event(s,'convert',{'value':1,'from':'h','to':'min'},{'error':'fixture offline'})
    checks = []
    for label,record,expected in [
        ('a',first,'8'),('b',first,'2'),('result',first,'-37'),('positive',first,'No.'),
        ('negative',first,'Yes.'),('zero',first,'No.'),('gt',first,'No.'),('lt',first,'Yes.'),
        ('eq',first,'No.'),('amount',second,'2'),('source',second,'kg'),('target',second,'g'),
        ('tool',second,'convert'),('result',second,'0'),('zero',second,'Yes.'),('eq',second,'Yes.'),
        ('a',second,None),('status',first,'The call succeeded.'),
        ('b',third,None),('result',third,'No result. The call failed: division by zero'),
        ('status',fourth,'The call failed: fixture offline'),('positive',fourth,'No result. The call failed: fixture offline'),
        ('result',None,None)]:
        checks.append(render(label,record,'was the result equal to 0?')==expected)
    return checks


def main():
    path = DIR/'approved-teaching.jsonl'
    assert digest(path)==APPROVED_SHA and digest(DIR/'protocol.json')==PROTOCOL_SHA
    assert digest(Path(__file__).with_name('trace_readback_holdout.py'))==HOLDOUT_SHA
    if (DIR/'result.json').exists():
        raise ValueError('first-use holdout already scored')
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert not {r['user'].casefold() for r in rows} & {q.casefold() for qs in TEST.values() for q in qs}
    state=fit(rows)
    head=Head(state)
    save(DIR/'weights.json',state)
    totals=Counter()
    correct_by_label=Counter()
    for label, questions in TEST.items():
        for text in questions:
            prediction=head.decide(text)
            totals['positive']+=label!='defer'
            totals['claimed']+=prediction is not None
            totals['negative_claims']+=label=='defer' and prediction is not None
            if prediction==label:
                correct_by_label[label]+=1
                totals['correct']+=1
    precision=totals['correct']/max(1,totals['claimed'])
    coverage=totals['correct']/totals['positive']
    spec=json.loads((DIR/'protocol.json').read_text())
    rendering=render_checks()
    checks={'precision':precision>=spec['precision_min'],
            'coverage':coverage>=spec['correct_positive_coverage_min'],
            'negative_claims':totals['negative_claims']<=spec['false_positive_on_defers_max'],
            'families':len(correct_by_label)>=spec['minimum_families_correct'],'rendering':all(rendering)}
    report={'accepted':all(checks.values()),'checks':checks,'totals':totals,'precision':precision,'coverage':coverage,
            'negative_cases':len(TEST['defer']),'correct_by_family':correct_by_label,'render_checks':len(rendering),
            'teaching_sha':APPROVED_SHA,'holdout_sha':HOLDOUT_SHA,'protocol_sha':PROTOCOL_SHA,
            'classifier_sha':digest(Path(__file__).with_name('trace_readback_head.py'))}
    save(DIR/'result.json',report)
    if report['accepted']:
        save(DIR/'accepted-pin.json',{'files':{f:digest(DIR/f) for f in ('result.json','protocol.json','weights.json')}})
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
