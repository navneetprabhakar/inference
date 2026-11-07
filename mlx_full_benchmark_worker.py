"""Explicit-ticket full-own-model benchmark worker; never a training candidate.

Controller owns lock, immutable spec, phase order, watchdog and attempted budget.
No model/device is allocated on import. Torch and MLX use isolated environments.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
os.environ['MLX_ENABLE_TF32']='0'
import argparse,contextlib,hashlib,json,math,pathlib,struct,sys,time
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parent
CONFIG=dict(vocabulary=50257,context=1024,width=768,heads=12,depth=12)
TARGETS=8192;LENGTH=512;BATCH=2;ACCUMULATION=8;LR=6e-5

def require(ok,why):
 if not ok:raise ValueError(why)
def sha(path):
 with pathlib.Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def write(path,value):
 with pathlib.Path(path).open('x') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')
def artifact(run,name):
 require(pathlib.Path(name).name==name and name.endswith('.npz'),'artifact basename');return run/'artifacts'/name

def save_arrays(path,arrays,meta,budget):
 from mlx_full_benchmark_control import output_bytes,OUTPUT_LIMIT,storage_check
 budget.check();forecast=sum(x.nbytes for x in arrays.values())+len(arrays)*1024+65536
 require(output_bytes(budget.run)+forecast<=OUTPUT_LIMIT,'artifact disk forecast exceeds ceiling')
 require(not path.exists() and not path.with_suffix('.json').exists(),'preserve reference artifact')
 with path.open('xb') as f:np.savez(f,**arrays);f.flush();os.fsync(f.fileno())
 budget.check();receipt=dict(metadata=meta,file=path.name,bytes=path.stat().st_size,sha256=sha(path));write(path.with_suffix('.json'),receipt);return receipt

def load_arrays(path):
 receipt=json.loads(path.with_suffix('.json').read_text());require(receipt['file']==path.name and not path.is_symlink() and path.stat().st_size==receipt['bytes'] and sha(path)==receipt['sha256'],'reference artifact identity')
 with np.load(path,allow_pickle=False) as f:arrays={n:f[n] for n in f.files}
 return receipt['metadata'],arrays

def difference(actual,reference,*,baseline=None):
 require(set(actual)==set(reference),'comparison tensor inventory');maximum=0.;squared=reference_squared=delta_squared=delta_reference=0.;per_tensor={}
 for name in sorted(reference):
  a,b=actual[name],reference[name];require(a.shape==b.shape and a.dtype==b.dtype,'comparison shape/dtype');am=a.reshape(-1);bm=b.reshape(-1);mx=0.
  for start in range(0,am.size,65536):
   av=am[start:start+65536].astype(np.float64);bv=bm[start:start+65536].astype(np.float64);require(np.isfinite(av).all() and np.isfinite(bv).all(),'comparison finite values');diff=av-bv
   mx=max(mx,float(np.max(np.abs(diff),initial=0)));squared+=float(np.dot(diff,diff));reference_squared+=float(np.dot(bv,bv))
   if baseline is not None:
    base=baseline[name].reshape(-1)[start:start+65536].astype(np.float64);rd=bv-base;delta_squared+=float(np.dot(diff,diff));delta_reference+=float(np.dot(rd,rd))
  per_tensor[name]=mx;maximum=max(maximum,mx)
 total=sum(x.size for x in reference.values());result=dict(max_abs=maximum,rms=math.sqrt(squared/max(total,1)),relative_l2=math.sqrt(squared)/max(math.sqrt(reference_squared),1e-12),per_tensor_max_abs=per_tensor)
 if baseline is not None:result['update_delta_relative_l2']=math.sqrt(delta_squared)/max(math.sqrt(delta_reference),1e-12)
 return result

def validate_worker_environment(spec,phase):
 import importlib.metadata as metadata
 import mlx_full_benchmark_control as control
 control.validate_spec(spec)
 runtime='torch' if phase['runtime'].startswith('torch') else 'mlx'
 require(pathlib.Path(sys.executable).absolute()==pathlib.Path(spec['python'][runtime]).absolute(),'worker interpreter differs from frozen environment')
 actual={'python':sys.version,runtime:metadata.version(runtime),'numpy':metadata.version('numpy')}
 require(actual==spec['versions'][runtime],'worker package/Python versions differ')
 source=spec['source_spec'];data=spec['data'];identity=spec['benchmark_identity']
 for name,relative in [('foundation','runs/own-base-foundation-01-supervisor.json'),('optimizer','runs/optimizer-ablation-v1/supervisor.json')]:
  pin=spec['terminal_supervisors'][name];path=ROOT/relative;require(pin['path']==str(path) and sha(path)==pin['sha256'],'terminal supervisor identity differs');terminal=json.loads(path.read_text());require(terminal['state']=='completed' and terminal['worker_exit_code']==0,'terminal supervisor not successful')
  expected={'foundation':{'trainer':'base_train.py','spec':'reports/base-foundation-100m/budget.json'},'optimizer':{'trainer':'optimizer_ablation_train.py','spec':'reports/optimizer-ablation-v1/experiment-r2.json','reporter':'optimizer_ablation_report.py'}}[name]
  for field,filename in expected.items():
   pinned=terminal['identity'];require(pinned[field]==str(ROOT/filename) and sha(ROOT/filename)==pinned[field+'_sha256'],'terminal supervisor runtime/spec differs')
  if name=='optimizer':require(terminal['parent']==source['parent'],'queue selected parent differs')
 require(identity['source']==source['parent'] and identity['source_offset']==source['source_offset'] and identity['configuration']==spec['configuration'] and identity['versions']==spec['versions'],'benchmark/source identity differs')
 require(data['source_offset']==source['source_offset'] and data['slice_targets']==spec['slice_targets'],'source/data slice differs')
 corpus=pathlib.Path(source['corpus']);manifest_path=corpus/'manifest.json';blocks_path=corpus/'validation-blocks.json'
 require(sha(manifest_path)==source['manifest_sha256'] and sha(blocks_path)==source['validation_blocks_sha256'],'source data metadata identity')
 manifest=json.loads(manifest_path.read_text());blocks=json.loads(blocks_path.read_text())
 require(identity['tokenizer']==manifest['tokenizer'],'tokenizer identity differs')
 require(data['validation_offsets']==[b['start'] for b in blocks if b['max_length']>=513][:2],'predetermined validation windows differ')
 for name in ('train','validation'):
  require(pathlib.Path(data[name+'_path'])==corpus/('fineweb-'+name+'.u16') and data[name+'_sha256']==manifest['shards']['fineweb-'+name]['sha256'],'source shard identity differs')
 return actual

def prefix_difference(original,altered,prefix=256):
 require(original.shape==altered.shape and original.ndim==3 and original.shape[1]==512,'causal full-logit shapes')
 result=difference({'prefix':altered[:,:prefix,:]},{'prefix':original[:,:prefix,:]})
 require(result['max_abs']<=1e-6,'causal-prefix invariance failed')
 return result

class Data:
 def __init__(self,spec):
  self.spec=spec;d=spec['data'];self.start=99999744;require(d['source_offset']==self.start and d['slice_targets']==16777216,'fixed source slice')
  self.train=np.memmap(d['train_path'],dtype='<u2',mode='r');self.validation=np.memmap(d['validation_path'],dtype='<u2',mode='r')
  require(sha(d['train_path'])==d['train_sha256'] and sha(d['validation_path'])==d['validation_sha256'],'data identity');require(self.start+16777216<len(self.train),'no-wrap slice including boundary')
 def batch(self,update,microbatch):
  require(0<=update<2048 and 0<=microbatch<8,'fixed slice exhaustion');start=self.start+update*8192+microbatch*1024
  rows=np.stack([self.train[start+i*512:start+(i+1)*512+1] for i in range(2)]).astype(np.int32);require(rows.shape==(2,513) and np.max(rows)<50257,'causal batch');return rows
 def validation_batch(self):
  offsets=self.spec['data']['validation_offsets'];require(len(offsets)==2,'fixed validation microbatch')
  rows=np.stack([self.validation[o:o+513] for o in offsets]).astype(np.int32);require(rows.shape==(2,513) and np.max(rows)<50257,'validation bounds');return rows

class Engine:
 def __init__(self,runtime,meta,arrays,identity,budget,*,native=None):
  self.runtime=runtime;self.meta=meta;self.source=arrays;self.budget=budget;self.identity=identity;self.progress=0
  if runtime.startswith('torch'):
   import torch
   from gpt2 import GPT2,Config
   from train import optimizer_for
   import own_base_neutral_state as neutral
   torch.set_num_threads(1);self.torch=torch;self.device='cpu' if runtime=='torch-cpu' else 'mps'
   with torch.device('meta'):self.model=GPT2(Config(**meta['identity']['model']))
   self.model.to_empty(device='cpu');self.optimizer=optimizer_for(self.model)
   neutral.import_objects(self.model,self.optimizer,meta,arrays,**{'expected_'+k:meta[k] for k in ('identity','source','progress','optimizer')})
   self.model.to(self.device)
   for state in self.optimizer.state.values():
    for k in ('exp_avg','exp_avg_sq'):state[k]=state[k].to(self.device)
   self.model.train();self.compiled=False
  else:
   import mlx.core as mx
   import mlx_own_base_adapter as adapter
   self.mx=mx;mx.set_default_device(mx.gpu);self.device=mx.gpu;self.compiled=True
   if native is None:self.model=adapter.DisposableCore(meta,arrays,pinned=adapter.expected(meta),benchmark_identity=identity,device=mx.gpu)
   else:self.model=adapter.DisposableCore.from_native(*native,benchmark_identity=identity,source_provenance=native[0]['source_provenance'],device=mx.gpu)
  self.sync();self.memory()
 def sync(self):
  if self.runtime.startswith('torch'):
   if self.device=='mps':self.torch.mps.synchronize()
  else:self.mx.eval(self.model.core.state);self.mx.synchronize()
 def memory(self):
  if self.runtime.startswith('torch'):
   if self.device=='cpu':return
   self.budget.memory(self.torch.mps.current_allocated_memory(),None,self.torch.mps.driver_allocated_memory())
  else:self.budget.memory(self.mx.get_active_memory(),self.mx.get_cache_memory(),None,peak=self.mx.get_peak_memory())
 def tensor(self,rows):
  if self.runtime.startswith('torch'):return self.torch.from_numpy(rows.astype(np.int64)).to(self.device)
  return self.mx.array(rows,dtype=self.mx.int32)
 def autocast(self):
  return self.torch.autocast('mps',dtype=self.torch.bfloat16) if self.runtime=='torch-mps-bf16' else contextlib.nullcontext()
 def evaluate(self,rows,*,gradients=False,logits=False):
  if self.runtime.startswith('torch'):
   import torch.nn.functional as F
   self.optimizer.zero_grad(set_to_none=True);seq=self.tensor(rows)
   with self.autocast():
    output=self.model(seq[:,:-1]);loss=F.cross_entropy(output.flatten(0,1),seq[:,1:].flatten())
   if gradients:loss.backward()
   self.sync();result=dict(loss=float(loss.item()))
   if logits:result['arrays']={'logits':output.detach().float().cpu().numpy()}
   if gradients:
    result['arrays']={n:p.grad.detach().cpu().numpy().copy() for n,p in self.model.named_parameters()};norm=self.torch.linalg.vector_norm(self.torch.stack([self.torch.linalg.vector_norm(p.grad) for p in self.model.parameters()]));result['norm']=float(norm.item())
  else:
   import mlx_train_core as core
   seq=self.tensor(rows)
   if gradients:
    loss,g=core.accumulated_gradients(self.model.core.params,[seq],self.model.core.config,device=self.device);_,norm=core.clip_gradients(g,1.,device=self.device);self.mx.eval(loss,g,norm);result=dict(loss=float(loss.item()),norm=float(norm.item()),arrays={n:np.array(a) for n,a in g.items()})
   else:
    output=core.forward(self.model.core.params,seq[:,:-1],self.model.core.config,device=self.device);target=self.mx.take_along_axis(output,seq[:,1:,None],axis=-1).squeeze(-1);loss=self.mx.mean(self.mx.logsumexp(output,axis=-1)-target);self.mx.eval(output,loss);result=dict(loss=float(loss.item()))
    if logits:result['arrays']={'logits':np.array(output)}
  require(math.isfinite(result['loss']),'nonfinite loss');self.memory();return result
 def update(self,rows):
  require(len(rows)==8 and all(x.shape==(2,513) for x in rows),'full production update shape')
  if self.runtime.startswith('torch'):
   from gpt2 import next_token_loss
   self.optimizer.zero_grad(set_to_none=True);loss_sum=0.
   for group in self.optimizer.param_groups:group['lr']=LR
   for row in rows:
    with self.autocast():loss=next_token_loss(self.model,self.tensor(row))/8
    loss.backward();loss_sum+=float(loss.detach().item())
    if self.device=='cpu':self.budget.check()
   norm=self.torch.nn.utils.clip_grad_norm_(self.model.parameters(),1.,error_if_nonfinite=True);self.optimizer.step();self.sync();result=(loss_sum,float(norm.item()))
  else:result=self.model.step([self.tensor(r) for r in rows],learning_rate=LR)
  require(all(math.isfinite(v) for v in result),'nonfinite update');self.progress+=1;self.memory();return result
 def snapshot_arrays(self):
  if self.runtime.startswith('torch'):
   return {kind+'::'+n:(p if kind=='weight' else self.optimizer.state[p]['exp_avg' if kind=='m' else 'exp_avg_sq']).detach().cpu().numpy().copy() for n,p in self.model.named_parameters() for kind in ('weight','m','v')}
  _,arrays=self.model.snapshot();return {k:v for k,v in arrays.items() if k.startswith(('weight::','m::','v::'))}
 def restore(self):
  if self.runtime.startswith('torch'):
   with self.torch.no_grad():
    for n,p in self.model.named_parameters():
     p.copy_(self.torch.from_numpy(self.source['weight::'+n]).to(self.device));state=self.optimizer.state[p]
     for kind,key in [('m','exp_avg'),('v','exp_avg_sq')]:state[key].copy_(self.torch.from_numpy(self.source[kind+'::'+n]).to(self.device))
     state['step'].copy_(self.torch.from_numpy(self.source['step::'+n]))
    for g,policy in zip(self.optimizer.param_groups,self.meta['optimizer']):g['lr']=policy['learning_rate']
   self.optimizer.zero_grad(set_to_none=True)
  else:
   import mlx_own_base_adapter as adapter
   self.model.restore_source_in_place(self.source,pinned=adapter.expected(self.meta))
  self.progress=0;self.sync();self.memory()

def source_convert(spec,run,budget):
 from mlx_own_base_source import load_verified,exact_torch_roundtrip
 model,opt,meta,arrays,pinned=load_verified(spec['source_spec']);budget.check();del model,opt
 report=exact_torch_roundtrip(meta,arrays,pinned);budget.check()
 report['artifact']=save_arrays(artifact(run,'neutral-source.npz'),arrays,dict(neutral=meta,pinned=pinned),budget)
 write(run/'source-provenance.json',dict(neutral=meta,pinned=pinned,scalar_learning_rate=report));return report

def correctness(spec,run,phase,budget):
 command=phase['command'];reference=command.endswith('reference');base,arrays=load_arrays(artifact(run,'neutral-source.npz'));meta=base['neutral'];require(meta['identity']['model']==CONFIG,'full frozen architecture')
 engine=Engine(phase['runtime'],meta,arrays,spec['benchmark_identity'],budget);data=Data(spec);path=artifact(run,phase['artifact']);result={}
 if command.startswith(('logits','gradients')):
  kind=command.split('-')[0];rows=data.batch(0,phase['microbatch']);budget.reserve(1024,kind);started=time.monotonic();result=engine.evaluate(rows,gradients=kind=='gradients',logits=kind=='logits');seconds=time.monotonic()-started;values=result.pop('arrays');budget.commit(1024,kind,dict(seconds=seconds,**result));result['seconds']=seconds
  if kind=='logits':
   altered=rows.copy();altered[:,256:]=(altered[:,256:]+1)%CONFIG['vocabulary'];budget.reserve(1024,'causal-prefix');changed=engine.evaluate(altered,logits=True);budget.commit(1024,'causal-prefix',dict(loss=changed['loss']));result['causal_prefix']=prefix_difference(values['logits'],changed['arrays']['logits']);del changed
  if reference:result['artifact']=save_arrays(path,values,dict(kind=kind,microbatch=phase['microbatch'],**result),budget)
  else:
   ref,expected=load_arrays(path);require(ref['kind']==kind and ref['microbatch']==phase['microbatch'],'reference kind/batch');metrics=difference(values,expected);result['comparison']=metrics;result['loss_abs_difference']=abs(result['loss']-ref['loss'])
   require(result['loss_abs_difference']<=1e-4,'FP32 loss parity')
   if kind=='logits':require(metrics['rms']<=1e-4 and metrics['max_abs']<=1e-3,'full-logit parity')
   else:
    result['norm_relative_difference']=abs(result['norm']-ref['norm'])/max(abs(ref['norm']),1e-12)
    require(metrics['relative_l2']<=1e-3 and metrics['max_abs']<=1e-4 and result['norm_relative_difference']<=1e-3,'all-gradient parity')
 elif command.startswith('updates'):
  trace=[]
  for step in range(2):
   budget.reserve(8192,'correctness-update');started=time.monotonic();loss,norm=engine.update([data.batch(step,i) for i in range(8)]);record=dict(loss=loss,norm=norm,seconds=time.monotonic()-started);budget.commit(8192,'correctness-update',record);trace.append(record)
  values=engine.snapshot_arrays();result['trace']=trace
  if reference:result['artifact']=save_arrays(path,values,dict(kind='two-updates',trace=trace),budget)
  else:
   ref,expected=load_arrays(path);require(ref['kind']=='two-updates','update reference kind');result['comparison']={}
   for kind,ceiling in [('weight',5e-5),('m',1e-5),('v',1e-5)]:
    a={k:v for k,v in values.items() if k.startswith(kind+'::')};b={k:expected[k] for k in a};metric=difference(a,b,baseline={k:arrays[k] for k in a} if kind=='weight' else None);result['comparison'][kind]=metric;require(metric['max_abs']<=ceiling,kind+' update parity')
    if kind=='weight':require(metric['update_delta_relative_l2']<=.02,'update delta parity')
 else:raise ValueError('unknown correctness command')
 budget.check();return result

def timed_update(engine,data,index,budget,kind):
 budget.reserve(8192,kind);start=time.monotonic();loss,norm=engine.update([data.batch(index,i) for i in range(8)]);record=dict(index=index,loss=loss,norm=norm,seconds=time.monotonic()-start);budget.commit(8192,kind,record);return record

def checkpoint_io(engine,run,phase,budget):
 """One atomic native full-state save/readback; disposable after receipt publication."""
 path=run/'artifacts'/('checkpoint-'+phase['id']);path.mkdir(exist_ok=False);start=time.monotonic()
 from mlx_full_benchmark_control import output_bytes,OUTPUT_LIMIT
 require(output_bytes(run)+1600*1024**2<=OUTPUT_LIMIT,'checkpoint forecast')
 if engine.runtime.startswith('torch'):
  payload=dict(model=engine.model.state_dict(),optimizer=engine.optimizer.state_dict(),benchmark_identity=engine.identity,source_identity=engine.meta,committed_updates=engine.progress,cpu_rng=engine.torch.get_rng_state(),mps_rng=engine.torch.mps.get_rng_state())
  pending=path/'pending.pt'
  with pending.open('xb') as f:engine.torch.save(payload,f);f.flush();os.fsync(f.fileno())
  digest=sha(pending);final=path/(digest+'.pt');os.replace(pending,final);receipt=dict(file=final.name,sha256=digest,bytes=final.stat().st_size)
  pending_meta=path/'pending.json';write(pending_meta,receipt);os.replace(pending_meta,path/'accepted.json');fd=os.open(path,os.O_RDONLY)
  try:os.fsync(fd)
  finally:os.close(fd)
  saved_seconds=time.monotonic()-start;start_read=time.monotonic();require(sha(final)==digest,'Torch checkpoint byte integrity');loaded=engine.torch.load(final,map_location='cpu',mmap=True,weights_only=True)
  require(loaded['benchmark_identity']==engine.identity and loaded['committed_updates']==engine.progress,'Torch checkpoint identity/cursor')
  for n,p in engine.model.state_dict().items():require(engine.torch.equal(loaded['model'][n],p.detach().cpu()),'Torch checkpoint weights')
  original=engine.optimizer.state_dict();require(loaded['optimizer']['param_groups']==original['param_groups'],'Torch checkpoint groups')
  for n,state in original['state'].items():
   for k,v in state.items():require(engine.torch.equal(loaded['optimizer']['state'][n][k],v.detach().cpu()),'Torch checkpoint moments/steps')
  require(engine.torch.equal(loaded['cpu_rng'],payload['cpu_rng']) and engine.torch.equal(loaded['mps_rng'],payload['mps_rng']),'Torch checkpoint RNG')
  del loaded,payload
 else:
  import mlx_own_base_adapter as bridge
  meta,arrays=engine.model.snapshot();receipt=bridge.publish(path,meta,arrays,benchmark_identity=engine.identity,source_provenance=engine.model.provenance,check=budget.check);saved_seconds=time.monotonic()-start;start_read=time.monotonic()
  other_meta,other=bridge.read_native(path,benchmark_identity=engine.identity,source_provenance=engine.model.provenance);require(meta==other_meta and all(np.array_equal(a,other[n]) for n,a in arrays.items()),'MLX checkpoint exact readback')
  del arrays,other
 report=dict(save_seconds=saved_seconds,read_seconds=time.monotonic()-start_read,bytes=receipt['bytes'],sha256=receipt['sha256'],atomic_native_state=True,exact_readback=True)
 write(path/'io-result.json',report);budget.check()
 # Only this new disposable accepted checkpoint is removed, after successful
 # readback plus persisted small evidence. Protected source is reverified.
 source=engine.meta['source'];require(sha(source['path'])==source['sha256'],'protected source changed before disposable cleanup')
 file=path/receipt['file'];require(file.parent==path and file.exists() and not file.is_symlink(),'checkpoint cleanup ownership');file.unlink()
 return report

def sustained(spec,run,phase,budget):
 base,arrays=load_arrays(artifact(run,'neutral-source.npz'));meta=base['neutral'];engine=Engine(phase['runtime'],meta,arrays,spec['benchmark_identity'],budget);data=Data(spec)
 budget.period('warmup');warm=[]
 for i in range(10):warm.append(timed_update(engine,data,i,budget,'warmup'))
 trace_before=engine.model.core.trace_count if engine.compiled else None
 engine.restore();settling=[timed_update(engine,data,i,budget,'settling') for i in range(2)]
 trace_after=engine.model.core.trace_count if engine.compiled else None
 if engine.compiled and trace_after!=trace_before:
  # Protocol permits cache warm-up repeats only inside the original five-minute cap.
  for i in range(2,12):warm.append(timed_update(engine,data,i,budget,'restore-cache-warmup'))
  trace_before=engine.model.core.trace_count;engine.restore();settling=[timed_update(engine,data,i,budget,'settling-after-rewarmup') for i in range(2)];trace_after=engine.model.core.trace_count
  require(trace_before==trace_after,'restore repeatedly invalidates compiled graph')
 budget.period('measured');begin=time.monotonic();updates=[];bins=[dict(targets=0,updates=0) for _ in range(6)];index=2;runway=False
 while True:
  elapsed=time.monotonic()-begin;remaining=1800-elapsed;largest=max([x['seconds'] for x in updates] or [x['seconds'] for x in settling]);margin=max(10.,2*largest)
  if remaining<=margin:runway=True;break
  require(index<2048,'fixed 2048-update slice exhausted before sustained window completed')
  item=timed_update(engine,data,index,budget,'measured');item['committed_at_seconds']=time.monotonic()-begin
  require(item['committed_at_seconds']<=1800,'last update exceeded measured window');updates.append(item);bucket=min(5,int(item['committed_at_seconds']//300));bins[bucket]['targets']+=8192;bins[bucket]['updates']+=1;index+=1
 # Retain a fixed 1800-second denominator, explicitly including end-of-window
 # idle runway. Switch the last 0.5s to overhead to avoid sub-ms cap overruns.
 while time.monotonic()-begin<1799.5:budget.check();time.sleep(min(.2,max(0.,1799.5-(time.monotonic()-begin))))
 budget.period('overhead')
 while time.monotonic()-begin<1800:budget.check();time.sleep(min(.1,max(0.,1800-(time.monotonic()-begin))))
 elapsed=time.monotonic()-begin;require(updates and elapsed>=1800,'incomplete sustained window')
 budget.reserve(1024,'fixed-validation');start=time.monotonic();validation=engine.evaluate(data.validation_batch());validation['seconds']=time.monotonic()-start;budget.commit(1024,'fixed-validation',validation)
 io=checkpoint_io(engine,run,phase,budget);targets=len(updates)*8192
 for b in bins:b['targets_per_second']=b['targets']/300
 return dict(warmup=warm,settling=settling,compiled_trace_count_before_restore=trace_before,compiled_trace_count_after_restore=trace_after,warmup_updates=len(warm),settling_updates=len(settling),measured_updates=len(updates),measured_trace=updates,measured_window_seconds=1800.,prescribed_window_seconds=1800.,observed_window_seconds=elapsed,last_commit_seconds=updates[-1]['committed_at_seconds'],slice_exhausted=False,ending_idle_seconds=1800-updates[-1]['committed_at_seconds'],idle_included_in_denominator=runway,targets=targets,targets_per_second=targets/1800,contiguous_five_minute_bins=bins,last_ten_minutes_targets_per_second=sum(b['targets'] for b in bins[-2:])/600,validation=validation,checkpoint_io=io,checkpoint_adjusted_targets_per_second=(targets/1800)*600/(600+io['save_seconds']),precision='BF16 autocast with FP32 master parameters/moments' if phase['runtime']=='torch-mps-bf16' else 'FP32',correctness_pass=None)

def resume_phase(spec,run,phase,budget):
 import mlx_own_base_adapter as bridge
 command=phase['command'];data=Data(spec);source=json.loads((run/'source-provenance.json').read_text());meta=source['neutral'];identity=spec['benchmark_identity']
 if command=='resume-check':
  provenance=json.loads((run/'resume-provenance.json').read_text());saved,arrays=bridge.read_native(run/'artifacts/native-resume',benchmark_identity=identity,source_provenance=provenance)
  engine=Engine('mlx-gpu-fp32',meta,{},identity,budget,native=(saved,arrays));trace=[timed_update(engine,data,i,budget,'native-resumed-update') for i in (2,3)];final,values=engine.model.snapshot();reference,expected=load_arrays(artifact(run,'resume-reference.npz'))
  require(final==reference['native_metadata'],'native resume full metadata/cursor');require(set(values)==set(expected) and all(np.array_equal(values[n],expected[n]) for n in values),'native resume exact every array')
  require([(x['loss'],x['norm']) for x in trace]==[tuple(x) for x in reference['loss_norm_trace'][2:]],'native resume exact subsequent loss/norm trace')
  return dict(correctness_pass=True,exact_arrays=len(values),exact_metadata=True,exact_subsequent_trace=True,trace=trace,fresh_process=True)
 base,arrays=load_arrays(artifact(run,'neutral-source.npz'));engine=Engine('mlx-gpu-fp32',meta,arrays,identity,budget);steps=4 if command=='resume-reference' else 2
 trace=[timed_update(engine,data,i,budget,'native-resume-reference' if steps==4 else 'native-resume-before-save') for i in range(steps)];saved,values=engine.model.snapshot()
 if steps==4:
  receipt=save_arrays(artifact(run,'resume-reference.npz'),values,dict(native_metadata=saved,loss_norm_trace=[(x['loss'],x['norm']) for x in trace]),budget)
  return dict(trace=trace,artifact=receipt)
 # The source neutral weight file is now redundant: native state has full own
 # identity/progress/RNG and fresh restore does not pretend new weights are source.
 require(command=='resume-pause','resume command');source_receipt=meta['source'];require(sha(source_receipt['path'])==source_receipt['sha256'],'protected source before neutral cleanup')
 neutral_path=artifact(run,'neutral-source.npz');require(sha(neutral_path)==json.loads(neutral_path.with_suffix('.json').read_text())['sha256'],'neutral cleanup identity');neutral_path.unlink()
 write(run/'resume-provenance.json',engine.model.provenance);receipt=bridge.publish(run/'artifacts/native-resume',saved,values,benchmark_identity=identity,source_provenance=engine.model.provenance,check=budget.check)
 return dict(trace=trace,checkpoint=receipt,neutral_disposable_removed=True)

def cleanup(run,phase,budget):
 path=artifact(run,phase['artifact']);receipt=json.loads(path.with_suffix('.json').read_text());require(not path.is_symlink() and sha(path)==receipt['sha256'],'disposable cleanup identity');path.unlink();path.with_suffix('.json').unlink();budget.check();return dict(removed=phase['artifact'])

def execute_command(spec,run,phase,budget):
 command=phase['command']
 if command=='source-convert':return source_convert(spec,run,budget)
 if command=='cleanup':return cleanup(run,phase,budget)
 if command=='sustained':return sustained(spec,run,phase,budget)
 if command.startswith('resume-'):return resume_phase(spec,run,phase,budget)
 if command in ('logits-reference','logits-compare','gradients-reference','gradients-compare','updates-reference','updates-compare'):return correctness(spec,run,phase,budget)
 raise ValueError('unknown worker command')

def result_payload(phase,result,seconds):
 return dict(result,state='complete',phase=phase['id'],command=phase['command'],runtime=phase['runtime'],correctness_pass=True if phase['command']!='sustained' else None,seconds=seconds)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--spec',required=True);parser.add_argument('--run',required=True);parser.add_argument('--phase',required=True);parser.add_argument('--ticket-fd',type=int,required=True);args=parser.parse_args()
 import mlx_full_benchmark_control as control
 ticket=control.runtime.consume_ticket(args.ticket_fd);spec=json.loads(pathlib.Path(args.spec).read_text());run=pathlib.Path(args.run).resolve();phase=next(p for p in spec['phases'] if p['id']==args.phase)
 require(ticket['spec_sha256']==sha(args.spec) and ticket['phase']==args.phase,'ticket specification');require(run==pathlib.Path(spec['run']).resolve(),'output identity')
 validate_worker_environment(spec,phase)
 for relative,h in spec['code_sha256'].items():require(sha(ROOT/relative)==h,'worker runtime pin')
 budget=control.WorkerBudget(spec,run,args.phase,ticket);destination=run/'phases'/args.phase/'result.json';started=time.monotonic()
 try:
  command=phase['command'];result=execute_command(spec,run,phase,budget)
  budget.check();output=result_payload(phase,result,time.monotonic()-started);control.validate_phase_result(phase,output);write(destination,output)
 except BaseException as error:
  if not destination.exists():write(destination,dict(state='failed',phase=args.phase,command=phase['command'],runtime=phase['runtime'],correctness_pass=False,seconds=time.monotonic()-started,error_type=type(error).__name__,error=str(error)))
  raise
if __name__=='__main__':main()
