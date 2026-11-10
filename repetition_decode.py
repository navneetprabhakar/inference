"""Optional generated-token repetition penalty; never repairs text or tool calls."""
import math
import torch
from tokenizer import EOT

def validate_penalty(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<1:
        raise ValueError('repetition penalty must be finite and >=1')
    return float(value)

def penalize(logits, generated, penalty=1.):
    penalty=validate_penalty(penalty)
    if penalty==1 or not generated:return logits
    result=logits.clone()
    # Apply once per distinct generated token, not once per occurrence. Prompt
    # tokens are excluded so repeating a user-supplied entity is not penalized.
    ids=torch.tensor(sorted(set(generated)),device=logits.device,dtype=torch.long)
    values=result[ids]
    result[ids]=torch.where(values<0,values*penalty,values/penalty)
    return result

@torch.inference_mode()
def greedy(model,prefix,budget,guard,*,repetition_penalty=1.):
    penalty=validate_penalty(repetition_penalty)
    device=next(model.parameters()).device
    ids=list(prefix);output=[]
    for _ in range(budget):
        guard.check()
        logits=model(torch.tensor([ids],device=device))[0,-1]
        token=int(penalize(logits,output,penalty).argmax().item())
        output.append(token)
        if token==EOT:break
        ids.append(token)
    return output
