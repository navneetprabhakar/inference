"""CPU synthetic chat wiring checks using the real offline broker and tokenizer.

No checkpoints, private cases or GPU. Scripted frames test plumbing, not a
model's conversational or tool-selection capability.
"""
from copy import deepcopy
import json
from unittest.mock import patch

import torch

from dialogue import assistant_prompt,training_row
from guards import ResourceStop
from own_base_chat import Chat,policy_text,stable_tool_record
from tokenizer import EOT,load
from tools import FixtureSession


class Guard:
    def __init__(self):self.checks=0
    def check(self):self.checks+=1


class Script:
    def __init__(self,tok,steps):self.tok=tok;self.steps=iter(steps);self.prefixes=[]
    def __call__(self,prefix,budget):
        assert budget==256
        self.prefixes.append(list(prefix))
        value=next(self.steps)
        if callable(value):value=value(self.tok.decode(prefix))
        if isinstance(value,list):return value
        raw=value if isinstance(value,str) else json.dumps(value,sort_keys=True,separators=(',',':'))
        return self.tok.encode(raw).ids+[EOT]


def calculate(a,b,op='add'):return {'call':{'name':'calculate','arguments':dict(op=op,a=a,b=b)}}


def chat(tok,steps):
    script=Script(tok,steps)
    return Chat(None,tok,Guard(),generate=script),script


def run():
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    tok=load();checks=[]
    def check_observation(text):
        assert '"result":56' in text and '"call_id":"c1"' in text
        assert 'timestamp' not in text
        return {'text':'56'}
    c,g=chat(tok,[calculate(7,8,'multiply'),check_observation,calculate(56,3),{'text':'59'}])
    first=c.turn('Multiply7 and8.');assert first['answer']=='56' and first['failure'] is None
    assert first['trace'][0]['data']['result']==56 and 'timestamp' in first['trace'][0]
    assert c.history[1]['call_id']=='c1' and c.history[2]['record']['call_id']=='c1'
    assert c.history[2]['record']['source']=='offline fixture'
    assert 'timestamp' not in c.history[2]['record']
    # Teacher row uses the exact same assistant prefixes as this runtime.
    full=c.prompt_history();row=training_row(tok,full)
    assert row.inputs[:len(g.prefixes[0])]==g.prefixes[0]
    assert assistant_prompt(tok,full[:-1],reply_budget=256)==g.prefixes[1]
    assert c.current_policy==policy_text(True)
    second=c.turn('Add3 to that observed value.')
    assert second['answer']=='59' and second['trace'][0]['data']['result']==59
    assert second['trace'][0]['call_id']=='c2' and len(c.session.trace)==2
    assert c.current_policy==policy_text(True);checks.append('real arithmetic, follow-up, binding and SFT prefix')
    # The returned trace is detached from the broker's authoritative history.
    first['trace'][0]['data']['result']=999
    assert c.session.trace[0]['data']['result']==56
    projected=stable_tool_record(c.session.trace[0]);projected['data']['result']=998
    assert c.session.trace[0]['data']['result']==56;checks.append('trace projection preserves authoritative records')
    def error_readback(text):
        assert 'division by zero' in text
        return {'text':'The tool reported division by zero.'}
    c,g=chat(tok,[calculate(3,0,'divide'),error_readback]);result=c.turn('Divide3 by0.')
    assert result['answer']=='The tool reported division by zero.' and result['failure'] is None
    assert result['trace'][0]['ok'] is False and c.session.decisions[0]['dispatched'] is True
    checks.append('real adapter error reaches model')
    c,g=chat(tok,[calculate(2,3),{'text':'Tools are disabled.'}]);result=c.turn('Please calculate.',permit_calls=False)
    assert result['answer']=='Tools are disabled.' and not result['trace'][0]['ok']
    assert c.session.decisions[0]['dispatched'] is False
    assert c.current_policy==policy_text(False);checks.append('disabled tools never dispatch')
    c,g=chat(tok,[{'call':{'name':'convert','arguments':{'value':1,'from':'km','to':'m'}}},{'text':'1000'}])
    result=c.turn('Convert1km to metres.',allowed_names=['convert'])
    assert result['answer']=='1000' and result['trace'][0]['data']['result']==1000
    assert c.current_policy==policy_text(True,['convert']);checks.append('scoped real unit conversion')
    c,g=chat(tok,[calculate(1,2),{'text':'Unavailable.'}]);result=c.turn('Calculate.',allowed_names=['convert'])
    assert c.session.decisions[0]['dispatched'] is False and result['answer']=='Unavailable.'
    checks.append('allowed-name scope enforced')
    c,g=chat(tok,[{'text':'First.'},{'text':'Second.'}]);c.turn('A',permit_calls=True);c.turn('B',permit_calls=False)
    assert c.turn_records[0]['policy']==policy_text(True) and c.turn_records[1]['policy']==policy_text(False)
    first_system=json.loads(tok.decode(g.prefixes[1]).split('[system]\n',1)[1].split('<|endoftext|>',1)[0])
    assert first_system['text']==policy_text(False)
    checks.append('current policy rebuilt without rewriting prior conversation frames')
    c,g=chat(tok,[{'text':'I will answer directly.'}]);c.turn('Do not use any tools.',permit_calls=True)
    assert c.session.permit_calls is True;checks.append('user text does not mutate host policy')
    c,g=chat(tok,[calculate(7,8,'multiply'),{'text':'The fixture reported6.'}])
    result=c.turn('Use recorded fixture.',fixture_for=calculate(7,8,'multiply')['call'],fixture={'result':6})
    assert result['trace'][0]['source']=='synthetic recorded fixture' and result['trace'][0]['data']['result']==6
    assert result['answer']=='The fixture reported6.';checks.append('explicit counterfactual fixture is labeled and observed')
    malformed=['{"text":"one","text":"two"}','{"text":"x","call":{"name":"calculate","arguments":{}}}',
               '{not-json}',tok.encode('{"text":"unfinished"}').ids,
               tok.encode('{"text":"one"}').ids+[EOT]+tok.encode('{"text":"two"}').ids+[EOT],
               [0]*257,[EOT+1,EOT]]
    for value in malformed:
        c,g=chat(tok,[value,{'text':'Must never be generated'}]);result=c.turn('Hi')
        assert result['answer'] is None and result['failure'] and not result['trace']
        again=c.turn('Retry');assert again['answer'] is None and again['failure'] and len(g.prefixes)==1
        assert not any(m['role']=='assistant' for m in c.history)
    checks.append('seven malformed/capped frames halt without invented assistant answers')
    c,g=chat(tok,[calculate(1,2),{'text':'Must never be generated'}]);real=c.session.propose
    def bad_binding(*args,**kwargs):
        record=real(*args,**kwargs);record['call_id']='wrong-id';return record
    with patch.object(c.session,'propose',side_effect=bad_binding):result=c.turn('Compute.')
    assert result['answer'] is None and 'binding' in result['failure']
    assert result['trace'][0]['call_id']=='c1' and result['trace'][0]['data']['result']==3 and len(g.prefixes)==1
    checks.append('wrong return binding halts while preserving actual execution trace')
    c,g=chat(tok,[{'text':'Must not run'}]);result=c.turn('x '*2000)
    assert result['answer'] is None and result['failure'] and not g.prefixes and not result['trace']
    assert c.history[0]['text']=='x '*2000;checks.append('initial context overflow preserves complete pending user')
    # Fill to the initial reserved-reply boundary, then observe a real call.
    size=1
    while True:
        try:assistant_prompt(tok,[{'role':'system','text':policy_text(True)},{'role':'user','text':'x '*size}],reply_budget=256)
        except ValueError:break
        size+=1
    c,g=chat(tok,[calculate(1,2),{'text':'Must not run'}]);result=c.turn('x '*(size-1))
    assert result['answer'] is None and result['failure'] and len(result['trace'])==1 and len(g.prefixes)==1
    assert c.history[-1]['role']=='tool' and c.history[-1]['record']['data']['result']==3
    checks.append('post-tool context overflow keeps real tool trace without synthetic closure')
    c,g=chat(tok,[calculate(1,1),calculate(2,1),calculate(3,1)]);result=c.turn('A')
    assert result['answer'] is None and 'quota' in result['failure'] and len(result['trace'])==2
    checks.append('two-call turn quota')
    c,g=chat(tok,[calculate(1,1),calculate(2,1),{'text':'3'},calculate(1,1),calculate(2,1),{'text':'3'},calculate(1,1)])
    one=c.turn('A');two=c.turn('B');three=c.turn('C')
    assert one['failure'] is None and two['failure'] is None,(one,two)
    assert three['answer'] is None and 'quota' in three['failure'] and len(c.session.trace)==4
    checks.append('four-call session quota')
    c,g=chat(tok,[calculate(7,8,'multiply'),calculate(56,3),
                 {'text':'The tool returned 59 after adding three to the first result.'},
                 calculate(59,4,'subtract'),calculate(55,5,'divide'),
                 {'text':'The tool returned 11 after the subtraction and division.'}])
    first=c.turn('Multiply seven by eight, then add three to the result. Please use the calculator for both steps.')
    second=c.turn('Now subtract four from that result, then divide the new amount by five. Again, use the calculator.')
    assert first['failure'] is None and second['failure'] is None
    assert len(c.session.trace)==4 and c.session.trace[-1]['data']['result']==11
    assert all(len(prefix)+256<=1024 for prefix in g.prefixes)
    checks.append('four executed dependent calls with complete natural-language history fit the frozen context')
    # Infrastructure faults after real execution propagate unchanged, with
    # authoritative trace retained by finally and no fabricated closure.
    for error in (ResourceStop('synthetic guard stop'),RuntimeError('synthetic decoder OOM'),
                  MemoryError('synthetic allocation failure')):
        def fail(_prefix,exception=error):raise exception
        c,g=chat(tok,[calculate(7,8,'multiply'),fail])
        if isinstance(error,ResourceStop):
            class StopAfterExecution(Guard):
                def check(self):
                    super().check()
                    if self.checks==3:raise error
            c.guard=StopAfterExecution()
        try:c.turn('Multiply seven by eight.')
        except type(error) as caught:assert caught is error
        else:raise AssertionError('infrastructure failure was swallowed')
        saved=c.turn_records[-1]['result']
        assert saved['failure_kind']=='infrastructure' and saved['answer'] is None
        assert saved['trace']==c.session.trace and saved['trace'][0]['data']['result']==56
        assert len(c.history)==3 and c.history[-1]['role']=='tool'
        before=len(g.prefixes)
        assert c.turn('Continue')['failure_kind']=='closed_session' and len(g.prefixes)==before
    checks.append('guard stop, decoder RuntimeError and MemoryError propagate with real trace and closed history')
    # Default route really invokes token-by-token decoder on an injected CPU model.
    answer_ids=tok.encode('{"text":"Decoder path."}').ids+[EOT]
    class DecoderStub(torch.nn.Module):
        def __init__(self):super().__init__();self.weight=torch.nn.Parameter(torch.zeros(1));self.index=0
        def forward(self,row):
            scores=torch.full((1,row.shape[1],EOT+1),-100.,device='cpu')
            scores[0,-1,answer_ids[self.index]]=100.;self.index+=1;return scores
    model=DecoderStub();guard=Guard();c=Chat(model,tok,guard);result=c.turn('Hi')
    assert result['answer']=='Decoder path.' and model.index==len(answer_ids) and guard.checks>=len(answer_ids)
    checks.append('default actual greedy decoder path, synthetic CPU logits only')
    print(json.dumps(dict(state='passed',checks=checks,model_quality_claim=False,gpu_operations=False,
                         model_checkpoint_loaded=False,live_preview_changed=False),indent=2))

if __name__=='__main__':run()
