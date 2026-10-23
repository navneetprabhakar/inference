"""Inference-only decoding and passage-control diagnosis; no optimizer exists here."""
import json,sys,time,hashlib
from pathlib import Path
import numpy as np
import torch
import mlx.core as mx
from mlx_lm.models.llama import Model,ModelArgs
from mlx.utils import tree_unflatten
from engine_support import ROOT,PROJECT,UPSTREAM,CHECKPOINT,Meter,mapping,sha,save
sys.path.insert(0,str(UPSTREAM))
from tokenizer import Tokenizer

def main():
 contract=json.loads((ROOT/'contract.json').read_text());clock=json.loads((ROOT/'clock.json').read_text());meter=Meter()
 assert contract['inference_only_authorized'] and not contract['training_authorized']
 assert sha(CHECKPOINT)==contract['reference']['checkpoint_sha256']
 def check(n,phase):
  assert time.time()<min(clock['stage2_deadline_epoch'],clock['overall_original_deadline_epoch'])-20
  assert not (ROOT/'global-stop.json').exists()
  if mx.get_active_memory()+mx.get_cache_memory()>12*1024**3 or mx.get_peak_memory()>12*1024**3:raise RuntimeError('GPU_MEMORY_CAP')
  meter.reserve(n,phase)
 mx.set_cache_limit(512*1024**2);mx.set_memory_limit(12*1024**3)
 state=torch.load(CHECKPOINT,map_location='cpu',weights_only=False);assert state['optimizer_step']==1745 and state['completed_targets']==228720640
 model=Model(ModelArgs(model_type='llama',hidden_size=288,num_hidden_layers=6,intermediate_size=768,num_attention_heads=6,num_key_value_heads=6,rms_norm_eps=1e-5,vocab_size=32000,max_position_embeddings=256,rope_traditional=True,tie_word_embeddings=True))
 params={new:mx.array(state['model'][old].numpy(),dtype=mx.bfloat16) for old,new in mapping().items()};assert sum(v.size for v in params.values())==15191712
 model.update(tree_unflatten(list(params.items())));tok=Tokenizer(str(UPSTREAM/'tokenizer.model'));packet=json.loads((PROJECT/'restart/foundation-stage2-v1/packet.json').read_text());saved=json.loads((PROJECT/'restart/foundation-stage2-v1/stage2-evaluation/option-scores.json').read_text());saved={v['id']:v for v in saved if v['kind']=='grounded'}
 scores=[]
 for case in packet['grounded']:
  context,question=case['prefix'].rsplit('. ',1);context+='.'
  words=[v.strip().rstrip('.') for v in case['options']];assert all(w.isalpha() for w in words)
  import re
  rename=dict(zip(words,words[1:]+words[:1]));changed=re.sub(r'\b('+'|'.join(map(re.escape,words))+r')\b',lambda m:rename[m[0]],context)
  for kind,prefix,answer in [('intact',case['prefix'],case['answer']),('empty_passage',question,case['answer']),('counterfactual_passage',changed+' '+question,(case['answer']+1)%4)]:
   pre=tok.encode(prefix,bos=True,eos=False);values=[]
   for opt in case['options']:
    target=tok.encode(opt,bos=False,eos=False);ids=pre+target;assert len(ids)<=256;check(len(ids)-1,'grounded-'+kind)
    logits=model(mx.array([ids[:-1]],dtype=mx.int32)).astype(mx.float32)[0,len(pre)-1:,:];logp=logits-mx.logsumexp(logits,axis=-1,keepdims=True);score=mx.sum(mx.take_along_axis(logp,mx.array(target,dtype=mx.int32)[:,None],axis=-1));mx.eval(score);assert np.isfinite(float(score));values.append(float(score))
   winners=[i for i,v in enumerate(values) if abs(v-max(values))<=1e-8];prediction=winners[0] if len(winners)==1 else None
   if kind=='intact':assert np.allclose(values,saved[case['id']]['scores'],rtol=0,atol=1e-5),'Same checkpoint inference mismatch'
   scores.append(dict(id=case['id'],family=case['family'],kind=kind,prefix=prefix,answer=answer,prediction=prediction,correct=prediction==answer,scores=values))
 save(ROOT/'grounding-controls.json',scores)
 rows=[]
 for family in range(20):
  case=packet['stories'][family*5+family%5];ids=tok.encode(case['prefix'],bos=True,eos=False);out=[];eos=False
  for _ in range(96):
   check(len(ids),'greedy-story-full-input');logits=model(mx.array([ids],dtype=mx.int32))[0,-1,:].astype(mx.float32);assert bool(mx.all(mx.isfinite(logits)));token=int(mx.argmax(logits).item())
   if token==tok.eos_id:eos=True;break
   ids.append(token);out.append(token)
  rows.append(dict(**case,decoding='greedy',response=tok.decode(out),generated_ids=out,BOS_positions=[i for i,v in enumerate(out) if v==tok.bos_id],eos=eos));save(ROOT/'greedy-stories.json',rows)
  print('greedy stories',len(rows),flush=True)
 summary=dict(status='COMPLETE_INFERENCE_ONLY',training_updates=0,optimizer_created=False,weights_updated=False,checkpoint_unchanged=sha(CHECKPOINT)==contract['reference']['checkpoint_sha256'],grounding={k:sum(v['correct'] for v in scores if v['kind']==k) for k in ['intact','empty_passage','counterfactual_passage']},cases_per_grounding_condition=100,greedy_cases=20,processed_positions=meter.total(),frozen_gate_unchanged=True,controls_are_reused_development_not_fresh_acceptance=True)
 save(ROOT/'result.json',summary);print(json.dumps(summary))
if __name__=='__main__':main()
