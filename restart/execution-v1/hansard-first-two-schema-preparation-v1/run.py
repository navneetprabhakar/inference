"""Isolated prefix diagnostic. Nonexecuting by default; no network/ledger."""
import time
START=time.clock_gettime(time.CLOCK_MONOTONIC)
import argparse,hashlib,json,os,re,signal,stat,subprocess,sys
from pathlib import Path
import core
HERE=Path(__file__).resolve().parent
CAP=256000;SLOT=16000
clk=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ident(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def alarm(*a):raise TimeoutError('30sec_shared_deadline')
def required(p):return {str(HERE/n) for n in ['run.py','core.py','checks.py','profile.json','contract.json']}|set(p['metadata_pins'])|set(p['runtime_pins'])
def verify(a):
 if h(HERE/'profile.json')!=a.profile_sha256 or h(HERE/'code-pins.json')!=a.code_pins_sha256:raise ValueError('external_pin')
 p=json.loads((HERE/'profile.json').read_text());pins=json.loads((HERE/'code-pins.json').read_text())['SHA256']
 if set(pins)!=required(p) or sum(Path(f).stat().st_size for f in pins)>4000000:raise ValueError('inventory')
 for f,s in pins.items():
  if h(f)!=s:raise ValueError('pin_changed')
 if str(Path(sys.executable).resolve())!=p['python'] or p['limits']!={'records':2,'compressed_total':2000000,'decoded_per_file':8000000,'line_per_file':4000000,'seconds':30,'RSS_bytes':128000000,'all_output':256000,'whole_record_copy_max':64000}:raise ValueError('fixed_limits_runtime')
 sup=json.loads(Path(p['terminal_supervisor']).read_text());worker=json.loads(Path(p['terminal_worker']).read_text())
 if sup['status']!='TERMINAL_PARTIAL_SOURCE_NO_RETRY' or not sup['worker_reaped'] or worker['completed_files']!=2:raise ValueError('terminal_scope')
 for b in p['inputs']:
  r=json.loads(Path(b['receipt']).read_text());f=Path(b['path'])
  if r['status']!='COMPLETE_EXACT_BYTES_SHA256_RAW_FILE' or r['SHA256']!=b['SHA256'] or r['bytes']!=b['bytes'] or r['source_ordinal']!=b['source_ordinal'] or r['stat']!=b['stat'] or f.is_symlink() or ident(f.stat())!=b['stat']:raise ValueError('completed_file_binding')
 for pid in p['old_PIDs']:
  try:os.kill(pid,0)
  except ProcessLookupError:continue
  raise ValueError('old_owner_PID_present')
 return p

def rss(snapshot,root,child=None):
 rows={}
 for line in snapshot.splitlines():
  if not line.strip():continue
  fs=line.split()
  if len(fs)!=3 or any(not re.fullmatch('[0-9]+',v) for v in fs):raise ValueError('RSS_malformed')
  pid,ppid,n=map(int,fs)
  if pid<=0 or pid==ppid or pid in rows:raise ValueError('RSS_identity')
  rows[pid]=(ppid,n)
 if root not in rows or rows[root][1]<=0:raise ValueError('RSS_missing_root')
 owned={root}
 while True:
  new=owned|{pid for pid,(ppid,n) in rows.items() if ppid in owned}
  if new==owned:break
  owned=new
 if child is not None and (child not in owned or rows[child][1]<=0):raise ValueError('RSS_missing_worker')
 return sum(rows[pid][1]*1024 for pid in owned)
def usage(out):return sum(f.stat().st_size for f in out.iterdir() if f.is_file())
def check(out,start,extra=0):
 if clk()-start>=30:raise TimeoutError('shared_deadline')
 if usage(out)+extra>CAP:raise ValueError('output_cap')
def write(out,name,obj,start,slot=False):
 raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True)+'\n').encode()
 if slot:
  if len(raw)>SLOT:raise ValueError('terminal_slot')
  with (out/name).open('r+b') as f:f.write(raw+b' '*(SLOT-len(raw)));f.flush();os.fsync(f.fileno())
 else:
  check(out,start,len(raw))
  with (out/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def worker(a):
 signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,max(.001,a.start+27-clk()));out=None;owned=False
 try:
  p=verify(a);out=Path(p['output'])
  if os.getppid()!=a.parent:raise ValueError('parent_PID')
  until=min(a.start+27,clk()+2)
  while not (out/'ownership.json').exists() and clk()<until:time.sleep(.01)
  owner=json.loads((out/'ownership.json').read_text())
  if owner!={'supervisor_PID':a.parent,'worker_PID':os.getpid(),'start':a.start,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256}:raise ValueError('ownership')
  owned=True;budget=core.Budget(2000000);records=[]
  for i,b in enumerate(p['inputs']):
   check(out,a.start);path=Path(b['path']);before=ident(path.stat());fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
   try:
    if not stat.S_ISREG(os.fstat(fd).st_mode) or ident(os.fstat(fd))!=before or before!=b['stat']:raise ValueError('source_FD_custody')
    def custody():
     check(out,a.start)
     if ident(os.fstat(fd))!=before or ident(path.stat())!=before:raise ValueError('source_changed')
    raw,receipt=core.first(lambda n:os.read(fd,n),budget,custody);obj=core.parse(raw);info=core.describe(obj);custody()
    if len(raw)<=64000:
     check(out,a.start,len(raw))
     with (out/f'record-{i}.jsonl').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
     info['whole_raw_record_file']=f'record-{i}.jsonl';info['whole_record_retained']=True
    else:info.update({'whole_record_retained':False,'reason':'Whole physical line exceeds64KB copy allowance; metadata+exact locator/hash only; never truncated.'})
    info.update({'source_ordinal':b['source_ordinal'],'source_path':b['path'],'source_SHA256_inherited':b['SHA256'],'prefix':receipt})
    write(out,f'schema-{i}.json',info,a.start);records.append({'source_ordinal':b['source_ordinal'],'line_SHA256':receipt['raw_line_SHA256'],'line_bytes':len(raw),'whole_record_retained':info['whole_record_retained']})
   finally:os.close(fd)
  verify(a);check(out,a.start)
  write(out,'result.json',{'status':'COMPLETE_TWO_BIASED_SCHEMA_PREFIX_EXAMPLES_NO_ADMISSION','records':records,'compressed_total_bytes_read':budget.used,'whole_gzip_CRC_EOF_validation_claimed':False,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256,'new_admitted_documents':0},a.start,True)
 except BaseException as e:
  if owned:write(out,'result.json',{'status':'PARTIAL_DIAGNOSTIC_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000]},a.start,True)
  raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
def supervise(a):
 child=None;created=False;out=None;peak=0
 for sig in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):signal.signal(sig,alarm)
 signal.setitimer(signal.ITIMER_REAL,max(.001,START+27-clk()))
 try:
  p=verify(a);out=Path(p['output'])
  if out.exists() or out.is_symlink():raise ValueError('once_only_output')
  out.mkdir();created=True
  for n in ['result.json','supervisor.json']:(out/n).write_bytes(b' '*SLOT)
  child=subprocess.Popen([sys.executable,'-B',str(HERE/'run.py'),'--worker','--start',str(START),'--parent',str(os.getpid()),'--profile-sha256',a.profile_sha256,'--code-pins-sha256',a.code_pins_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  write(out,'ownership.json',{'supervisor_PID':os.getpid(),'worker_PID':child.pid,'start':START,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256},START)
  while child.poll() is None:
   check(out,START);ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=.5)
   peak=max(peak,rss(ps.stdout,os.getpid(),child.pid if child.poll() is None else None))
   if peak>128000000:raise ValueError('128MB_RSS')
   time.sleep(.05)
  child.wait(timeout=1);check(out,START)
  ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=.5)
  peak=max(peak,rss(ps.stdout,os.getpid()))
  if peak>128000000:raise ValueError('terminal_128MB_RSS')
  result=json.loads((out/'result.json').read_text());ok=child.returncode==0 and result.get('status')=='COMPLETE_TWO_BIASED_SCHEMA_PREFIX_EXAMPLES_NO_ADMISSION'
  write(out,'supervisor.json',{'status':'COMPLETE_SCHEMA_DIAGNOSTIC_NO_ADMISSION' if ok else 'PARTIAL_DIAGNOSTIC_NO_RETRY','worker_reaped':True,'worker_exit':child.returncode,'peak_observed_RSS_bytes':peak,'elapsed_seconds':clk()-START,'result_SHA256':h(out/'result.json'),'output_bytes':usage(out)},START,True)
  return 0 if ok else 1
 except BaseException as e:
  signal.setitimer(signal.ITIMER_REAL,max(.001,START+30-clk()))
  if child is not None:
   if child.poll() is None:
    try:os.killpg(child.pid,signal.SIGKILL)
    except ProcessLookupError:pass
   child.wait(timeout=1)
  if created:write(out,'supervisor.json',{'status':'PARTIAL_DIAGNOSTIC_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'worker_reaped':child is None or child.poll() is not None,'elapsed_seconds':clk()-START},START,True)
  raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--worker',action='store_true');ap.add_argument('--profile-sha256',required=True);ap.add_argument('--code-pins-sha256',required=True);ap.add_argument('--start',type=float);ap.add_argument('--parent',type=int);a=ap.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a);print('STATIC_ONLY_NO_GZIP_SOURCE_READ')
