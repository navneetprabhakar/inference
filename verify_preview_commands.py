"""Independent full-checkpoint before/after screen of explicit command handling."""
import json
import sys
import torch
from serve_chat import CPUGuard, load_student, resolve_weights, ROOT
from tokenizer import load

OUT=ROOT/'reports/explicit-commands'
# Preregister exact answers/trace counts or clarification keywords.
CASES=[
 ('direct add','Would you please add 12 and 7?',True,None,'19',1),
 ('direct subtract','Subtract 13 from 6, please.',True,None,'-7',1),
 ('direct divide','Calculate 18 / 4.',True,None,'4.5',1),
 ('direct multiply','Multiply -8 by 3.',True,None,'-24',1),
 ('valid conversion','Please convert 2.5 kilometers into meters.',True,None,'2500',1),
 ('word conversion','Convert eight hours to minutes.',True,None,'480',1),
 ('failed division','Calculate 8 / 0.',True,None,'division by zero',1),
 ('disabled arithmetic','Multiply 7 by 14.',False,None,'permit',0),
 ('disabled conversion','Convert 9 kilograms to grams.',False,None,'permit',0),
 ('incompatible units','Convert 14 seconds to kilograms.',True,None,'incompatible',0),
 ('unsupported unit','Convert 8 furlongs to meters.',True,None,'unsupported',0),
 ('wrong domain','Please convert 3 kilograms into seconds.',True,None,'incompatible',0),
 ('reference with suffix','Please subtract 5 from that result with the calculator.',True,23,'18',1),
 ('counterfactual prior','Divide the previous answer by 4 using the offline calculator.',True,-18,'-4.5',1),
 ('reference from error','Add 9 to that answer with the calculator.',True,'failure','no successful',0),
 ('reference disabled','Multiply the last output by four using the calculator.',False,51,'permit',0),
]
CONTROLS=['How does a calculator work?', 'What does it mean to convert an image?', 'Is twelve larger than five?',
          'My name is Rowan.', 'Tell me about unit testing.', 'What result did the tool return?',
          'Do not calculate 9 / 3.', 'If I multiplied seven by five, would the answer be even?',
          'Quote the phrase “convert 7 liters to grams”.']
def run(stage):
    from assistant_preview import Chat
    if stage=='before':
        from memory_chat import Chat as MemoryChat
        from reference_ops_chat import Chat as ReferenceChat
        class BaselineBackend(ReferenceChat):
            def __init__(self, model, tok, guard, reader=None):
                assert reader is None
                super().__init__(model,tok,guard)
        class Baseline(MemoryChat):
            backend_class=BaselineBackend
        Chat=Baseline
    elif stage!='after':
        raise ValueError('Choose before or after')
    torch.set_num_threads(1)
    pin=ROOT/'reports/working-chat/conversation-preview.json'
    w,sha=resolve_weights(None,None,pin)
    m=load_student(w,sha,'cpu')
    t=load()
    rows=[]
    for name,q,permit,prior,expected,n in CASES:
        c=Chat(m,t,CPUGuard())
        if prior is not None:
            proposal={'name':'calculate','arguments':{'a':2,'b':8,'op':'add'}}
            c.session.start_turn(permit_calls=True,fixture_for=proposal,fixture={'error':'offline'} if prior=='failure' else {'result':prior})
            c.session.propose(json.dumps(proposal),assistant_call_boundary=True)
        r=c.turn(q,permit_calls=permit)
        actual=r['answer'] or ''
        answer_ok=(expected.lower() in actual.lower() if any(ch.isalpha() for ch in expected) else expected==actual)
        rows.append(dict(name=name,user=q,correct=bool(answer_ok and len(r['trace'])==n and r['failure'] is None),
                         answer=actual,trace=r['trace'],failure=r['failure'],origins=r['frame_origins']))
    controls=[]
    for q in CONTROLS:
        c=Chat(m,t,CPUGuard())
        r=c.turn(q)
        controls.append(dict(user=q,trace=len(r['trace']),origins=r['frame_origins'],answer=r['answer'],failure=r['failure']))
    report=dict(stage=stage,checkpoint_sha=sha,correct=sum(row['correct'] for row in rows),total=len(rows),
                control_calls=sum(row['trace'] for row in controls),cases=rows,controls=controls)
    OUT.mkdir(exist_ok=True)
    (OUT/(stage+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    print(stage,report['correct'],'/',len(rows),'controls calls',report['control_calls'])
    print([(r['name'],r['answer']) for r in rows if not r['correct']])
    if stage=='after':
        assert report['correct']==len(rows) and report['control_calls']==0
        for r in rows:
            for event in r['trace']:
                assert event['source']=='offline fixture'
                assert event['ok'] or event['error']=='division by zero'
if __name__=='__main__':
    run(sys.argv[1])
