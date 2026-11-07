"""Explicit frozen four-phase steady/resume probe; no production campaign."""
import argparse,fcntl,json,math,os,shutil,sys,time
from pathlib import Path
import mlx_sequential_fit as fit
rt=fit.rt;require=fit.require;ROOT=fit.ROOT
RUN=ROOT/'runs/own-base-mlx-sequential-steady-01'
LIMITS=dict(wall_seconds=1200,attempted_targets=2212864,output_bytes=2*1024**3,free_disk_bytes=20*1024**3)
PHASES=['steady','reference','pause','resume']

def validate(spec,check=lambda:None):
 require(spec.get('state')=='reviewed_sequential_steady_resume' and spec['schema']==1,'reviewed steady spec required');require(spec['run']==str(RUN) and spec['limits']==LIMITS and spec['phases']==PHASES,'fixed steady allocation')
 fit.validate(spec['fit_spec'],check);require(spec['fit_run']==str(fit.RUN),'verified fit source');require(str(RUN/'STOP')in spec['stop_paths'] and set(spec['fit_spec']['stop_paths'])<=set(spec['stop_paths']),'all STOPs inherited')
 for p,h in spec['code_sha256'].items():require(fit.digest(ROOT/p,check)==h,'steady code pin:'+p)
 for p,pin in spec['proof_files'].items():require(Path(p).stat().st_size==pin['bytes'] and fit.digest(p,check)==pin['sha256'],'fit receipt identity')
 terminal=fit.read(fit.RUN/'terminal.json');require(terminal['state']=='two_update_fit_only' and terminal['ledger']==dict(reserved_targets=16384,committed_targets=16384,pending=None),'successful fit gate')
 require(spec['python']==spec['fit_spec']['python'],'same runtime');return spec

class Budget(fit.Budget):
 def __init__(self,spec,run,ticket,phase,*,probe=True):super().__init__(spec,run,ticket,probe=probe);self.phase=phase;self.beat=self.run/'phases'/phase/'heartbeat'
 def check(self):
  require(rt.remaining(self.ticket)>0,'steady deadline');require(not any(Path(p).exists()for p in self.spec['stop_paths']),'STOP');require(fit.output_bytes(self.run)<LIMITS['output_bytes']-1024**2,'steady output headroom')
  if time.monotonic()-self.last_beat>=1:self.beat.write_text(str(time.monotonic()));self.last_beat=time.monotonic()
  if self.probe:
   require(shutil.disk_usage(self.run).free>=LIMITS['free_disk_bytes'],'disk floor')
   if time.monotonic()-self.last_os>=30:
    self.last_os=time.monotonic();fit.require_ac();require(rt.apple_thermal()in (0,1),'thermal');require(fit.swap_bytes()-self.baseline<=1024**3,'swap growth')
 def reserve(self,targets,kind):
  self.check();v=fit.read(self.run/'ledger.json');require(type(targets)==int and targets in (1024,8192) and v['pending']is None and v['reserved_targets']+targets<=LIMITS['attempted_targets'],'attempt ceiling/pending');v['reserved_targets']+=targets;v['pending']=dict(phase=self.phase,targets=targets,kind=kind);rt.atomic(self.run/'ledger.json',v);self.event('reserved',pending=v['pending'])
 def commit(self,metrics):
  self.check();v=fit.read(self.run/'ledger.json');require(v['pending']and v['pending']['phase']==self.phase,'pending phase');v['committed_targets']+=v['pending']['targets'];v['pending']=None;rt.atomic(self.run/'ledger.json',v);self.event('committed',phase=self.phase,metrics=metrics)

def measured_window(update,check,*,now=time.monotonic,sleep=time.sleep,settling_seconds):
 start=now();trace=[];bins=[0]*6
 while True:
  remaining=600-(now()-start);largest=max([x['seconds']for x in trace]+[settling_seconds]);margin=max(10.,2*largest)
  if remaining<=margin:break
  require(len(trace)<256,'measured slice exhausted before window')
  x=update(2+len(trace),'measured');x['committed_at_seconds']=now()-start;require(x['committed_at_seconds']<=600,'measured update crossed boundary');trace.append(x);bins[min(5,int(x['committed_at_seconds']//100))]+=8192
 require(trace,'no measured updates')
 while now()-start<600:check();sleep(min(.2,600-(now()-start)))
 return dict(prescribed_seconds=600,observed_seconds=now()-start,last_commit_seconds=trace[-1]['committed_at_seconds'],updates=len(trace),targets=len(trace)*8192,targets_per_second=len(trace)*8192/600,trace=trace,bins_100_seconds=bins,last200_targets_per_second=sum(bins[-2:])/200,idle_in_denominator=True)

def worker(path,run,phase,fd):
 ticket=rt.consume_ticket(fd);require(ticket['spec_sha256']==fit.digest(path) and ticket['phase']==phase,'owned exact phase ticket');spec=fit.read(path);require(Path(run).resolve()==RUN and phase in PHASES,'fixed run/phase');budget=Budget(spec,run,ticket,phase);budget.check();validate(spec,budget.check)
 import importlib.metadata as md
 require(Path(sys.executable).absolute()==Path(spec['python']).absolute() and dict(python=sys.version,mlx=md.version('mlx'),numpy=md.version('numpy'))==spec['fit_spec']['versions'],'runtime version')
 import numpy as np
 import mlx.core as mx
 import mlx_own_base_adapter as bridge
 from mlx_sequential_native import SequentialNative
 from mlx_sequential_train_core import check_memory
 from mlx_full_benchmark_worker_v2 import Data,load_arrays
 from mlx_train_core import causal_loss
 source=Path(spec['fit_spec']['source_run']);source_receipt=fit.read(source/'artifacts/neutral-source.json');base=source_receipt['metadata'];meta=base['neutral'];data=Data(spec['fit_spec']['reference_spec']);identity=spec['execution_identity']
 mx.set_default_device(mx.gpu);mx.set_cache_limit(1024**3);mx.set_memory_limit(12*1024**3);mx.synchronize();mx.reset_peak_memory();peak=0;last=time.monotonic()
 def boundary(stage,index):
  nonlocal peak,last
  entered=time.monotonic();budget.check();mx.synchronize();active=mx.get_active_memory();current_peak=mx.get_peak_memory();peak=max(peak,current_peak);cache=mx.get_cache_memory();rss=rt.group_rss(os.getpgrp());budget.event('memory',phase=phase,stage=stage,index=index,active=active,peak=peak,cache=cache,rss=rss,interval_seconds=entered-last)
  check_memory(active=active,peak=peak,cache=cache,rss=rss,cache_limit=2**63);begin=time.monotonic();mx.clear_cache();mx.synchronize();post=dict(active=mx.get_active_memory(),peak=max(peak,mx.get_peak_memory()),cache=mx.get_cache_memory(),rss=rt.group_rss(os.getpgrp()));budget.event('cache_cleared',phase=phase,stage=stage,seconds=time.monotonic()-begin,**post);check_memory(**post);peak=post['peak'];last=time.monotonic()
 if phase=='resume':
  pause=fit.read(RUN/'phases/pause/result.json');require(pause['source_provenance']['source_neutral']==meta,'resume original neutral provenance');native_meta,native_arrays=bridge.read_native(RUN/'native',benchmark_identity=identity,source_provenance=pause['source_provenance']);model=SequentialNative.from_native(native_meta,native_arrays,benchmark_identity=identity,source_provenance=pause['source_provenance'],device=mx.gpu,boundary=boundary);del native_arrays,native_meta
 else:
  base,arrays=load_arrays(source/'artifacts/neutral-source.npz');model=SequentialNative(meta,arrays,pinned=base['pinned'],benchmark_identity=identity,device=mx.gpu,boundary=boundary);del arrays,base
 boundary('load',-1)
 def update(index,kind):
  nonlocal last
  budget.reserve(8192,kind);start=time.monotonic();last=start;rows=[mx.array(data.batch(index,i),dtype=mx.int32)for i in range(8)];loss,norm=model.step(rows,learning_rate=6e-5);del rows;record=dict(index=index,loss=loss,norm=norm,seconds=time.monotonic()-start);budget.commit(record);return record
 result={}
 if phase=='steady':
  setup=time.monotonic();warmup=[update(i,'warmup')for i in range(4)];callables=(id(model.core._micro),id(model.core._apply));_,arrays=load_arrays(source/'artifacts/neutral-source.npz');model.restore_source_in_place(arrays,pinned=bridge.expected(meta));del arrays;boundary('restored',-1);require(callables==(id(model.core._micro),id(model.core._apply)),'compiled callables replaced');settling=[update(i,'settling')for i in range(2)];require(time.monotonic()-setup<=120,'warmup/restore/settling ceiling')
  measured=measured_window(update,budget.check,settling_seconds=max(x['seconds']for x in settling));budget.reserve(1024,'validation');tick=time.monotonic();loss=causal_loss(model.core.params,mx.array(data.validation_batch()),model.core.config,device=mx.gpu);mx.eval(loss);boundary('validation',0);validation=dict(loss=float(loss.item()),seconds=time.monotonic()-tick);require(math.isfinite(validation['loss']),'finite validation');budget.commit(validation);result=dict(warmup=warmup,settling=settling,measured=measured,validation=validation,restored_callables_preserved=True)
 elif phase=='reference':
  trace=[update(i,'resume-reference')for i in range(4)];result=dict(state_digest=model.digest_state(budget.check),subsequent_trace=[dict(loss=x['loss'],norm=x['norm'])for x in trace[2:]],trace=trace)
 elif phase=='pause':
  trace=[update(i,'resume-pause')for i in range(2)];cm,ca=model.snapshot();boundary('host_snapshot',2);forecast=sum(a.nbytes for a in ca.values())+16*1024**2;require(fit.output_bytes(RUN)+forecast+256*1024**2<=LIMITS['output_bytes'],'one checkpoint disk forecast');require(not (RUN/'native').exists(),'one native publication only');tick=time.monotonic();receipt=bridge.publish(RUN/'native',cm,ca,benchmark_identity=identity,source_provenance=model.provenance,check=budget.check);save_seconds=time.monotonic()-tick;del ca;tick=time.monotonic();rm,ra=bridge.read_native(RUN/'native',benchmark_identity=identity,source_provenance=model.provenance);read_seconds=time.monotonic()-tick;require(rm==cm,'native readback metadata');del ra,rm;boundary('native_io',2);require(len(list((RUN/'native').glob('*.npz')))==1,'single full native checkpoint');result=dict(trace=trace,source_provenance=model.provenance,receipt=receipt,save_seconds=save_seconds,read_seconds=read_seconds)
 else:
  require(model.progress['committed_updates']==2,'resume exact boundary');trace=[update(i,'resume-check')for i in (2,3)];actual=model.digest_state(budget.check);reference=fit.read(RUN/'phases/reference/result.json');require(actual==reference['state_digest'],'exact every-array/cursor/native digest mismatch');observed=[dict(loss=x['loss'],norm=x['norm'])for x in trace];require(observed==reference['subsequent_trace'],'exact freshprocess trace mismatch');result=dict(exact_digest=True,arrays=len(actual['arrays']),exact_trace=True,fresh_process=True,progress=model.progress)
 boundary('phase_complete',-1);budget.check();rt.atomic(RUN/'phases'/phase/'result.json',dict(result,state='complete',phase=phase,peak_bytes=peak));return 0

def launch(path,expected):
 start=time.monotonic();ticket=rt.make_ticket(1200,expected);path=Path(path).resolve();require(path.stat().st_size<1024**2 and fit.digest(path)==expected,'exact spec');spec=validate(fit.read(path),lambda:require(rt.remaining(ticket)>10,'verification deadline'));require(not RUN.exists(),'fresh output');require(shutil.disk_usage(ROOT).free>=20*1024**3+2*1024**3,'disk forecast');require(not any(Path(p).exists()for p in spec['stop_paths']),'STOP');fit.require_ac();lock=(ROOT/'runs/mps.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);RUN.mkdir();(RUN/'phases').mkdir();baseline=fit.swap_bytes();rt.atomic(RUN/'launch.json',dict(baseline_swap_bytes=baseline,started_monotonic=start,started_wall=ticket['wall_started'],spec_sha256=expected));rt.atomic(RUN/'spec.json',spec);rt.atomic(RUN/'ledger.json',dict(reserved_targets=0,committed_targets=0,pending=None));last=-math.inf;resume_started=None
 def check(pid,remaining):
  nonlocal last
  require(rt.remaining(ticket)>0,'outer deadline')
  require(not any(Path(p).exists()for p in spec['stop_paths']),'STOP');require(fit.output_bytes(RUN)<2*1024**3-1024**2,'output cap');require(shutil.disk_usage(ROOT).free>=20*1024**3,'disk floor')
  if time.monotonic()-last>=30:
   last=time.monotonic();fit.require_ac();require(rt.apple_thermal()in (0,1),'thermal');require(rt.group_rss(pid,timeout=min(2,max(.01,remaining)))<=18*1024**3,'RSS');require(fit.swap_bytes(min(2,max(.01,remaining)))-baseline<=1024**3,'swap')
 try:
  for phase in PHASES:
   out=RUN/'phases'/phase;out.mkdir();remaining=rt.remaining(ticket)
   if phase=='reference':resume_started=time.monotonic()
   if phase!='steady':remaining=min(remaining,240-(time.monotonic()-resume_started))
   else:remaining=min(remaining,840)
   require(remaining>10,'phase/outer deadline');child=rt.make_ticket(remaining,expected);child['deadline']=min(child['deadline'],ticket['deadline']);child['phase']=phase
   status=rt.supervise(lambda fd:[spec['python'],str(Path(__file__).resolve()),'_worker',str(path),str(RUN),phase,str(fd)],out,ticket=child,heartbeat_seconds=90,grace_seconds=10,max_rss_bytes=18*1024**3,check=check);rt.atomic(out/'watchdog.json',status);require(status['exit_code']==0 and not status['watchdog_reason']and status['within_deadline'],'phase incomplete');require(fit.read(out/'result.json')['state']=='complete' and fit.read(RUN/'ledger.json')['pending']is None,'complete phase ledger')
  steady=fit.read(RUN/'phases/steady/result.json');pause=fit.read(RUN/'phases/pause/result.json');resume=fit.read(RUN/'phases/resume/result.json');ledger=fit.read(RUN/'ledger.json');require(ledger['reserved_targets']==ledger['committed_targets']==(14+steady['measured']['updates'])*8192+1024 and resume['exact_digest'] and resume['exact_trace'],'complete allocation accounting')
  result=dict(state='steady_and_native_resume_feasible_not_production',ledger=ledger,measured=steady['measured'],checkpoint_io=dict(save_seconds=pause['save_seconds'],read_seconds=pause['read_seconds'],bytes=pause['receipt']['bytes']),checkpoint_adjusted_proxy=steady['measured']['targets_per_second']*600/(600+pause['save_seconds']),resume=resume,wall_seconds=time.monotonic()-start,no_retry=True);rt.atomic(RUN/'terminal.json',result);return 0
 except BaseException as error:rt.atomic(RUN/'terminal.json',dict(state='incomplete',error_type=type(error).__name__,error=str(error)[:4096],ledger=fit.read(RUN/'ledger.json'),wall_seconds=time.monotonic()-start,no_retry=True));return 2
 finally:lock.close()

if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='_worker':raise SystemExit(worker(sys.argv[2],sys.argv[3],sys.argv[4],int(sys.argv[5])))
 parser=argparse.ArgumentParser();parser.add_argument('spec');parser.add_argument('--expected-spec-sha256',required=True);args=parser.parse_args();raise SystemExit(launch(args.spec,args.expected_spec_sha256))
