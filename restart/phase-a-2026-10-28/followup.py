"""Orthogonal prompt-form inference; carries every previous A4 charge forward."""
import json,sys,time,hashlib,gc
import numpy as np,torch
from build import ROOT,PRIVATE,P,SPEC,sp,serial
from contracts import Budget
sys.path.insert(0,str(P/'restart/conversation-improvement-v1'))
import adapter9 as adapter
SOURCE=P/'restart/conversation-improvement-v1/private/cycle10-1600.pt'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert not (ROOT/'followup-started.json').exists();manifest=json.loads((ROOT/'followup-freeze.json').read_text())
 for name,h in manifest['files'].items():assert sha(P/name)==h
 parent=ROOT/'inference-ledger.json';assert sha(parent)==manifest['parent_ledger_sha256'];d=json.loads(parent.read_text());assert 'active' not in d
 ledger=ROOT/'followup-ledger.json';assert not ledger.exists();ledger.write_text(json.dumps(d));(ROOT/'followup-started.json').write_text(json.dumps(dict(updates=0,scope='same30min/5M PhaseA4 aggregate cap; no reset')))
 meter=Budget(ledger,SPEC['inference_max_positions'],SPEC['inference_max_seconds']);log=(PRIVATE/'followup-responses.jsonl').open('x')
 try:
  a=adapter.Adapter();a.restore(torch.load(SOURCE,map_location='cpu',weights_only=False));e,common=a.e,a.common;model=common.bind(e);mx=e.mx
  import mlx.optimizers as optim
  def forbidden(*args,**kwargs):raise RuntimeError('OPTIMIZER_FORBIDDEN')
  optim.Optimizer.apply_gradients=forbidden
  def digest():
   h=hashlib.sha256()
   for k in sorted(e.params):h.update(k.encode());h.update(np.array(e.params[k]).tobytes())
   return h.hexdigest()
  before=digest()
  for case in json.loads((PRIVATE/'followup-probes.json').read_text()):
   ids=serial([dict(role='user',content=case['user'])])[0];tokens=[];stop=None
   for _ in range(16):
    meter.reserve(len(ids),'followup-generation');v=model(mx.array([ids],mx.int32))[0,-1,:].astype(mx.float32);mx.eval(v);e.memory()
    assert bool(mx.all(mx.isfinite(v)));token=int(mx.argmax(v))
    if token in [sp.bos_id(),sp.eos_id()]:stop=token;break
    tokens.append(token);ids.append(token)
   text=sp.decode(tokens);r=dict(case,response=text,eos=stop==sp.eos_id(),correct=text.strip()==case['expected'] and stop==sp.eos_id());log.write(json.dumps(r)+'\n');log.flush()
  after=digest();assert before==after;assert sha(SOURCE)==manifest['source_sha256'];(ROOT/'followup-result.json').write_text(json.dumps(dict(status='COMPLETED',parameter_hash_before=before,parameter_hash_after=after,updates=0,final_test_used=False)))
 except BaseException as ex:(ROOT/'followup-stop.json').write_text(json.dumps(dict(reason=str(ex),type=type(ex).__name__)));raise
 finally:log.close();meter.close()
if __name__=='__main__':main()
