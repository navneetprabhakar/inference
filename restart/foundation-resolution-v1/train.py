"""Single shared bounded training runner, parameterized by resolution phase/arm."""
import argparse,concurrent.futures,copy,json,math,sys,time
import numpy as np
from common import *
from evaluate import fixed_loss,options,generate

def exact(a,b,path='state'):
 import torch
 if isinstance(a,torch.Tensor):
  assert isinstance(b,torch.Tensor) and a.dtype==b.dtype and a.shape==b.shape and torch.equal(a,b),path
 elif isinstance(a,np.ndarray):assert np.array_equal(a,b),path
 elif isinstance(a,dict):
  assert a.keys()==b.keys(),path
  for k in a:exact(a[k],b[k],path+'.'+str(k))
 elif isinstance(a,(list,tuple)):
  assert type(a)==type(b) and len(a)==len(b),path
  for i,(x,y) in enumerate(zip(a,b)):exact(x,y,path+f'[{i}]')
 else:assert a==b,path

def snapshot(engine,out):
 import torch
 finite(engine);state=engine.checkpoint();step=engine.base_step+engine.local_step
 state.update(optimizer_step=step,completed_targets=step*131072,reserved_targets=step*131072,full_training_authorized=False,next_stage_authorized=False,resolution_version=1)
 state['scheduler']={**state['scheduler'],'step':step};state['data_cursor']={**state['data_cursor'],'completed_microbatches':step*32}
 path=out/'checkpoint.pt';tmp=out/'checkpoint.partial';torch.save(state,tmp);loaded=torch.load(tmp,map_location='cpu',weights_only=False);exact(state,loaded)
 for v in state['model'].values():assert v.dtype==torch.float32 and torch.isfinite(v).all()
 for v in state['optimizer']['state'].values():
  for field in ['step','exp_avg','exp_avg_sq']:assert torch.isfinite(v[field]).all()
 tmp.replace(path)
 receipt=dict(path=str(path.relative_to(PROJECT)),sha256=sha(path),optimizer_step=step,completed_targets=step*131072,additional_updates=engine.local_step,verified_exact_CPU_reload=True,epoch=time.time())
 save(out/'checkpoint.json',receipt);return receipt

def main():
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['R1','R2']);p.add_argument('arm',choices=['A','B','selected']);a=p.parse_args();phase=a.phase
 check(phase);freeze_check(phase)
 assert sha(ROOT/'plan.json')==read(ROOT/'approval-receipt.json')['plan_sha256']
 if phase=='R1':
  assert read(ROOT/'R0-result.json')['status']=='PASS' and a.arm in ['A','B']
  source=PROJECT/'restart/foundation-stage3-v1/stage3-checkpoint.pt';source_sha=read(ROOT/'plan.json')['reference_checkpoint']['sha256'];n=256;base_step=2889
  baseline=read(ROOT/'baseline/summary.json')['validation_nll'];out=ROOT/a.arm
  if a.arm=='B':
   assert read(ROOT/'A/training-complete.json')['status']=='PASS'
   schedule=lambda step:original_rate(2889)+(.00005-original_rate(2889))*(step-2889)/255
  else:schedule=original_rate
 else:
  choice=read(ROOT/'R1-result.json');assert choice['status']=='PASS' and a.arm=='selected';arm=choice['selected_arm'];source=ROOT/arm/'checkpoint.pt';source_sha=read(ROOT/arm/'checkpoint.json')['sha256'];base_step=3145;n=572
  baseline=read(ROOT/arm/'summary.json')['validation_nll'];out=ROOT/'R2';schedule=original_rate if arm=='A' else lambda step:.00005
 assert sha(source)==source_sha;out.mkdir(exist_ok=False)
 engine,Stream=load_engine(source,schedule=schedule);assert engine.base_step==base_step
 stream=Stream(skip_sequences=base_step*512);meter=Meter(phase);start=time.monotonic();losses=[];spikes=0;hashes=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
  future=pool.submit(stream.batch,512)
  for i in range(n):
   check(phase);batch=future.result()
   if i+1<n:future=pool.submit(stream.batch,512)
   assert stream.consumed>=(base_step+i+1)*512
   digest=__import__('hashlib').sha256(batch.tobytes()).hexdigest();hashes.append(digest)
   if phase=='R1' and a.arm=='B':assert digest==read(ROOT/'A/batch-hashes.json')['hashes'][i],'ARM_DATA_MISMATCH'
   meter.reserve(131072,'training-'+a.arm);loss,norm=engine.update(batch,lambda:check(phase));finite(engine)
   assert math.isfinite(loss) and math.isfinite(norm)
   if i<16 and loss>2*baseline:raise RuntimeError('FIRST16_LOSS_SPIKE')
   losses.append(loss)
   if i>=16:
    spikes=spikes+1 if loss>1.5*float(np.mean(losses[:16])) else 0
    if spikes>=3:raise RuntimeError('CONSECUTIVE_LOSS_SPIKES')
   elapsed=time.monotonic()-start
   row=dict(phase=phase,arm=a.arm,update=i+1,total_updates=n,optimizer_step=base_step+i+1,loss=loss,gradient_norm=norm,learning_rate=schedule(base_step+i),elapsed_seconds=elapsed,targets=(i+1)*131072,training_targets_per_second=(i+1)*131072/elapsed,input_sha256=digest)
   with (out/'updates.jsonl').open('a') as f:f.write(json.dumps(row)+'\n');f.flush()
   save(ROOT/'progress.json',row)
   if (i+1)%8==0:print(json.dumps(row),flush=True)
   if (i+1)%64==0 or i+1==n:
    receipt=snapshot(engine,out);nll=fixed_loss(engine,meter)
    with (out/'validation-history.jsonl').open('a') as f:f.write(json.dumps(dict(update=i+1,nll=nll,epoch=time.time()))+'\n')
    if nll>baseline+.10:raise RuntimeError('PERIODIC_VALIDATION_REGRESSION')
    save(out/'latest-validation.json',dict(update=i+1,nll=nll))
    print(json.dumps(dict(event='checkpoint',phase=phase,arm=a.arm,update=i+1,nll=nll)),flush=True)
 rows,scores=options(engine,meter);save(out/'options.json',rows)
 save(out/'summary.json',dict(validation_nll=nll,**scores,dtype_proof=engine.dtype_proof))
 generate(engine,meter,read(ROOT/'probes.json')['stories'],out/'stories.json')
 if phase=='R2':generate(engine,meter,read(OLD/'packet.json')['stories'],out/'original-stories.json')
 save(out/'batch-hashes.json',dict(hashes=hashes,sequence_start=base_step*512,sequence_end=(base_step+n)*512))
 assert sha(source)==source_sha,'ORIGIN_MUTATED'
 save(out/'training-complete.json',dict(status='PASS',phase=phase,arm=a.arm,additional_updates=n,additional_targets=n*131072,checkpoint=receipt,seconds=time.monotonic()-start,memory=engine.memory(),source_immutable=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:
  save(ROOT/'STOP.json',dict(phase=sys.argv[1],reason=type(e).__name__+': '+str(e),epoch=time.time(),training_authorized=False));raise
