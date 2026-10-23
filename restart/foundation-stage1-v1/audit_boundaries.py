"""Read-only replay of every frozen story to retain hidden document markers.
Original outputs/scores remain untouched. Replays must reproduce decoded text.
"""
import json,sys,time
from types import SimpleNamespace
import numpy as np
import torch
import mlx.core as mx
from mlx_lm.models.llama import Model,ModelArgs
from engine_support import ROOT,UPSTREAM,Meter,mapping,save,sha
from inference_binding import bind_compute_views
sys.path.insert(0,str(UPSTREAM))
from tokenizer import Tokenizer

def main():
 if (ROOT/'boundary-audit.json').exists():raise RuntimeError('One audit; no selective replay')
 assert json.loads((ROOT/'train-supervisor.json').read_text())['worker_reaped']
 mx.set_cache_limit(512*1024**2);mx.set_memory_limit(12*1024**3)
 state=torch.load(ROOT/'stage1-checkpoint.pt',map_location='cpu',weights_only=False)
 model=Model(ModelArgs(model_type='llama',hidden_size=288,num_hidden_layers=6,intermediate_size=768,num_attention_heads=6,num_key_value_heads=6,rms_norm_eps=1e-5,vocab_size=32000,max_position_embeddings=256,rope_traditional=True,tie_word_embeddings=True))
 params={new:mx.array(state['model'][old].numpy(),dtype=mx.float32) for old,new in mapping().items()}
 model=bind_compute_views(SimpleNamespace(model=model,params=params,dtype=mx.bfloat16))
 tok=Tokenizer(str(UPSTREAM/'tokenizer.model'));meter=Meter();rows=json.loads((ROOT/'stage1-evaluation/stories.json').read_text());out=[]
 deadline=json.loads((ROOT/'clock.json').read_text())['stage1_deadline_epoch']-20
 for row in rows:
  mx.random.seed(row['seed']);ids=tok.encode(row['prefix'],bos=True,eos=False);generated=[]
  for _ in range(row['max_new_tokens']):
   assert time.time()<deadline and not (ROOT/'global-stop.json').exists()
   meter.reserve(len(ids),'boundary-audit-full-input')
   logits=model(mx.array([ids],dtype=mx.int32))[0,-1,:].astype(mx.float32)/.7
   assert bool(mx.all(mx.isfinite(logits)))
   order=mx.argsort(logits)[::-1];sorted_logits=logits[order];probs=mx.softmax(sorted_logits);masked=mx.where(mx.cumsum(probs)-probs>.9,-float('inf'),sorted_logits)
   token=int(order[mx.random.categorical(masked)].item())
   if token==tok.eos_id:break
   ids.append(token);generated.append(token)
  text=tok.decode(generated);boundaries=[i for i,t in enumerate(generated) if t==tok.bos_id]
  out.append(dict(id=row['id'],generated_ids=generated,decoded_reproduced_original=text==row['response'],BOS_positions=boundaries,first_document_response=tok.decode(generated[:boundaries[0]]) if boundaries else text))
  save(ROOT/'boundary-audit.json',dict(status='IN_PROGRESS',rows=out))
  if len(out)%20==0:print('audited',len(out),flush=True)
 save(ROOT/'boundary-audit.json',dict(status='COMPLETE',training_updates=0,decoded_matches=sum(v['decoded_reproduced_original'] for v in out),cases=len(out),cases_with_BOS=sum(bool(v['BOS_positions']) for v in out),first_document_scoring_not_a_replacement_for_frozen_full_window_scores=True,rows=out))
if __name__=='__main__':main()
