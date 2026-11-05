import sys
from pathlib import Path
import numpy as np
from tokenizers import Tokenizer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from goal_plain_roles import render,encode_episode,EOS
ROOT=Path(__file__).resolve().parents[1]

def test_readable_roles_exact_prompt_prefix_and_assistant_only_targets():
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'))
    messages=[{'role':'user','content':'My name is Návneet. What is 3 plus 4?'},{'role':'assistant','content':'7.'},{'role':'user','content':'Repeat it.'},{'role':'assistant','content':'7.'}]
    ids,mask,n=encode_episode(tok,messages);encoded=tok.encode(render(messages))
    assert ids[:n].tolist()==encoded.ids
    assert not any(x in {2,3,4,6} for x in ids[:n])
    assert sum(ids[i]==1 and mask[i-1]==1 for i in range(1,n))==2
    for i,m in enumerate(messages):
        if m['role']=='assistant':
            prefix=tok.encode(render(messages[:i],True)).ids
            assert ids[:len(prefix)].tolist()==prefix
            assert mask[len(prefix)-1]==1
    assert np.count_nonzero(mask[n-1:])==0

def test_tool_call_marker_is_retained_but_tool_result_is_not_supervised():
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'))
    messages=[{'role':'user','content':'Add.'},{'role':'assistant','content':'<|tool_call|>{"name":"calculate","arguments":{"op":"add","a":1,"b":2}}'},{'role':'tool','content':'{"result":3}'},{'role':'assistant','content':'3.'}]
    ids,mask,n=encode_episode(tok,messages)
    assert 5 in ids[:n]
    start=len(tok.encode(render(messages[:2])+'Tool result:\n').ids)
    end=len(tok.encode(render(messages[:3])).ids)
    assert not mask[start-1:end-1].any()

def test_context_overflow_is_rejected():
    tok=Tokenizer.from_file(str(ROOT/'data/sft-v3/tokenizer.json'))
    assert encode_episode(tok,[{'role':'user','content':'word '*1000},{'role':'assistant','content':'Answer.'}]) is None
