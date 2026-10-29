"""Approved PhaseA4 inference only. No optimizer calls or historical ledger mutations."""
import json,sys,time,hashlib,gc,os
from pathlib import Path
import numpy as np
import torch
import psutil
from build import ROOT,PRIVATE,P,SPEC,sp,serial
from contracts import Budget
sys.path.insert(0,str(P/'restart/conversation-improvement-v1'))
import adapter9 as adapter
s=adapter.s
SOURCES={
 'foundation':P/'restart/foundation-resolution-v1/B/checkpoint.pt',
 'factual_A':P/'restart/factual-binding-v1/binding/epoch-400.pt',
 'broader_B':P/'restart/broader-curriculum-v1/broad/epoch-100.pt',
 'grounding_adapter':P/'restart/conversation-improvement-v1/private/cycle10-1600.pt'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):q=p.with_suffix('.tmp');q.write_text(json.dumps(v,indent=2));q.replace(p)
def resources():
 if psutil.Process().memory_info().rss>12*1024**3 or psutil.disk_usage(P).free<60*1024**3:raise RuntimeError('RESOURCE_CAP')
def array_digest(e):
 h=hashlib.sha256()
 for k in sorted(e.params):h.update(k.encode());h.update(np.array(e.params[k]).tobytes())
 return h.hexdigest()
def prompt(messages):return serial(messages)[0]
def normalized(x):return ' '.join(x.casefold().strip().split())
def strict(kind,x,y):
 if kind=='time':return x.strip()==y.strip()
 return normalized(x)==normalized(y)
def main():
 assert not (ROOT/'inference-started.json').exists(),'No implicit rerun'
 freeze=json.loads((ROOT/'freeze.json').read_text())
 for raw,h in freeze['files'].items():assert sha(P/raw)==h,raw
 for name,path in SOURCES.items():assert sha(path)==freeze['sources'][name]
 save(ROOT/'inference-started.json',dict(time=time.time(),updates_allowed=0));meter=Budget(ROOT/'inference-ledger.json',SPEC['inference_max_positions'],SPEC['inference_max_seconds']);probes=json.loads((PRIVATE/'inference-probes.json').read_text());result=[];log=(PRIVATE/'inference-responses.jsonl').open('x');cal=[]
 try:
  for name,path in SOURCES.items():
   resources();start=time.monotonic()
   if name=='grounding_adapter':
    a=adapter.Adapter();a.restore(torch.load(path,map_location='cpu',weights_only=False));e,common=a.e,a.common
   else:e,common=s.load(path,mode='resume')
   import mlx.optimizers as optim
   def forbidden(*args,**kwargs):raise RuntimeError('OPTIMIZER_CALL_FORBIDDEN')
   optim.Optimizer.apply_gradients=forbidden
   before=array_digest(e);model=common.bind(e);mx=e.mx
   def logits(ids,kind):
    resources();meter.reserve(len(ids),kind);v=model(mx.array([ids],mx.int32))[0,-1,:].astype(mx.float32);mx.eval(v)
    if not bool(mx.all(mx.isfinite(v))):raise RuntimeError('NONFINITE_LOGITS')
    e.memory();return v
   for case_index,case in enumerate(probes):
    for mode in (['generated','gold'] if case['family']=='state' else ['generated']):
     history=[]
     for turn in range(len(case['messages'])//2):
      user=case['messages'][2*turn];expected=case['messages'][2*turn+1]['content'];history.append(user);ids=prompt(history);prefix=ids.copy();cap=24 if case['family']=='state' else 16;tokens=[];stop=None;overflow=len(ids)+cap>256
      if not overflow:
       for _ in range(cap):
        v=logits(ids,'generate');token=int(mx.argmax(v))
        if token in [sp.bos_id(),sp.eos_id()]:stop=token;break
        tokens.append(token);ids.append(token)
      text=sp.decode(tokens);row={k:v for k,v in case.items() if k not in ['messages']};row.update(model=name,mode=mode,turn=turn,user=user['content'],expected=expected,response=text,eos=stop==sp.eos_id(),bos=stop==sp.bos_id(),overflow=overflow,correct=strict(case['kind'],text,expected) and stop==sp.eos_id() and not overflow,reference_tokens=[])
      if case['family'] in ['name','time']:
       reference=sp.encode(expected)+[sp.eos_id()]
       for position,target in enumerate(reference):
        v=logits(prefix+reference[:position],'reference-prefix');lp=v-mx.logsumexp(v);rank=1+int(mx.sum(v>v[target]));pred=int(mx.argmax(v));row['reference_tokens'].append(dict(position=position,target=target,predicted=pred,rank=rank,log_probability=float(lp[target]),target_eos=target==sp.eos_id(),predicted_eos=pred==sp.eos_id()))
       row['first_reference_error']=next((x for x in row['reference_tokens'] if x['predicted']!=x['target']),None)
      log.write(json.dumps(row)+'\n');log.flush();result.append(row);history.append(dict(role='assistant',content=expected if mode=='gold' else text))
    if name=='foundation' and case_index==3:
     elapsed=time.monotonic()-start;estimate=elapsed/4*(128+48)*4
     receipt=dict(first_four_seconds=elapsed,conservative_linear_projection_seconds=estimate,positions_so_far=meter.data['positions'],note='Includes initial model loading; pessimistic convenience calibration, hard caps remain binding.')
     save(ROOT/'inference-calibration.json',receipt)
     if estimate>SPEC['inference_max_seconds']:raise RuntimeError('PROJECTED_INFERENCE_BUDGET_INFEASIBLE')
   after=array_digest(e);assert before==after,'MODEL_PARAMS_CHANGED';assert sha(path)==freeze['sources'][name]
   cal.append(dict(model=name,parameter_hash_before=before,parameter_hash_after=after,checkpoint_sha256=sha(path),seconds=time.monotonic()-start,turns=sum(r['model']==name for r in result)));save(ROOT/'inference-model-integrity.json',cal)
   print(json.dumps(cal[-1]),flush=True)
   del model,e,common
   if name=='grounding_adapter':del a
   gc.collect()
  save(ROOT/'inference-result.json',dict(status='COMPLETED',turns=len(result),updates=0,models=list(SOURCES),final_test_used=False))
 except BaseException as ex:save(ROOT/'inference-stop.json',dict(reason=str(ex),type=type(ex).__name__,completed_turns=len(result)));raise
 finally:log.close();meter.close()
if __name__=='__main__':main()
