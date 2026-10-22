"""Reused bounded supervisor/strict RSS and fixed terminal slots; no source parser."""
import json,os,pathlib,shutil,signal,subprocess,sys,time
LIMITS={"worker_seconds":110,"external_seconds":120,"output_bytes":32000000,"tree_RSS_bytes":1000000000}
SLOTS={"result.json":32768,"supervisor.json":32768}
def outsize(out):return sum(p.stat().st_size for p in out.rglob('*') if p.is_file())

def write(out,name,raw):
 if outsize(out)+len(raw)>LIMITS['output_bytes']-65536:raise ValueError('prewrite_output_cap')
 with (out/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())

def data(obj):return (json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()

def slot(out,name,obj):
 raw=data(obj);n=SLOTS[name]
 if len(raw)>n:raise ValueError('terminal_slot')
 with (out/name).open('r+b') as f:f.write(raw+b' '*(n-len(raw)));f.flush();os.fsync(f.fileno())

def arm(seconds):
 def stop(s,f):raise TimeoutError('deadline_or_signal')
 for s in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:signal.signal(s,stop)
 if seconds<=0:raise TimeoutError('already_expired')
 signal.setitimer(signal.ITIMER_REAL,seconds)

def tree_rss(pid):
 v=subprocess.run(['ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=2).stdout
 rows={}
 for line in v.splitlines():
  f=line.split()
  if len(f)!=3:raise ValueError('RSS_malformed')
  i,parent,rss=map(int,f)
  if i in rows or i<=0 or parent<0 or rss<0 or i==parent:raise ValueError('RSS_invalid')
  rows[i]=(parent,rss)
 if pid not in rows or rows[pid][1]<=0:raise ValueError('RSS_root_missing')
 found={pid}
 while True:
  more={i for i,(parent,rss) in rows.items() if parent in found}
  if more<=found:break
  found|=more
 return sum(rows[i][1]*1024 for i in found)

def supervise(out,command,preflight=None,started=None):
 start=time.clock_gettime(time.CLOCK_MONOTONIC) if started is None else started;child=None;peak=0;arm(LIMITS['external_seconds']-(time.clock_gettime(time.CLOCK_MONOTONIC)-start))
 try:
  if preflight:preflight()
  out.mkdir(exist_ok=False)
  for name,n in SLOTS.items():(out/name).write_bytes(b' '*n)
  if shutil.disk_usage(out).free<53474836480+LIMITS['output_bytes']:raise ValueError('weights_scratch_freefloor')
  cmd=command(start)
  with (out/'worker.log').open('xb') as log:
   child=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   write(out,'ownership.json',data({'supervisor_PID':os.getpid(),'worker_PID':child.pid,'shared_start':start}))
   while child.poll()is None:
    peak=max(peak,tree_rss(os.getpid()))
    if peak>LIMITS['tree_RSS_bytes'] or outsize(out)>LIMITS['output_bytes']:raise ValueError('resource_bound')
    time.sleep(.05)
   rc=child.wait()
  if time.clock_gettime(time.CLOCK_MONOTONIC)-start>=LIMITS['external_seconds']:raise TimeoutError('external_elapsed_before_COMPLETE')
  peak=max(peak,tree_rss(os.getpid()))
  if peak>LIMITS['tree_RSS_bytes'] or outsize(out)>LIMITS['output_bytes']:raise ValueError('final_resource_bound')
  result=json.loads((out/'result.json').read_text())
  if rc or not result['status'].startswith('COMPLETE'):raise ValueError('worker_not_complete')
  slot(out,'supervisor.json',{'status':'COMPLETE','child_reaped':True,'child_pid':child.pid,'returncode':rc,'peak_tree_RSS_bytes':peak,'elapsed_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-start,'output_bytes':outsize(out)})
 except BaseException as e:
  if child is not None and child.poll()is None:
   os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=3)
  if (out/'supervisor.json').exists():slot(out,'supervisor.json',{'status':'PARTIAL_NO_RETRY','child_reaped':child is None or child.poll()is not None,'error':type(e).__name__+':'+str(e)})
  raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
