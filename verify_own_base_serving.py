"""CPU boundary check: strict own-base chat through the existing session API."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json

import serve_chat
from tokenizer import load, EOT


class Guard:
    def check(self):pass


class Model:
    def parameters(self):return []


def run():
    tok=load();args=SimpleNamespace(runtime='own-base',watch_pin=False,device='cpu')
    with patch('serve_chat.load_student',return_value=Model()):
        factory,info=serve_chat.build_runtime(args,Guard(),tok,Path('/fixture/own.pt'),'a'*64,{'status':'cpu fixture'})
    sessions=serve_chat.Sessions(factory,info)
    opened=sessions.open();token=opened['session'];chat=sessions.lookup(token).chat
    frames=iter([{'call':{'name':'calculate','arguments':{'op':'multiply','a':7,'b':6}}}, {'text':'42'}, {'text':'42'}])
    prefixes=[]
    def generate(prefix,budget):
        prefixes.append(list(prefix));assert budget==256
        return tok.encode(json.dumps(next(frames),separators=(',',':'))).ids+[EOT]
    chat.generate=generate
    first=sessions.turn(token,'t1','Multiply seven by six.',True)
    assert first['answer']=='42' and len(first['trace'])==1
    assert first['trace'][0]['source']=='offline fixture' and first['trace'][0]['data']['result']==42
    assert first['selected_path']=='gpt2/astra-dialogue-v1'
    # Idempotent HTTP/session turn IDs must not execute the tool twice.
    assert sessions.turn(token,'t1','Multiply seven by six.',True)==first
    assert len(chat.session.trace)==1
    second=sessions.turn(token,'t2','Recall that result without calling.',False)
    assert second['answer']=='42' and second['trace']==[] and len(prefixes)==3
    assert '"permit_calls":false' in chat.current_policy
    assert json.dumps(chat.current_policy)[1:-1] in tok.decode(prefixes[-1])
    assert 'Multiply seven by six.' in tok.decode(prefixes[-1])
    assert len(sessions.open(token)['turns'])==2
    assert serve_chat.RUNTIMES['raw']=='local_chat'
    print(json.dumps(dict(state='PASS',runtime='own-base',real_tool_calls=1,
                         tested='Session selection, actual arithmetic trace, full-history recall, changed policy and idempotent turn IDs',
                         model_loaded=False,gpu_operations=False,live_preview_changed=False)))


if __name__=='__main__':run()
