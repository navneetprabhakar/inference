"""GPT-2 with a learned causal token-copy distribution for grounded generation."""
import math

import torch
from torch import nn
from torch.nn import functional as F

from gpt2 import Config, GPT2


class CopyGPT2(GPT2):
    def __init__(self,config=Config(),copy_width=64,aliases=None):
        super().__init__(config)
        self.copy_query=nn.Linear(config.width,copy_width,bias=False)
        self.copy_key=nn.Linear(config.width,copy_width,bias=False)
        self.copy_gate=nn.Linear(config.width,1)
        self.copy_surface=nn.Linear(config.width,1)
        if aliases is None:
            aliases=list(range(config.vocabulary))
            if config.vocabulary==50257:
                from tokenizer import EOT, load
                vocabulary=load().get_vocab()
                for piece,idx in vocabulary.items():
                    if idx!=EOT:
                        other=piece[1:] if piece.startswith("Ġ") else "Ġ"+piece
                        aliases[idx]=vocabulary.get(other,idx)
        if len(aliases)!=config.vocabulary or any(i<0 or i>=config.vocabulary for i in aliases):
            raise ValueError("invalid copy token alias")
        # This deterministic table is reconstructed from the pinned tokenizer, including
        # for meta-device inference loaders; it isn't a learned parameter.
        self.register_buffer("aliases",torch.tensor(aliases,dtype=torch.long,device="cpu"),persistent=False)
        self.copy_scale=1/math.sqrt(copy_width)
        nn.init.normal_(self.copy_query.weight,std=.02)
        nn.init.normal_(self.copy_key.weight,std=.02)
        nn.init.zeros_(self.copy_gate.weight)
        nn.init.constant_(self.copy_gate.bias,-2.)
        nn.init.zeros_(self.copy_surface.weight)
        nn.init.constant_(self.copy_surface.bias,-1.)

    def hidden(self,ids):
        length=ids.shape[1]
        if not 0<length<=self.positions.num_embeddings:
            raise ValueError("sequence length is outside the model context")
        h=self.tokens(ids)+self.positions(torch.arange(length,device=ids.device))
        for block in self.blocks:
            h=block(h)
        return self.final_norm(h)

    def components(self,ids,positions,last_only=False):
        h=self.hidden(ids)
        batch,time=positions.unbind(1)
        query=h[batch,time]
        keys=self.copy_key(h).transpose(1,2)
        if last_only:
            attention=torch.bmm(self.copy_query(query)[:,None],keys)[:,0]
        else:
            # Multiplying once per sequence avoids repeating the entire key
            # matrix for every supervised token in the same conversation.
            attention=torch.bmm(self.copy_query(h),keys)[batch,time]
        attention=attention*self.copy_scale
        future=torch.arange(ids.shape[1],device=ids.device)[None,:]>time[:,None]
        attention=attention.masked_fill(future,-torch.inf).softmax(-1)
        return F.linear(query,self.tokens.weight),attention,self.copy_gate(query)[:,0],self.copy_surface(query).sigmoid(),ids[batch]

    def supervised(self,ids,labels):
        positions=(labels!=-100).nonzero()
        if not len(positions):
            raise ValueError("empty supervision")
        batch,time=positions.unbind(1)
        target=labels[batch,time]
        logits,attn,gate,surface,source=self.components(ids,positions)
        vocab=F.log_softmax(logits,-1).gather(1,target[:,None])[:,0]
        exact=(attn*(source==target[:,None])).sum(-1)
        alternate=(attn*(self.aliases[source]==target[:,None])).sum(-1)
        copy=(1-surface[:,0])*exact+surface[:,0]*alternate
        scores=torch.logaddexp(F.logsigmoid(-gate)+vocab,F.logsigmoid(gate)+copy.clamp_min(1e-20).log())
        return scores,target,batch

    def next_logits(self,ids):
        batch=torch.arange(len(ids),device=ids.device)
        positions=torch.stack([batch,torch.full_like(batch,ids.shape[1]-1)],dim=1)
        logits,attn,gate,surface,source=self.components(ids,positions,last_only=True)
        probabilities=F.softmax(logits,-1)*torch.sigmoid(-gate[:,None])
        mass=attn*torch.sigmoid(gate[:,None])
        copied=torch.zeros_like(probabilities).scatter_add(1,source,mass*(1-surface))
        copied=copied.scatter_add(1,self.aliases[source],mass*surface)
        return (probabilities+copied).clamp_min(1e-20).log()

    def forward(self,ids,prediction_mask=None):
        if prediction_mask is None:
            mask=torch.ones_like(ids,dtype=torch.bool)
        else:
            mask=prediction_mask
        logits,attn,gate,surface,source=self.components(ids,mask.nonzero())
        probabilities=F.softmax(logits,-1)*torch.sigmoid(-gate[:,None])
        mass=attn*torch.sigmoid(gate[:,None])
        copied=torch.zeros_like(probabilities).scatter_add(1,source,mass*(1-surface))
        copied=copied.scatter_add(1,self.aliases[source],mass*surface)
        output=(probabilities+copied).clamp_min(1e-20).log()
        return output.view(*ids.shape,-1) if prediction_mask is None else output


def verify():
    torch.manual_seed(31)
    model=CopyGPT2(Config(vocabulary=37,width=24,heads=3,depth=2,context=32),copy_width=8,aliases=[(i+1)%37 for i in range(37)])
    ids=torch.tensor([[3,7,9,5,2],[8,12,3,2,2]])
    labels=torch.tensor([[-100,9,-100,4,3],[-100,3,17,2,-100]])
    out=model(ids)
    torch.testing.assert_close(out.exp().sum(-1),torch.ones_like(ids,dtype=torch.float))
    scores,target,_=model.supervised(ids,labels)
    ref=out[labels!=-100].gather(1,target[:,None])[:,0]
    torch.testing.assert_close(scores,ref)
    torch.testing.assert_close(model.next_logits(ids),out[:,-1])
    other=ids.clone()
    other[:,3:]=11
    torch.testing.assert_close(out[:,:3],model(other)[:,:3],rtol=1e-4,atol=1e-6)
    loss=-scores.mean()
    loss.backward()
    for name,param in model.named_parameters():
        assert param.grad is not None and torch.isfinite(param.grad).all(),name
    print("Copy distribution normalization, causal prefix, supervised likelihood and gradients verified.")


if __name__=="__main__":
    verify()
