"""Prospective sequential benchmark control; pure stdlib plus existing watchdog.

No default activation, model imports, conversion, or worker execution at import.
"""
import stat
import fcntl,hashlib,json,math,os,re,subprocess,time,sys,argparse
from pathlib import Path
import own_base_dev_run as runtime
ROOT=Path(__file__).resolve().parent
PERIOD_LIMITS=dict(correctness=2700.,warmup=900.,measured=5400.,resume=900.,overhead=900.)
TOKEN_LIMIT=24993792;OUTPUT_LIMIT=4*1024**3;DISK_FLOOR=20*1024**3

def require(value,message):
 if not value:raise runtime.RunnerStop(message)
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def read_ledger(run):
 value=json.loads((Path(run)/'benchmark-ledger.json').read_text());h=value.pop('sha256');require(hashlib.sha256(canonical(value)).hexdigest()==h,'ledger checksum');return value
def write_ledger(run,value):
 value=dict(value);value['sha256']=hashlib.sha256(canonical(value)).hexdigest();runtime.atomic(Path(run)/'benchmark-ledger.json',value)
def initialize(spec,run,spec_sha):
 path=Path(run)/'benchmark-ledger.json';require(not path.exists(),'existing ledger refused')
 prior=spec.get('prior_attempt');periods={p:0. for p in PERIOD_LIMITS}
 if prior:
  periods.update(prior['period_seconds']);periods['overhead']+=prior['elapsed_wall_seconds']-prior['worker_active_seconds']
 write_ledger(run,dict(schema=1,state='prepared',spec_sha256=spec_sha,reserved_targets=prior['reserved_targets'] if prior else 0,committed_targets=prior['committed_targets'] if prior else 0,pending=None,operations=0,period_seconds=periods,active_seconds=prior['elapsed_wall_seconds'] if prior else 0.,phase=None,completed_phases=[],created_wall=time.time()))
def output_bytes(run):
 root=Path(run).absolute();require(root.is_dir() and not root.is_symlink(),'owned output root required');total=0
 def fail(error):raise error
 for directory,dirs,files in os.walk(root,onerror=fail):
  for name in dirs+files:
   path=Path(directory)/name
   try:info=path.lstat()
   except FileNotFoundError:
    if name not in files:raise
    # Only an entry already enumerated under this still-existing owned root.
    # Worker atomic replacement/cleanup may remove it between walk and stat.
    require(root.is_dir() and not root.is_symlink() and path.parent.resolve().is_relative_to(root.resolve()),'output root changed during scan')
    continue
   require(not stat.S_ISLNK(info.st_mode),'benchmark output symlink')
   if name in files:total+=info.st_size
 return total

def storage_check(spec,run):
 import shutil
 priorbytes=output_bytes(spec['prior_attempt']['run']) if 'prior_attempt' in spec else 0
 require(output_bytes(run)+priorbytes<=OUTPUT_LIMIT,'4GiB aggregate benchmark disk ceiling')
 require(shutil.disk_usage(run).free>=DISK_FLOOR,'20GiB disk floor')
 require(not any(Path(p).exists()for p in spec['stop_paths']),'explicit STOP')

def swap_bytes(timeout=2):
 text=subprocess.check_output(['sysctl','-n','vm.swapusage'],text=True,timeout=timeout);match=re.search(r'used = ([\d.]+)([KMG])',text)
 require(match,'swap telemetry unavailable');return float(match[1])*{'K':1024,'M':1024**2,'G':1024**3}[match[2]]

def require_ac():
 text=subprocess.check_output(['pmset','-g','batt'],text=True,timeout=2)
 require("'AC Power'"in text,'AC power required')

class WorkerBudget:
 """Single owned worker; durable cumulative attempts, never refunded.

 Constructor assumes ticket was consumed through runtime.consume_ticket(FIFO).
 CPU tests may supply now and disable OS probes; production CLI must not expose
 those injectable controls. No framework/GPU imports occur here.
 """
 def __init__(self,spec,run,phase,ticket,*,now=time.monotonic,probe=True):
  self.spec=spec;self.run=Path(run);self.phase=phase;self.ticket=ticket;self.now=now;self.probe=probe
  self.current='correctness'if phase.startswith('A')else'resume'if phase.startswith('D')else'overhead'
  self.last=now();self.period_started=self.last;self.last_probe=-math.inf;self.local_periods={p:0. for p in PERIOD_LIMITS};self.rss_bad=0;self.swap_bad=0
  require(ticket['watchdog_pid']==os.getppid() and ticket['phase']==phase,'worker ticket phase/parent')
  value=read_ledger(run);require(value['spec_sha256']==ticket['spec_sha256'] and value['pending']is None,'spec or pending mismatch')
  require(value['phase']==phase and value['state']=='running','controller phase authorization')
  self.baseline_swap=json.loads((self.run/'launch.json').read_text())['baseline_swap_bytes'];self.check()
 def _account(self,value):
  now=self.now();elapsed=max(0.,now-self.last);self.last=now;value['period_seconds'][self.current]+=elapsed;value['active_seconds']+=elapsed;self.local_periods[self.current]+=elapsed
  require(value['active_seconds']<=10800 and all(value['period_seconds'][k]<=v for k,v in PERIOD_LIMITS.items()),'aggregate phase/active time ceiling')
  if self.current in ('warmup','measured'):require(self.local_periods[self.current]<=({'warmup':300,'measured':1800}[self.current]),'per-runtime time ceiling')
  return value
 def check(self,force=False):
  require(runtime.remaining(self.ticket)>0 and time.time()-self.ticket['benchmark_wall_started']<21600,'worker/global calendar deadline')
  value=self._account(read_ledger(self.run));write_ledger(self.run,value)
  (self.run/'phases'/self.phase/'heartbeat').write_text(str(time.monotonic()))
  if self.probe:storage_check(self.spec,self.run)
  if self.probe and (force or self.now()-self.last_probe>=30):
   self.last_probe=self.now();storage_check(self.spec,self.run);require_ac()
   state=runtime.apple_thermal();require(state in range(4) and state<2,'thermal unavailable/serious')
   rss=runtime.group_rss(os.getpgrp());swap=swap_bytes()
   self.rss_bad=self.rss_bad+1 if rss>18*1024**3 else 0;self.swap_bad=self.swap_bad+1 if swap-self.baseline_swap>1024**3 else 0
   require(self.rss_bad<2 and self.swap_bad<2,'repeated RSS/swap threshold')
   self._event('resources',rss=rss,swap_growth=swap-self.baseline_swap,thermal=state)
 def _event(self,event,**data):
  payload=json.dumps(dict(event=event,phase=self.phase,period=self.current,wall=time.time(),**data),allow_nan=False)+'\n'
  with (self.run/'benchmark-events.jsonl').open('a')as f:f.write(payload);f.flush();os.fsync(f.fileno())
 def period(self,name):
  require(name in PERIOD_LIMITS,'unknown benchmark period');self.check();self.current=name;self.period_started=self.now();self._event('period_started')
 def reserve(self,targets,kind):
  require(type(targets)==int and targets>0 and isinstance(kind,str) and kind,'valid target attempt required');self.check();value=read_ledger(self.run)
  require(value['pending']is None,'unfinished operation');require(value['reserved_targets']+targets<=TOKEN_LIMIT,'aggregate attempted target ceiling')
  value['reserved_targets']+=targets;value['operations']+=1;value['pending']=dict(phase=self.phase,period=self.current,targets=targets,kind=kind,operation=value['operations']);write_ledger(self.run,value);self._event('reserved',pending=value['pending'],reserved_targets=value['reserved_targets'])
 def commit(self,targets,kind,metrics):
  self.check();value=read_ledger(self.run);pending=value['pending'];require(pending and pending['phase']==self.phase and pending['targets']==targets and pending['kind']==kind,'commit differs from reservation')
  canonical(metrics);value['committed_targets']+=targets;value['pending']=None;write_ledger(self.run,value);self._event('committed',operation=pending['operation'],targets=targets,kind=kind,metrics=metrics)
 def memory(self,active,cache,driver,**extra):
  require(isinstance(active,(int,float)) and math.isfinite(active) and 0<=active<12*1024**3,'active GPU allocation threshold/unavailable')
  require(cache is None or isinstance(cache,(int,float))and math.isfinite(cache)and cache>=0,'cache telemetry')
  require(driver is None or isinstance(driver,(int,float))and math.isfinite(driver)and driver>=0,'driver telemetry')
  self._event('gpu_memory',active=active,cache=cache,driver=driver,driver_unavailable=driver is None,**extra)

COMMANDS={'source-convert','logits-reference','logits-compare','gradients-reference','gradients-compare','updates-reference','updates-compare','sustained','resume-reference','resume-pause','resume-check','cleanup'}
RUNTIMES={'torch-cpu','torch-mps-fp32','mlx-gpu-fp32','torch-mps-bf16'}

def expected_phase_plan():
 phases=[]
 def add(id,command,runtime='torch-cpu',artifact='neutral-source.npz',microbatch=None):phases.append(dict(id=id,command=command,runtime=runtime,artifact=artifact,microbatch=microbatch))
 add('A00-source','source-convert')
 for mb in (0,1):
  for kind in ('logits','gradients'):
   artifact=f'ref-mb{mb}-{kind}.npz';prefix=f'A{mb}{kind}'
   add(prefix+'-cpu',kind+'-reference',artifact=artifact,microbatch=mb)
   for runtime in ('torch-mps-fp32','mlx-gpu-fp32'):add(prefix+'-'+runtime,kind+'-compare',runtime,artifact,mb)
   add(prefix+'-cleanup','cleanup',artifact=artifact)
 add('Aupdates-cpu','updates-reference',artifact='ref-updates.npz')
 for runtime in ('torch-mps-fp32','mlx-gpu-fp32'):add('Aupdates-'+runtime,'updates-compare',runtime,'ref-updates.npz')
 add('Aupdates-cleanup','cleanup',artifact='ref-updates.npz')
 for i,runtime in enumerate(('torch-mps-fp32','mlx-gpu-fp32','torch-mps-bf16')):add('BC'+str(i)+'-'+runtime,'sustained',runtime,artifact=f'sustained-{i}.npz')
 for command in ('resume-reference','resume-pause','resume-check'):add('D'+command,command,'mlx-gpu-fp32',artifact='resume-reference.npz')
 return phases

def validate_prior_attempt(prior):
 run=ROOT/'runs/own-base-mlx-full-benchmark-01';require(prior['run']==str(run),'fixed first attempt')
 expected={'launch.json','terminal.json','benchmark-ledger.json','spec.json','phases/A0gradients-cleanup/watchdog.json'}
 require(set(prior['files'])==expected,'complete prior failure evidence')
 for relative,pin in prior['files'].items():
  path=run/relative;require(path.stat().st_size==pin['bytes'] and runtime.checksum(path)==pin['sha256'],'prior evidence changed')
 launch=json.loads((run/'launch.json').read_text());terminal=json.loads((run/'terminal.json').read_text());ledger=read_ledger(run);watchdog=json.loads((run/'phases/A0gradients-cleanup/watchdog.json').read_text())
 require(terminal['state']=='incomplete' and ledger['state']=='incomplete' and ledger['phase']=='A0gradients-cleanup' and ledger['pending'] is None,'expected infrastructure failure only')
 require(ledger['reserved_targets']==ledger['committed_targets']==9216,'prior attempts exact')
 for key in ('reserved_targets','committed_targets','period_seconds'):require(prior[key]==ledger[key],'prior budget mismatch')
 require(prior['worker_active_seconds']==ledger['active_seconds'] and prior['launch_wall']==launch['started_wall'],'prior time mismatch')
 require(prior['terminal_mtime_ns']==(run/'terminal.json').stat().st_mtime_ns,'prior terminal time changed')
 elapsed=(run/'terminal.json').stat().st_mtime-launch['started_wall'];require(prior['elapsed_wall_seconds']==elapsed and elapsed>=ledger['active_seconds'],'conservative prior wall charge')
 require(watchdog.get('exit_code')==-15 and watchdog.get('watchdog_reason')=="[Errno 2] No such file or directory: '"+str(run/'artifacts/ref-mb0-gradients.json')+"'",'only reviewed cleanup race permits rerun')
 return prior

def validate_spec(spec):
 require(spec.get('schema')==1 and spec.get('state')=='reviewed_for_full_model_feasibility','reviewed benchmark spec required')
 validate_prior_attempt(spec['prior_attempt'])
 require(spec['limits']==dict(active_seconds=10800,calendar_seconds=21600,attempted_targets=TOKEN_LIMIT,output_bytes=OUTPUT_LIMIT,free_disk_bytes=DISK_FLOOR,rss_bytes=18*1024**3,swap_growth_bytes=1024**3,gpu_active_bytes=12*1024**3,telemetry_seconds=30,max_retries=0),'fixed benchmark limits')
 require(spec['period_limits']==PERIOD_LIMITS,'phase periods differ')
 run=Path(spec['run']);require(run==ROOT/'runs/own-base-mlx-full-benchmark-02' and not run.is_symlink(),'fixed benchmark output')
 require(spec['source_spec']['source_offset']==99999744 and spec['slice_targets']==16777216 and spec['targets_per_update']==8192,'fixed source slice/batch')
 require(spec['configuration']==dict(microbatch=2,length=512,accumulation=8,lr=6e-5),'unchanged workload')
 requiredstops={str(ROOT/'runs/own-base-mlx-full-benchmark-01/STOP'),str(ROOT/'runs/STOP'),str(run/'STOP'),str(ROOT/'runs/own-base-foundation-01/STOP')}|{str(ROOT/f'runs/optimizer-ablation-v1-{x}/STOP')for x in ('preserve-095','reset-095','reset-scaled')}
 require(requiredstops<=set(spec['stop_paths']),'inherited STOPs')
 require(spec['driver_telemetry_policy']=='MLX0.32.4 null with reason; mandatory active/cache/peak and OS guards','explicit driver limitation')
 require(spec['worker']=='mlx_full_benchmark_worker_v2.py' and 'mlx_full_benchmark_control_v2.py'in spec['code_sha256'] and spec['worker']in spec['code_sha256'],'controller and worker pins')
 for name,h in spec['code_sha256'].items():
  path=(ROOT/name).resolve();require(path.is_relative_to(ROOT)and runtime.checksum(path)==h,'changed code: '+name)
 for name,p in spec['python'].items():require(name in ('torch','mlx')and Path(p).is_file(),'existing environment only')
 phases=spec['phases'];require(phases and len(phases)<=40 and len({p['id']for p in phases})==len(phases),'bounded unique phases')
 sustained=[]
 for phase in phases:
  require(re.fullmatch('[A-D][a-zA-Z0-9_-]+',phase['id']),'phase ID');require(phase['command']in COMMANDS and phase['runtime']in RUNTIMES,'known phase command/runtime')
  require(phase.get('microbatch')in (None,0,1),'microbatch index');require(re.fullmatch('[a-zA-Z0-9_.-]+',phase['artifact'])and phase['artifact']not in ('.','..'),'disposable artifact basename')
  if phase['command']=='sustained':sustained.append(phase['runtime'])
 require(sustained==['torch-mps-fp32','mlx-gpu-fp32','torch-mps-bf16'],'fixed sustained order')
 require(phases==expected_phase_plan(),'fixed semantic phase plan/order/artifacts')
 require(spec['tolerances']==dict(causal_prefix_max=1e-6,loss_abs=1e-4,logit_rms=1e-4,logit_max=1e-3,gradient_relative_l2=1e-3,gradient_max=1e-4,norm_relative=1e-3,weight_max=5e-5,update_delta_relative=0.02,moment_max=1e-5,resume_exact=True),'fixed correctness tolerances')
 return spec

def validate_phase_result(phase,output):
 require(output.get('state')=='complete' and output.get('phase')==phase['id'] and output.get('command')==phase['command'] and output.get('runtime')==phase['runtime'],'worker phase proof mismatch')
 if phase['command'] in ('logits-compare','gradients-compare','updates-compare','resume-check'):require(output.get('correctness_pass') is True,'correctness failed')
 if phase['command']=='sustained':
  require(output.get('prescribed_window_seconds')==1800 and output.get('observed_window_seconds',0)>=1800 and 0<output.get('last_commit_seconds',float('inf'))<=1800 and output.get('warmup_updates',0)>=10 and output.get('settling_updates')==2 and type(output.get('measured_updates'))==int and 0<output['measured_updates']<=2046 and output.get('slice_exhausted') is False,'sustained phase incomplete')
 return output

def admission(spec,run):
 import shutil
 parentbytes=spec['source_spec']['parent']['bytes'];estimate=math.ceil(1.1*parentbytes)+16*1024**2;forecast=2*estimate+512*1024**2+256*1024**2+output_bytes(spec['prior_attempt']['run'])
 require(forecast<=OUTPUT_LIMIT,'forecast exceeds4GiB');require(shutil.disk_usage(ROOT).free>=DISK_FLOOR+forecast,'forecast below20GiBfloor');require(not Path(run).exists(),'existing benchmark refused');require_ac();return forecast

def launch(spec_path,expected):
 wall=time.time();mono=time.monotonic();path=Path(spec_path).resolve()
 require(path.is_file()and path.stat().st_size<1024**2 and runtime.checksum(path)==expected,'exact bounded spec required')
 spec=validate_spec(json.loads(path.read_text()));prior=spec['prior_attempt'];run=Path(spec['run']);forecast=admission(spec,run)
 lock=(ROOT/'runs/mps.lock').open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 run.mkdir();(run/'phases').mkdir();(run/'artifacts').mkdir();runtime.atomic(run/'spec.json',spec);runtime.atomic(run/'launch.json',dict(started_wall=wall,started_monotonic=mono,baseline_swap_bytes=swap_bytes(),forecast_bytes=forecast,parent_pid=os.getpid(),spec_sha256=expected));initialize(spec,run,expected)
 try:
  for phase in spec['phases']:
   storage_check(spec,run);value=read_ledger(run);require(value['pending']is None,'unfinished operation prevents continuation')
   activeleft=10800-prior['elapsed_wall_seconds']-(time.monotonic()-mono);calendarleft=21600-(time.time()-prior['launch_wall'])
   prefix=phase['id'][0];period='correctness'if prefix=='A'else'resume'if prefix=='D'else None
   phaseleft=PERIOD_LIMITS[period]-value['period_seconds'][period]if period else 300+1800+300
   seconds=min(activeleft,calendarleft,phaseleft);require(seconds>10,'remaining budget insufficient')
   phaseout=run/'phases'/phase['id'];phaseout.mkdir();value.update(state='running',phase=phase['id']);write_ledger(run,value)
   ticket=runtime.make_ticket(seconds,expected);ticket.update(phase=phase['id'],benchmark_wall_started=prior['launch_wall'])
   baseline=json.loads((run/'launch.json').read_text())['baseline_swap_bytes'];last=-math.inf;rssbad=swapbad=0
   def check(pid,available):
    nonlocal last,rssbad,swapbad
    storage_check(spec,run)
    if time.monotonic()-last>=30:
     last=time.monotonic();require_ac();thermal=runtime.apple_thermal();require(thermal in range(4)and thermal<2,'mandatory thermal guard');rss=runtime.group_rss(pid,timeout=min(2,max(.01,available)));swap=swap_bytes(min(2,max(.01,available)))-baseline
     rssbad=rssbad+1 if rss>18*1024**3 else 0;swapbad=swapbad+1 if swap>1024**3 else 0;require(rssbad<2 and swapbad<2,'repeated parent RSS/swap guard')
   python=spec['python']['mlx'if phase['runtime']=='mlx-gpu-fp32'else'torch']
   def command(fd):
    return [python,str(ROOT/spec['worker']),'--spec',str(path),'--run',str(run),'--phase',phase['id'],'--ticket-fd',str(fd)]

   result=runtime.supervise(command,phaseout,ticket=ticket,heartbeat_seconds=90,grace_seconds=10,max_rss_bytes=2**63,check=check)
   runtime.atomic(phaseout/'watchdog.json',result);require(result['exit_code']==0 and not result['watchdog_reason']and result['within_deadline'],'phase incomplete; no automaticretry')
   output=json.loads((phaseout/'result.json').read_text());validate_phase_result(phase,output)
   value=read_ledger(run);require(value['pending']is None,'pending operation atphaseend');value['completed_phases'].append(dict(id=phase['id'],result_sha256=runtime.checksum(phaseout/'result.json'),watchdog_sha256=runtime.checksum(phaseout/'watchdog.json')));write_ledger(run,value)
  value=read_ledger(run);value.update(state='completed_execution_feasibility_not_migration',phase=None);write_ledger(run,value);runtime.atomic(run/'terminal.json',dict(state=value['state'],ledger_sha256=runtime.checksum(run/'benchmark-ledger.json'),wall_seconds=time.time()-wall,automatic_retries=0));return 0
 except BaseException as error:
  value=read_ledger(run);value.update(state='incomplete',error_type=type(error).__name__,error=str(error)[:4096]);write_ledger(run,value);runtime.atomic(run/'terminal.json',dict(state='incomplete',error_type=type(error).__name__,error=str(error)[:4096],pending=value['pending'],automatic_retries=0));return 2
 finally:lock.close()

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('spec');parser.add_argument('--expected-spec-sha256',required=True);args=parser.parse_args();raise SystemExit(launch(args.spec,args.expected_spec_sha256))
