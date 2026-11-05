"""One-shot audited fit and first-use evaluation, including actual tool-session execution."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from followon_product_chat import accepted_head
from reference_ops_chat import Chat
from reference_ops_curriculum import DIR
from reference_ops_head import fit,predict
from reference_ops_holdout import NEGATIVE,POSITIVE
from tools import FixtureSession
from trace_readback_chat import selected_readback
from trace_readback_head import digest


def save(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def runtime(patterns):
    # Same .turn, learned heads, host permissions, trace, serializer and adapter.
    # Tiny byte tokenizer and empty model stand in for GPT (evaluated path doesn't decode it).
    chat=Chat.__new__(Chat)
    chat.patterns=patterns
    chat.reference_call=False
    chat.reference_notice=None
    chat.session=FixtureSession()
    chat.model=SimpleNamespace(positions=SimpleNamespace(num_embeddings=8192))
    chat.guard=Mock()
    chat.tok=SimpleNamespace(decode=lambda seq:bytes(seq).decode(),encode=lambda text:SimpleNamespace(ids=list(text.encode())))
    chat.ids=[]
    chat.history=[]
    chat.last_request=None
    chat.readback_answer=None
    chat.readback=selected_readback()
    chat.head=accepted_head()
    return chat


def seed(chat, n, success=True):
    call={'name':'calculate','arguments':{'a':17,'b':11,'op':'add'}}
    chat.session.start_turn(permit_calls=True,fixture_for=call,fixture={'result':n} if success else {'error':'fixture unavailable'})
    return chat.session.propose(json.dumps(call),assistant_call_boundary=True)


def evaluate(patterns):
    claimed=correct=calls=0
    classes=set()
    passed=[]
    for q,expected,operand in POSITIVE:
        predicted,value=predict(patterns,q)
        if predicted is None or predicted=='defer':
            continue
        claimed+=1
        correct+=(predicted,value)==(expected,operand)
        classes.add(predicted)
        for prior in (-11, 28, 0.5):
            c=runtime(patterns)
            seed(c,prior)
            r=c.turn(q)
            op=expected.removeprefix('reverse_')
            a,b=(operand,prior) if expected.startswith('reverse_') else (prior,operand)
            event=r['trace'][0] if len(r['trace'])==1 else {}
            ok=event.get('ok') and event.get('arguments')==dict(op=op,a=a,b=b)
            passed.append(bool(ok and r['answer']==str(event['data']['result']).removesuffix('.0') and r['failure'] is None))
            calls+=1
    c=runtime(patterns)
    seed(c,28)
    r=c.turn('Now add 6 to that result.')
    passed.append(r['answer']=='34' and len(r['trace'])==1 and r['frame_origins'][0]=='learned-reference-pattern/typed-serialization')
    r=c.turn('Now add 6 to that result.',permit_calls=False)
    passed.append(not r['trace'] and r['selected_path']=='host/reference-abstention')
    r=c.turn('Divide the prior output by zero.')
    passed.append(len(r['trace'])==1 and r['trace'][0].get('error')=='division by zero' and r['answer']!='34')
    r=c.turn('Now add 6 to that result.')
    passed.append(not r['trace'] and r['selected_path']=='host/reference-abstention')
    c=runtime(patterns)
    seed(c,12,False)
    r=c.turn('Add 6 to that result.')
    passed.append(not r['trace'] and r['selected_path']=='host/reference-abstention')
    c=runtime(patterns)
    for n in range(4):
        seed(c,n)
    r=c.turn('Add 6 to that result.')
    passed.append(not r['trace'] and r['answer'] is None and 'quota' in r['failure'])
    c=runtime(patterns)
    seed(c,-48)
    r=c.turn('What result did the tool return?')
    passed.append(not r['trace'] and r['answer']=='-48' and r['selected_path']=='learned-readback/host-trace-render')
    return {'positive':len(POSITIVE),'claimed':claimed,'correct':correct,'covered_classes':sorted(classes),
            'negative':len(NEGATIVE),'negative_claims':sum(predict(patterns,q)[0] not in (None,'defer') for q in NEGATIVE),
            'actual_call_checks':calls,'runtime_checks':len(passed),'runtime_pass':sum(passed)}


def main():
    if (DIR/'result.json').exists():
        raise ValueError('First-use results already recorded')
    approved=DIR/'approved-teaching.jsonl'
    assert digest(approved)=='97643dc224a1dff5fabdf5b4f70160e661209e3b8ebd08ff9e4db9d3669fa090'
    assert digest(Path(__file__).with_name('reference_ops_holdout.py'))=='f3108e8df92c958dc0a5617e0e0f92cafdb9925fd2904160028d5fed49c56f61'
    assert digest(DIR/'protocol.json')=='3d0f7e1263114f53f7bb691bd7085fcbff80b630001df29620107795478fde33'
    rows=[json.loads(line) for line in approved.read_text().splitlines()]
    patterns=fit(rows)
    result=evaluate(patterns)
    spec=json.loads((DIR/'protocol.json').read_text())
    checks={'precision':result['claimed']>0 and result['correct']==result['claimed'],
            'coverage':result['correct']/result['positive']>=spec['fresh_supported_coverage_min'],
            'classes':len(result['covered_classes'])>=spec['minimum_op_classes'],
            'negatives':result['negative_claims']==0,'runtime':result['runtime_checks']==result['runtime_pass']}
    result.update(checks=checks,accepted=all(checks.values()),teaching_sha=digest(approved),
                  implementation={name:digest(Path(__file__).with_name(name)) for name in ('reference_ops_head.py','reference_ops_chat.py')})
    save(DIR/'weights.json',patterns)
    save(DIR/'result.json',result)
    if result['accepted']:
        save(DIR/'accepted-pin.json',{name:digest(DIR/name) for name in ('weights.json','result.json','protocol.json')})
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
