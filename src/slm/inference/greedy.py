"""Bounded raw-history greedy decoding; no teacher, retrieval, repair or tools."""
from contextlib import nullcontext
from pathlib import Path
import time
import numpy as np
from slm.common import checkpoint
from slm.common.tokenizer import BPE,STRUCTURAL,OFFSET
from slm.data.tokenized import sha
from slm.eval.portability import environment


def prompt_ids(tokenizer,messages):
    if not messages or messages[-1].get('role') not in ('user','tool'):
        raise ValueError('Generation needs a user/tool-ended conversation')
    # Serializer excludes its final EOS from x; append only the assistant role.
    ids,_,_=tokenizer.serialize(messages,objective='all')
    return ids+[STRUCTURAL['assistant']]


class GreedyModel:
    def __init__(self,model_path,tokenizer_path,backend='torch',device='cpu',*,expected_tokenizer_hash,
                 embedding_implementation='native-gather-v1'):
        if embedding_implementation not in ('native-gather-v1','dense-onehot-v1'):raise ValueError('Unknown embedding implementation')
        self.model_path=Path(model_path);self.tokenizer_path=Path(tokenizer_path)
        self.tokenizer_hash=sha(self.tokenizer_path/'manifest.json')
        if self.tokenizer_hash!=expected_tokenizer_hash:raise ValueError('Tokenizer binding differs')
        self.tokenizer=BPE.load(tokenizer_path);self.config,weights=checkpoint.load(model_path)
        if self.config.vocab_size!=self.tokenizer.vocab_size:raise ValueError('Model/tokenizer vocabulary differs')
        self.backend,self.device=backend,device;self.embedding_implementation=embedding_implementation
        if backend=='torch':
            import torch
            from slm.backends import torch_backend as impl
            self.array=lambda v:torch.tensor(v,device=device,dtype=torch.long)
            self.context=torch.no_grad
            self.argmax=lambda a:int(torch.argmax(a).item())
            self.finite=lambda a:bool(torch.isfinite(a).all().item())
        elif backend=='mlx':
            import mlx.core as mx
            from slm.backends import mlx_backend as impl
            self.array=mx.array;self.context=nullcontext
            self.argmax=lambda a:int(mx.argmax(a).item())
            self.finite=lambda a:bool(mx.all(mx.isfinite(a)).item())
        else:raise ValueError('Unknown backend')
        self.impl=impl;self.params=impl.load(self.config,weights,device) if backend=='torch' else impl.load(self.config,weights)
        self.identity={'model_manifest_sha256':sha(self.model_path/'manifest.json'),'tokenizer_manifest_sha256':self.tokenizer_hash,
            'architecture':self.config.to_dict(),'environment':environment(backend,device),'decoding':'raw-cached-greedy-v1',
            'backend_sha256':sha(Path(impl.__file__)),'embedding_implementation':embedding_implementation,'inference_sha256':sha(Path(__file__)),
            'binding_scope':'Explicit model-only/tokenizer pairing; vocabulary and supplied tokenizer hash checked, no inferred training provenance'}

    def generate(self,messages,max_new_tokens=64):
        if type(max_new_tokens) is not int or not 1<=max_new_tokens<=512:raise ValueError('Bounded generation budget required')
        ids=prompt_ids(self.tokenizer,messages)
        return self._generate_ids(ids,max_new_tokens)

    def _generate_ids(self,ids,max_new_tokens,allowed_controls=()):
        if type(max_new_tokens) is not int or not 1<=max_new_tokens<=512:raise ValueError('Bounded generation budget required')
        if len(ids)+max_new_tokens>self.config.max_seq_len:raise ValueError('Prompt plus generation budget exceeds context; no truncation')
        started=time.perf_counter();first=None;raw=[];content=[];reason='length';cache=None
        current=self.array([ids])
        with self.context():
            for _ in range(max_new_tokens):
                logits,cache,_=self.impl.forward(self.params,self.config,current,cache=cache,embedding_implementation=self.embedding_implementation)
                if not self.finite(logits[0,-1]):raise FloatingPointError('Nonfinite generation logits')
                token=self.argmax(logits[0,-1]);raw.append(token)
                if first is None:first=time.perf_counter()-started
                if token in (STRUCTURAL['message_end'],STRUCTURAL['eos']):
                    reason='message_end' if token==STRUCTURAL['message_end'] else 'eos';break
                if token<OFFSET and token not in allowed_controls:reason='invalid_structural';break
                if token>=OFFSET:content.append(token)
                current=self.array([[token]])
        text=self.tokenizer.decode(content);elapsed=time.perf_counter()-started
        return {'text':text,'token_ids':raw,'stop_reason':reason,'prompt_tokens':len(ids),'generated_tokens':len(raw),
            'content_tokens':len(content),'ttft_seconds':first,'seconds':elapsed,'max_new_tokens':max_new_tokens}

    def reference_loss(self,messages,reference):
        if not isinstance(reference,str) or not reference:raise ValueError('Nonempty reference required')
        x,y,mask=self.tokenizer.serialize([*messages,{'role':'assistant','content':reference}],max_length=self.config.max_seq_len)
        # Content-only targets: structural-token probability is not counted in bits/byte.
        final_start=len(prompt_ids(self.tokenizer,messages))-1
        mask=np.asarray(mask,dtype=np.float32)*(np.asarray(y)>=OFFSET)*(np.arange(len(y))>=final_start)
        count=int(mask.sum())
        if not count:raise ValueError('No reference content targets')
        with self.context():
            logits,_,_=self.impl.forward(self.params,self.config,self.array([x]),embedding_implementation=self.embedding_implementation)
            logits=self.impl.export({'logits':logits})['logits'][0]
        rows=logits[mask.astype(bool)].astype(np.float64)
        targets=np.asarray(y)[mask.astype(bool)]
        # Center on the target before FP64 log-sum-exp to avoid subtracting large logs.
        nll=np.logaddexp.reduce(rows-rows[np.arange(count),targets,None],axis=-1)
        value=float(nll.sum())
        if not np.isfinite(value):raise FloatingPointError('Nonfinite reference loss')
        return {'nll_sum':value,'content_targets':count,'utf8_bytes':len(reference.encode('utf-8')),
            'scope':'One supplied reference, teacher-forced content targets only; not free-generation task success'}
