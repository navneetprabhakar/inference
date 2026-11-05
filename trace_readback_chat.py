"""Opt-in CPU readback mode over the verified v2 tool pipeline."""
import json
from functools import lru_cache
from pathlib import Path

from fallback_head import Decision
from fallback_chat import Reply
from followon_product_chat import Chat as V2Chat
from local_chat import encode_frame
from trace_readback_curriculum import DIR
from trace_readback_head import Head, digest, render


@lru_cache(maxsize=1)
def selected_readback():
    pin = json.loads((DIR/'accepted-pin.json').read_text())
    if set(pin['files']) != {'result.json', 'protocol.json', 'weights.json'}:
        raise ValueError('Incomplete readback acceptance receipt')
    for filename, expected in pin['files'].items():
        if digest(DIR/filename)!=expected:
            raise ValueError('Readback evidence or weights changed')
    report = json.loads((DIR/'result.json').read_text())
    if digest(Path(__file__).with_name('trace_readback_head.py')) != report['classifier_sha']:
        raise ValueError('Readback classifier source differs from evaluated source')
    if not report['accepted'] or not all(report['checks'].values()):
        raise ValueError('Readback head failed its acceptance gate')
    return Head(json.loads((DIR/'weights.json').read_text()))


class Chat(V2Chat):
    def __init__(self,model,tok,guard,reader=None):
        super().__init__(model,tok,guard,reader=reader)
        self.readback = selected_readback()
        self.readback_answer = None

    def decide(self,user,phase=0):
        self.readback_answer = None
        trace = self.session.trace
        if phase==0 and trace:
            label = self.readback.decide(user)
            answer = render(label,trace[-1],user)
            if answer is not None:
                self.readback_answer = answer
                return Decision('trace_readback/'+label,None,0.,{})
        return super().decide(user,phase)

    def respond_ordinary(self,user,history_ids):
        if self.readback_answer is None:
            return super().respond_ordinary(user,history_ids)
        answer = self.readback_answer
        self.readback_answer = None
        prefix,body = encode_frame(self.tok,'assistant',{'text':answer})
        return Reply(json.dumps({'text':answer}),answer,None,prefix+body,
                     'learned-readback/host-trace-render')
