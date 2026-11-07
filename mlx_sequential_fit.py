"""Explicit-spec two-update fit probe. No default activation or model on import."""
import argparse,fcntl,hashlib,json,math,os,shutil,sys,time
from pathlib import Path
import own_base_dev_run as rt
from mlx_full_benchmark_control_v2 import output_bytes,swap_bytes,require_ac,require
ROOT=Path(__file__).resolve().parent
LIMITS=dict(wall_seconds=600,attempted_targets=16384,output_bytes=64*1024**2,free_disk_bytes=20*1024**3,gpu_bytes=12*1024**3,cache_bytes=1024**3,rss_bytes=18*1024**3,swap_growth_bytes=1024**3)
RUN=ROOT/'runs/own-base-mlx-sequential-fit-01'

def digest(path,check=lambda:None):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  while chunk:=f.read(4*1024**2):h.update(chunk);check()
 return h.hexdigest()
def read(path):return json.loads(Path(path).read_text())
def validate(spec,check=lambda:None):
 require(spec.get('state')=='reviewed_two_update_sequential_fit' and spec.get('schema')==1,'reviewed fit specification required')
 require(spec['run']==str(RUN) and spec['limits']==LIMITS,'fixed fit limits/run')
 require(spec['python']==str(ROOT/'.venv-mlx-own-base/bin/python'),'existing MLX interpreter only')
 require(spec['source_run']==str(ROOT/'runs/own-base-mlx-full-benchmark-02'),'fixed prior source artifacts')
 expected_stops={str(ROOT/'runs/STOP'),str(RUN/'STOP'),str(ROOT/'runs/own-base-foundation-01/STOP'),str(ROOT/'runs/own-base-mlx-full-benchmark-01/STOP'),str(ROOT/'runs/own-base-mlx-full-benchmark-02/STOP')}|{str(ROOT/f'runs/optimizer-ablation-v1-{a}/STOP')for a in ('preserve-095','reset-095','reset-scaled')}
 require(expected_stops<=set(spec['stop_paths']),'inherited STOPs')
 require(spec['cache_policy']=='fixed-clear-every-synchronized-boundary' and spec['updates']==2,'fixed scheduling/cache policy')
 for name,h in spec['code_sha256'].items():
  p=(ROOT/name).resolve();require(p.is_relative_to(ROOT) and digest(p,check)==h,'changed runtime:'+name)
 required={'mlx_sequential_fit.py','mlx_sequential_train_core.py','mlx_full_benchmark_worker_v2.py','mlx_own_base_adapter.py','mlx_train_core.py','own_base_dev_run.py'}
 require(required<=set(spec['code_sha256']),'runtime pins missing')
 for name,pin in spec['input_files'].items():
  p=Path(name);require(p.is_absolute() and p.resolve()==p and p.is_relative_to(ROOT) and not p.is_symlink() and p.stat().st_size==pin['bytes'] and digest(p,check)==pin['sha256'],'input artifact identity')
 prior=read(Path(spec['source_run'])/'spec.json');require(prior==spec['reference_spec'],'unchanged original reference identity')
 require(spec['reference_spec']['configuration']==dict(microbatch=2,length=512,accumulation=8,lr=6e-5),'unchanged update workload')
 for p in [Path(spec['source_run'])/'artifacts'/n for n in ('neutral-source.npz','neutral-source.json','ref-updates.npz','ref-updates.json')]:require(str(p)in spec['input_files'],'required reference pin')
 source=Path(spec['source_run']);accepted=read(source/'phases/A00-source/result.json');neutral_receipt=read(source/'artifacts/neutral-source.json')
 for name in ('phases/A00-source/result.json','phases/A00-source/watchdog.json','phases/Aupdates-cpu/result.json','phases/Aupdates-cpu/watchdog.json','benchmark-ledger.json','spec.json'):
  require(str(source/name)in spec['input_files'],'accepted reference proof missing')
 reference_accepted=read(source/'phases/Aupdates-cpu/result.json');require(reference_accepted['state']=='complete' and reference_accepted['artifact']==read(source/'artifacts/ref-updates.json'),'accepted Torch reference identity')
 require(accepted['state']=='complete' and accepted['exact_torch_roundtrip'] is True and accepted['artifact']==neutral_receipt,'accepted exact source conversion')
 for phase in ('A00-source','Aupdates-cpu'):
  watchdog=read(source/'phases'/phase/'watchdog.json');require(watchdog['exit_code']==0 and not watchdog['watchdog_reason'] and watchdog['within_deadline'],'accepted reference watchdog')
 ledger=read(source/'benchmark-ledger.json')
 for phase in ('A00-source','Aupdates-cpu'):
  entry=next(x for x in ledger['completed_phases']if x['id']==phase)
  require(entry['result_sha256']==digest(source/'phases'/phase/'result.json') and entry['watchdog_sha256']==digest(source/'phases'/phase/'watchdog.json'),'reference ledger accepted hashes')
 return spec

class Budget:
 def __init__(self,spec,run,ticket,*,probe=True):
  self.spec=spec;self.run=Path(run);self.ticket=ticket;self.probe=probe;self.last_os=-math.inf;self.last_beat=-math.inf;self.baseline=read(self.run/'launch.json')['baseline_swap_bytes']
 def check(self):
  require(rt.remaining(self.ticket)>0,'fit deadline');require(not any(Path(p).exists()for p in self.spec['stop_paths']),'STOP')
  require(output_bytes(self.run)<LIMITS['output_bytes']-1024**2,'fit output budget/headroom')
  if time.monotonic()-self.last_beat>=1:
   (self.run/'heartbeat').write_text(str(time.monotonic()));self.last_beat=time.monotonic()
  if self.probe:
   require(shutil.disk_usage(self.run).free>=LIMITS['free_disk_bytes'],'disk floor')
   if time.monotonic()-self.last_os>=30:
    self.last_os=time.monotonic();require_ac();require(rt.apple_thermal()in (0,1),'thermal unavailable/serious');require(swap_bytes()-self.baseline<=LIMITS['swap_growth_bytes'],'swap growth')
 def event(self,event,**data):
  self.check();payload=json.dumps(dict(event=event,wall=time.time(),**data),allow_nan=False)+'\n'
  with (self.run/'events.jsonl').open('a')as f:f.write(payload);f.flush();os.fsync(f.fileno())
 def reserve(self):
  self.check();v=read(self.run/'ledger.json');require(v['pending'] is None and v['reserved_targets']+8192<=16384,'attempt ceiling/pending');v['reserved_targets']+=8192;v['pending']=dict(targets=8192,update=v['reserved_targets']//8192);rt.atomic(self.run/'ledger.json',v);self.event('reserved',pending=v['pending'])
 def commit(self,metrics):
  self.check();v=read(self.run/'ledger.json');require(v['pending'] is not None,'missing reservation');v['committed_targets']+=8192;v['pending']=None;rt.atomic(self.run/'ledger.json',v);self.event('committed',metrics=metrics)

def compare_state(core,source,reference,budget):
 import numpy as np
 from mlx_full_benchmark_worker_v2 import difference
 results={}
 with np.load(reference,allow_pickle=False)as target:
  expected={kind+'::'+n for kind in ('weight','m','v')for n in core.params};require(set(target.files)==expected,'reference inventory')
  for kind,cap in [('weight',5e-5),('m',1e-5),('v',1e-5)]:
   maximum=error2=delta2=0.;per={}
   for name,param in core.params.items():
    budget.check();group=core.optimizers[0 if param.ndim>=2 else 1]
    actual=np.array(param if kind=='weight' else group.state[name][kind]);key=kind+'::'+name;ref=target[key]
    metric=difference({key:actual},{key:ref});maximum=max(maximum,metric['max_abs']);per[name]=metric['max_abs'];error2+=metric['rms']**2*actual.size
    if kind=='weight':
     rf=ref.reshape(-1);baseline=source[key].reshape(-1)
     for start in range(0,rf.size,65536):
      delta=rf[start:start+65536].astype(np.float64)-baseline[start:start+65536].astype(np.float64);delta2+=float(np.dot(delta,delta))
    del actual,ref
   result=dict(max_abs=maximum,per_tensor_max_abs=per);require(maximum<=cap,kind+' update parity')
   if kind=='weight':result['update_delta_relative_l2']=math.sqrt(error2)/max(math.sqrt(delta2),1e-12);require(result['update_delta_relative_l2']<=.02,'update delta parity')
   results[kind]=result
 return results

def worker(spec_path,run,fd):
 ticket=rt.consume_ticket(fd);require(ticket['spec_sha256']==digest(spec_path),'ticket exact spec');spec=read(spec_path);require(Path(run).resolve()==RUN and spec['run']==str(RUN),'worker output');budget=Budget(spec,run,ticket);budget.check();validate(spec,budget.check)
 import importlib.metadata as md
 require(Path(sys.executable).absolute()==Path(spec['python']).absolute(),'worker environment');require(dict(python=sys.version,mlx=md.version('mlx'),numpy=md.version('numpy'))==spec['versions'],'package versions')
 # No device/model allocation occurs before ticket/spec/lineage input verification.
 import numpy as np
 import mlx.core as mx
 import mlx_own_base_adapter as adapter
 from mlx_sequential_train_core import SequentialTrainCore,check_memory
 from mlx_full_benchmark_worker_v2 import load_arrays,Data,CONFIG
 from mlx_train_core import Config
 source=Path(spec['source_run']);base,arrays=load_arrays(source/'artifacts/neutral-source.npz');meta=base['neutral'];require(meta['identity']['model']==CONFIG,'exact own model')
 require(str(Path(meta['source']['path']))in spec['input_files'] and digest(meta['source']['path'],budget.check)==meta['source']['sha256'],'protected own checkpoint binding')
 cfg,core_meta,native,provenance=adapter.convert_neutral(meta,arrays,pinned=base['pinned']);data=Data(spec['reference_spec']);ref=read(source/'artifacts/ref-updates.json')['metadata'];require(ref['kind']=='two-updates' and len(ref['trace'])==2,'reference trace')
 mx.set_default_device(mx.gpu);previous_cache=mx.set_cache_limit(LIMITS['cache_bytes']);previous_memory=mx.set_memory_limit(LIMITS['gpu_bytes']);mx.synchronize();mx.reset_peak_memory();highwater=0;last_boundary_end=time.monotonic()
 def boundary(stage,index):
  nonlocal highwater,last_boundary_end
  entered=time.monotonic();interval=entered-last_boundary_end
  budget.check();mx.synchronize();active=mx.get_active_memory();peak=mx.get_peak_memory();cache=mx.get_cache_memory();highwater=max(highwater,peak);rss=rt.group_rss(os.getpgrp());budget.event('memory_before_clear',stage=stage,index=index,interval_since_previous_boundary_seconds=interval,active=active,peak=peak,phase_peak=highwater,cache=cache,rss=rss,driver=None,driver_reason='MLX0.32.4 API unavailable')
  # Peak/active/RSS cannot be hidden by clearing the allocator cache.
  check_memory(active=active,peak=highwater,cache=cache,rss=rss,cache_limit=2**63)
  begin=time.monotonic();mx.clear_cache();mx.synchronize();retained=mx.get_cache_memory();check_memory(active=mx.get_active_memory(),peak=max(highwater,mx.get_peak_memory()),cache=retained,rss=rt.group_rss(os.getpgrp()));budget.event('memory_after_clear',stage=stage,index=index,cache=retained,cleanup_seconds=time.monotonic()-begin);last_boundary_end=time.monotonic()
 budget.event('allocator_policy',previous_cache_limit=previous_cache,previous_memory_guideline=previous_memory,cache_limit=LIMITS['cache_bytes'],memory_guideline=LIMITS['gpu_bytes'])
 weights={n[8:]:v for n,v in native.items()if n.startswith('weight::')};policy=meta['optimizer'][0]
 core=SequentialTrainCore(weights,Config(**cfg),device=mx.gpu,boundary=boundary,learning_rate=policy['learning_rate'],betas=tuple(policy['betas']),epsilon=policy['epsilon'],matrix_decay=policy['weight_decay'],restored=(core_meta,native));boundary('initial_load',-1);trace=[]
 # convert_neutral constructs dictionaries sharing NumPy weight/moment arrays;
 # no extra full host copy there. Release every such alias after device eval.
 del arrays,native,weights,base,provenance
 for update in range(2):
  budget.reserve();start=time.monotonic();last_boundary_end=start;budget.event('update_started',update=update+1,monotonic=start);rows=[mx.array(data.batch(update,i),dtype=mx.int32)for i in range(8)];loss,norm=core.step(rows,learning_rate=6e-5);del rows
  result=dict(update=update+1,loss=loss,norm=norm,seconds=time.monotonic()-start);budget.commit(result);trace.append(result)
 with np.load(source/'artifacts/neutral-source.npz',allow_pickle=False)as baseline:
  comparison=compare_state(core,baseline,source/'artifacts/ref-updates.npz',budget)
 require(core.cursor['step']==core_meta['cursor']['step']+2 and core.cursor['trained_tokens']==core_meta['cursor']['trained_tokens']+16384,'exact optimizer/cursor count')
 for got,want in zip(trace,ref['trace']):require(abs(got['loss']-want['loss'])<=1e-4 and abs(got['norm']-want['norm'])/max(abs(want['norm']),1e-12)<=1e-3,'loss/norm trace parity')
 boundary('comparison_complete',2);rt.atomic(Path(run)/'result.json',dict(state='two_update_fit_and_parity_only',trace=trace,comparison=comparison,cursor=core.cursor,peak=highwater,native_resume_tested=False,sustained_throughput_tested=False));return 0

def launch(path,expected):
 started=time.monotonic();ticket=rt.make_ticket(600,expected);path=Path(path).resolve();require(path.stat().st_size<1024**2 and digest(path)==expected,'exact bounded spec');spec=validate(read(path),lambda:require(rt.remaining(ticket)>10,'verification deadline'));require(not RUN.exists(),'fresh fit directory');require(not any(Path(p).exists()for p in spec['stop_paths']),'STOP');require(shutil.disk_usage(ROOT).free>=LIMITS['free_disk_bytes']+LIMITS['output_bytes'],'disk forecast');require_ac()
 lock=(ROOT/'runs/mps.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 RUN.mkdir();rt.atomic(RUN/'spec.json',spec);baseline=swap_bytes();rt.atomic(RUN/'launch.json',dict(started_monotonic=started,started_wall=time.time(),baseline_swap_bytes=baseline,spec_sha256=expected));rt.atomic(RUN/'ledger.json',dict(reserved_targets=0,committed_targets=0,pending=None));last=-math.inf
 def check(pid,remaining):
  nonlocal last
  require(not any(Path(p).exists()for p in spec['stop_paths']),'STOP');require(output_bytes(RUN)<LIMITS['output_bytes']-1024**2,'output ceiling');require(shutil.disk_usage(ROOT).free>=LIMITS['free_disk_bytes'],'disk floor')
  if time.monotonic()-last>=30:
   last=time.monotonic();require_ac();require(rt.apple_thermal()in (0,1),'mandatory thermal');require(rt.group_rss(pid,timeout=min(2,max(.01,remaining)))<=LIMITS['rss_bytes'],'parent RSS');require(swap_bytes(min(2,max(.01,remaining)))-baseline<=LIMITS['swap_growth_bytes'],'parent swap')
 try:
  result=rt.supervise(lambda fd:[spec['python'],str(Path(__file__).resolve()),'_worker',str(path),str(RUN),str(fd)],RUN,ticket=ticket,heartbeat_seconds=90,grace_seconds=10,max_rss_bytes=LIMITS['rss_bytes'],check=check)
  rt.atomic(RUN/'watchdog.json',result);ledger=read(RUN/'ledger.json');passed=result['exit_code']==0 and not result['watchdog_reason'] and result['within_deadline'] and ledger==dict(reserved_targets=16384,committed_targets=16384,pending=None) and (RUN/'result.json').exists()
  rt.atomic(RUN/'terminal.json',dict(state='two_update_fit_only' if passed else 'incomplete',watchdog=result,ledger=ledger,wall_seconds=time.monotonic()-started,no_retry=True));return 0 if passed else 2
 except BaseException as error:
  rt.atomic(RUN/'terminal.json',dict(state='incomplete',error_type=type(error).__name__,error=str(error)[:4096],ledger=read(RUN/'ledger.json'),wall_seconds=time.monotonic()-started,no_retry=True));return 2
 finally:lock.close()

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='_worker':raise SystemExit(worker(sys.argv[2],sys.argv[3],int(sys.argv[4])))
 parser=argparse.ArgumentParser();parser.add_argument('spec');parser.add_argument('--expected-spec-sha256',required=True);args=parser.parse_args();raise SystemExit(launch(args.spec,args.expected_spec_sha256))
