"""Opt-in referenced arithmetic and conservative abstention over the readback product."""
from functools import lru_cache
from pathlib import Path
import json

from fallback_chat import Reply
from fallback_head import Decision
from local_chat import encode_frame
from reference_ops_curriculum import DIR
from reference_ops_head import REFERENCE, encode, predict
from trace_readback_chat import Chat as ReadbackChat
from trace_readback_head import digest
from tools import validate_arguments


@lru_cache(maxsize=1)
def accepted_patterns():
    pin=json.loads((DIR/'accepted-pin.json').read_text())
    if set(pin)!= {'weights.json','protocol.json','result.json'}:
        raise ValueError('Incomplete reference-operation acceptance receipt')
    for name, expected in pin.items():
        if digest(DIR/name)!=expected:
            raise ValueError('Reference-operation artifact checksum mismatch')
    report=json.loads((DIR/'result.json').read_text())
    if not report['accepted'] or not all(report['checks'].values()):
        raise ValueError('Reference-operation gate failed')
    for name, expected in report['implementation'].items():
        if digest(Path(__file__).with_name(name))!=expected:
            raise ValueError('Reference-operation implementation differs from evaluated code')
    return json.loads((DIR/'weights.json').read_text())


class Chat(ReadbackChat):
    def __init__(self, model,tok,guard):
        super().__init__(model,tok,guard)
        self.patterns=accepted_patterns()
        self.reference_call=False
        self.reference_notice=None

    def stop_reference(self,message):
        self.reference_notice=message
        return Decision('reference_abstain',None,0.,{},'reference-ops/host-abstention')

    def decide(self,user,phase=0):
        if phase:
            if self.reference_call:
                return Decision('done',None,0.,{},'reference-ops/one-call-complete')
            return super().decide(user,phase)
        self.reference_call=False
        self.reference_notice=None
        self.readback_answer=None
        trace=self.session.trace
        action,operand=predict(self.patterns,user)
        if action and action!='defer':
            if not self.session.permit_calls:
                return self.stop_reference('This turn does not permit a new calculation.')
            if not trace or not trace[-1]['ok']:
                return self.stop_reference('There is no successful result from the latest call to use.')
            prior=trace[-1]['data']['result']
            reverse=action.startswith('reverse_')
            args={'op':action.removeprefix('reverse_'),'a':operand if reverse else prior,
                  'b':prior if reverse else operand}
            try:
                validate_arguments('calculate',args)
            except ValueError:
                return self.stop_reference('The requested calculation is outside the supported numeric range.')
            self.reference_call=True
            return Decision(action,{'name':'calculate','arguments':args},0.,{},
                            'learned-reference-pattern/observed-result-and-explicit-operand')
        decision=super().decide(user,phase)
        if decision.action.startswith('trace_readback/'):
            return decision
        # A prior result can only be echoed after positive readback classification.
        if decision.action=='recall_number':
            return self.stop_reference('Please clarify whether to repeat the result or perform a new calculation.')
        if trace and REFERENCE.search(user) and encode(user)[0] is not None:
            return self.stop_reference('Please clarify the calculation or comparison you want.')
        return decision

    def respond_ordinary(self,user,history_ids):
        if self.reference_notice is None:
            return super().respond_ordinary(user,history_ids)
        answer=self.reference_notice
        prefix,body=encode_frame(self.tok,'assistant',{'text':answer})
        return Reply(json.dumps({'text':answer}),answer,None,prefix+body,'host/reference-abstention')

    def turn(self,*args,**kwargs):
        result=super().turn(*args,**kwargs)
        if self.history and self.reference_call and result['trace'] and result['frame_origins']:
            result['frame_origins'][0]='learned-reference-pattern/typed-serialization'
        return result
