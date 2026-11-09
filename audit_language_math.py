"""CPU-only independent attention/loss checks; never loads production weights."""
import copy
import hashlib
import json
import math
from pathlib import Path
import signal
import time

import torch
from torch.nn import functional as F
from gpt2 import Config, GPT2, next_token_loss

ROOT=Path(__file__).resolve().parent


def reference(model, ids):
    # Separate head slicing and explicit triangular masking, no SDPA call.
    hidden=model.tokens(ids)+model.positions(torch.arange(ids.shape[1]))
    for block in model.blocks:
        q,k,v=F.linear(block.before_attention(hidden),block.qkv.weight,block.qkv.bias).chunk(3,dim=-1)
        head_width=q.shape[-1]//block.heads
        pieces=[]
        for h in range(block.heads):
            sl=slice(h*head_width,(h+1)*head_width)
            scores=q[:,:,sl]@k[:,:,sl].transpose(-2,-1)/math.sqrt(head_width)
            future=torch.ones(ids.shape[1],ids.shape[1],dtype=torch.bool).triu(1)
            probabilities=scores.masked_fill(future,float('-inf')).softmax(-1)
            pieces.append(probabilities@v[:,:,sl])
        hidden=hidden+block.attention_out(torch.cat(pieces,dim=-1))
        hidden=hidden+block.mlp(block.before_mlp(hidden))
    return F.linear(model.final_norm(hidden),model.tokens.weight)


def main():
    started=time.monotonic()
    def deadline(*_):raise TimeoutError('120-second math audit ceiling')
    signal.signal(signal.SIGALRM,deadline);signal.alarm(120)
    assert not (ROOT/'runs/STOP').exists()
    torch.set_num_threads(1);torch.manual_seed(20261109)
    config=Config(vocabulary=37,context=32,width=24,heads=3,depth=2)
    model=GPT2(config).double().eval();other=copy.deepcopy(model)
    ids=torch.randint(0,37,(4,13));x,y=ids[:,:-1],ids[:,1:]
    actual=model(x);expected=reference(other,x)
    torch.testing.assert_close(actual,expected,atol=1e-11,rtol=1e-10)
    loss=next_token_loss(model,ids)
    manual=-expected.log_softmax(-1).gather(-1,y.unsqueeze(-1)).mean()
    torch.testing.assert_close(loss,manual,atol=1e-11,rtol=1e-10)
    loss.backward();manual.backward()
    gradient_error=0.
    for a,b in zip(model.parameters(),other.parameters()):
        torch.testing.assert_close(a.grad,b.grad,atol=1e-10,rtol=1e-9)
        gradient_error=max(gradient_error,float((a.grad-b.grad).abs().max()))
    changed=x.clone();changed[:,6:]=(changed[:,6:]+1)%37
    with torch.no_grad():
        future_error=float((model(changed)[:,:6]-actual[:,:6]).abs().max())
        assert future_error<1e-11
        prefix_error=max(float((model(x[:,:t+1])[:,-1]-actual[:,t]).abs().max()) for t in range(x.shape[1]))
        assert prefix_error<1e-11
        altered=x.clone();altered[:,0]=(altered[:,0]+1)%37
        context_effect=float((model(altered)[:,-1]-actual[:,-1]).abs().max())
        assert context_effect>1e-8
        mask=torch.zeros_like(x,dtype=torch.bool);mask[:,5:]=True
        torch.testing.assert_close(model(x,prediction_mask=mask),actual[mask],atol=1e-11,rtol=1e-10)
    accumulated=copy.deepcopy(model);accumulated.zero_grad(set_to_none=True)
    for row in ids:
        logits=accumulated(row[None,:-1])
        (F.cross_entropy(logits.flatten(0,1),row[1:],reduction='sum')/y.numel()).backward()
    for a,b in zip(model.parameters(),accumulated.parameters()):
        torch.testing.assert_close(a.grad,b.grad,atol=1e-10,rtol=1e-9)
    result=dict(state='PASS_cpu_reference_math_not_model_quality',production_weights_loaded=False,
                checks=['Explicit per-head attention forward equivalence','Full-model parameter-gradient equivalence','Shifted next-token CE equals manual gathered log probabilities','Future suffix cannot affect earlier logits','Each full-sequence position equals separate prefix inference','Earlier context changes final-position logits','Masked projection equals unmasked positions','Microbatch accumulation equals full-batch normalized gradients'],
                max_forward_error=float((actual-expected).abs().max().detach()),max_gradient_error=gradient_error,
                future_leak_error=future_error,prefix_inference_error=prefix_error,random_model_context_effect=context_effect,
                seconds=time.monotonic()-started,
                code_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in ['gpt2.py','audit_language_math.py','own_base_language_continue.py','base_train.py']},
                limitations=['Tiny random CPU FP64 fixture, not a trained-checkpoint or MPS/BF16 correctness proof.','Passing arithmetic checks does not establish learned context use or conversational capability.'])
    out=ROOT/'reports/post-25m-correctness-audit-v1';out.mkdir(exist_ok=True)
    with (out/'cpu-math.json').open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    signal.alarm(0);print(json.dumps(result))


if __name__=='__main__':main()
