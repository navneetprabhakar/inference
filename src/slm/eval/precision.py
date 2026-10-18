"""CPU FP64 diagnostic oracle. No precision/tolerance change to production backends."""
import argparse
import json
from pathlib import Path
import math
import numpy as np
import torch
from safetensors.numpy import load_file
from slm.common.checkpoint import load
from slm.common.training import recipe_from_state
from slm.eval.portability import get_batches


def forward64(params, config, tokens):
    if any(p.dtype != torch.float64 for p in params.values()):
        raise ValueError('Oracle requires FP64 parameters')
    batch,length=tokens.shape
    x=params['embedding'][tokens]
    causal=torch.arange(length)[:,None]>=torch.arange(length)[None,:]
    angles=torch.arange(length,dtype=torch.float64)[:,None]*config.rope_theta**(
        -torch.arange(config.head_dim//2,dtype=torch.float64)/(config.head_dim//2))
    phase=torch.polar(torch.ones_like(angles),angles)[None,None]
    traces=[]
    def norm(values,weight):
        return values/torch.sqrt(values.square().sum(-1,keepdim=True)/config.hidden_size+config.norm_eps)*weight
    def rotate(values):
        pairs=torch.view_as_complex(values.contiguous().reshape(*values.shape[:-1],config.head_dim//2,2))
        return torch.view_as_real(pairs*phase).flatten(-2)
    head_map=torch.arange(config.num_heads)//(config.num_heads//config.num_kv_heads)
    for layer in range(config.num_layers):
        prefix=f'layers.{layer}.'
        h=norm(x,params[prefix+'attn_norm'])
        def project(name,heads):
            return (h@params[prefix+name].T).reshape(batch,length,heads,config.head_dim).permute(0,2,1,3)
        q=rotate(project('q',config.num_heads))
        k=rotate(project('k',config.num_kv_heads))[:,head_map]
        v=project('v',config.num_kv_heads)[:,head_map]
        scores=(q@k.transpose(-1,-2))/math.sqrt(config.head_dim)
        probs=torch.softmax(scores.masked_fill(~causal[None,None],-float('inf')),-1)
        attention=(probs@v).permute(0,2,1,3).reshape(batch,length,config.hidden_size)
        x=x+attention@params[prefix+'o'].T
        h=norm(x,params[prefix+'ffn_norm'])
        gate=h@params[prefix+'gate'].T
        x=x+(torch.nn.functional.silu(gate)*(h@params[prefix+'up'].T))@params[prefix+'down'].T
        traces.append(x)
    return norm(x,params['final_norm'])@params['embedding'].T,traces


def capture64(params, config, batch, optimizer):
    x,y,mask=batch
    x,y=torch.tensor(x),torch.tensor(y)
    mask=torch.tensor(mask,dtype=torch.float64)
    logits,layers=forward64(params,config,x)
    ce=torch.nn.functional.cross_entropy(logits.reshape(-1,config.vocab_size),y.flatten(),reduction='none').reshape(y.shape)
    loss=(ce*mask).sum()/mask.sum()
    grads=dict(zip(params,torch.autograd.grad(loss,tuple(params.values()))))
    tensors={'logits':logits,'loss':loss}
    tensors.update({f'layer:{i}':v for i,v in enumerate(layers)})
    tensors.update({f'gradient:{k}':v for k,v in grads.items()})
    tensors.update({f'weight:{k}':v for k,v in params.items()})
    for k,p in params.items():
        tensors[f'moment_m:{k}']=optimizer.state[p]['exp_avg']
        tensors[f'moment_v:{k}']=optimizer.state[p]['exp_avg_sq']
    return tensors


def errors_against_oracle(actual, reference):
    result={}
    for key,ref in reference.items():
        value=actual[key].astype(np.float64)
        oracle=ref.detach().numpy()
        difference=value-oracle
        result[key]={'max_abs_error':float(np.abs(difference).max()),
                     'relative_l2_error':float(np.linalg.norm(difference.ravel())/max(np.linalg.norm(oracle.ravel()),1e-30))}
        if key.startswith('gradient:'):
            signs=(value*oracle)<0
            result[key].update(sign_disagreements=int(signs.sum()),
                largest_oracle_magnitude_at_sign_disagreement=float(np.abs(oracle[signs]).max()) if signs.any() else 0.)
    return result


def diagnose(bundle,cpu_probe,output):
    bundle,output=Path(bundle),Path(output)
    if output.exists():raise FileExistsError(output)
    config,weights=load(bundle/'initial/model')
    state=json.loads((bundle/'initial/state.json').read_text())
    recipe=recipe_from_state(state)
    params={k:torch.tensor(v,dtype=torch.float64,requires_grad=True) for k,v in weights.items()}
    del weights
    groups=[{'params':[p for k,p in params.items() if p.ndim==2 and k!='embedding'],'weight_decay':recipe.decay},
            {'params':[p for k,p in params.items() if p.ndim!=2 or k=='embedding'],'weight_decay':0.}]
    opt=torch.optim.AdamW(groups,lr=recipe.lr,betas=(recipe.beta1,recipe.beta2),eps=recipe.eps,foreach=False,fused=False)
    raw=load_file(str(bundle/'initial/optimizer.safetensors'))
    for k,p in params.items():
        opt.state[p].update(step=torch.tensor(float(state['step'])),
            exp_avg=torch.tensor(raw['m:'+k],dtype=torch.float64),exp_avg_sq=torch.tensor(raw['v:'+k],dtype=torch.float64))
    del raw
    batches=get_batches(bundle)
    reference=capture64(params,config,batches.items[0],opt)
    report={'purpose':'diagnostic, not an acceptance policy','parameters':config.parameter_count,
        'oracle':'Independent FP64 complex-RoPE forward, native CE and native AdamW; gradients and state projected to FP32 at update boundaries',
        'at_start':errors_against_oracle(load_file(str(bundle/'expected-2.safetensors')),reference)}
    del reference
    for index in (2,3):
        x,y,mask=batches.items[index]
        logits,_=forward64(params,config,torch.tensor(x))
        losses=torch.nn.functional.cross_entropy(logits.reshape(-1,config.vocab_size),torch.tensor(y).flatten(),reduction='none')
        mask64=torch.tensor(mask,dtype=torch.float64).flatten()
        loss=(losses*mask64).sum()/mask64.sum()
        gradients=torch.autograd.grad(loss,tuple(params.values()))
        for p,g in zip(params.values(),gradients):p.grad=g.float().double()
        torch.nn.utils.clip_grad_norm_(list(params.values()),recipe.clip)
        rate=recipe.rate(batches.counts(index+1)[0])
        for group in opt.param_groups:group['lr']=rate
        opt.step();opt.zero_grad(set_to_none=True)
        with torch.no_grad():
            for p in params.values():
                p.copy_(p.float().double())
                for slot in ('exp_avg','exp_avg_sq'):opt.state[p][slot]=opt.state[p][slot].float().double()
        del logits,losses,loss,gradients
    reference=capture64(params,config,batches.items[0],opt)
    report['mlx_after_two_updates']=errors_against_oracle(load_file(str(bundle/'expected-4.safetensors')),reference)
    report['cpu_after_two_updates']=errors_against_oracle(load_file(str(cpu_probe)),reference)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    for stage in ('at_start','mlx_after_two_updates','cpu_after_two_updates'):
        worst={}
        for name,m in report[stage].items():
            key=name.split(':')[0]
            worst[key]=max(worst.get(key,0.),m['max_abs_error'])
        print(stage,worst)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',required=True);p.add_argument('--cpu-probe',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();diagnose(a.bundle,a.cpu_probe,a.output)


if __name__=='__main__':main()
