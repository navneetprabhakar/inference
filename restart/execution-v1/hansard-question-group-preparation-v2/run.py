"""Bounded reviewed-subset development only; nonexecuting by default."""
import time,signal
START=time.clock_gettime(time.CLOCK_MONOTONIC)
def alarm(*a):raise TimeoutError('absolute_development_deadline')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,55)
import argparse,hashlib,json,os,stat,subprocess,sys,shutil
from pathlib import Path
import core,tree_size
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent/'m2-intake';CAP=5000000;SLOT=64000;FREE=53474836480
clk=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
def h(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ident(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def required(p):return {str(HERE/n) for n in ['run.py','core.py','checks.py','tree_size.py','profile.json','contract.json']}|set(p['metadata_inputs'])|set(p['runtime_inputs'])
def verify(a):
 if h(HERE/'profile.json')!=a.profile_sha256 or h(HERE/'code-pins.json')!=a.code_pins_sha256:raise ValueError('external_pins')
 p=json.loads((HERE/'profile.json').read_text());pins=json.loads((HERE/'code-pins.json').read_text())['SHA256']
 if set(pins)!=required(p) or p['limits']!={'sources':2,'source_each':200000,'total_source_bytes':131539,'output_bytes':5000000,'worker_seconds':55,'external_seconds':60,'RSS_bytes':1000000000}:raise ValueError('exact_inventory_limits')
 for f,d in pins.items():
  if h(f)!=d:raise ValueError('changed_pin')
 if str(Path(sys.executable).resolve())!=p['python']:raise ValueError('runtime')
 records=json.loads(Path(p['capture_records']).read_text());by={(x['source_id'],x['ordinal']):x for s in records['sources'] for x in s['captures']}
 if [(r['source_id'],r['ordinal']) for r in p['sources']]!=[(1,2770),(1,3857)]:raise ValueError('frozen_development_subset')
 for r in p['sources']:
  x=by[(r['source_id'],r['ordinal'])];f=Path(r['path'])
  if x['native_subsource']!='uk-hansard-lords-written-answers' or x['text_SHA256']!=r['SHA256'] or x['text_UTF8_bytes']!=r['bytes'] or f.is_symlink() or ident(f.stat())!=r['stat']:raise ValueError('source_metadata_custody')
 return p

def rss(snapshot,root,child):
 rows={}
 for line in snapshot.splitlines():
  v=line.split()
  if not v:continue
  if len(v)!=3 or any(not x.isascii() or not x.isdigit() for x in v):raise ValueError('RSS_malformed')
  pid,ppid,n=map(int,v)
  if pid<=0 or pid==ppid or pid in rows:raise ValueError('RSS_identity')
  rows[pid]=(ppid,n)
 if root not in rows or rows[root][1]<=0:raise ValueError('RSS_missing_root')
 owned={root}
 while True:
  nxt=owned|{k for k,v in rows.items() if v[0] in owned}
  if nxt==owned:break
  owned=nxt
 if child is not None and (child not in owned or rows[child][1]<=0):raise ValueError('RSS_missing_worker')
 return sum(rows[x][1]*1024 for x in owned)
def guard(out,start,extra=0):
 if clk()>=start+55:raise TimeoutError('worker_absolute_deadline')
 n=tree_size.census(out);remaining=max(0,CAP-n)
 if n+extra>CAP or tree_size.census(ROOT)+remaining>64000000000 or shutil.disk_usage(ROOT).free<FREE+remaining:raise ValueError('output_combined_disk_guard')
def write(out,name,obj,start,slot=False):
 raw=(json.dumps(obj,ensure_ascii=False,sort_keys=True)+'\n').encode();guard(out,start,0 if slot else len(raw))
 if slot:
  if len(raw)>SLOT:raise ValueError('terminal_slot')
  with (out/name).open('r+b') as f:f.write(raw+b' '*(SLOT-len(raw)));f.flush();os.fsync(f.fileno())
 else:
  with (out/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def worker(a):
 signal.setitimer(signal.ITIMER_REAL,max(.001,a.start+55-clk()));p=verify(a);out=Path(p['output']);rows=[]
 if os.getppid()!=a.parent:raise ValueError('owner_parent')
 until=min(a.start+55,clk()+2)
 while not (out/'ownership.json').exists() and clk()<until:time.sleep(.01)
 if json.loads((out/'ownership.json').read_text())!={'supervisor_PID':a.parent,'worker_PID':os.getpid(),'start':a.start,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256}:raise ValueError('ownership')
 try:
  for r in p['sources']:
   guard(out,a.start);path=Path(r['path']);fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
   try:
    before=os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or ident(before)!=r['stat'] or ident(path.stat())!=r['stat']:raise ValueError('source_FD_custody')
    raw=b''
    while len(raw)<=r['bytes']:
     b=os.read(fd,min(65536,r['bytes']+1-len(raw)))
     if not b:break
     raw+=b;guard(out,a.start)
    if len(raw)!=r['bytes'] or hashlib.sha256(raw).hexdigest()!=r['SHA256'] or ident(os.fstat(fd))!=r['stat'] or ident(path.stat())!=r['stat']:raise ValueError('source_exact_EOF_SHA_stat')
   finally:os.close(fd)
   text=raw.decode('utf-8',errors='strict');parts=core.segment(text)
   result={'source_id':r['source_id'],'ordinal':r['ordinal'],'parent_text_SHA256':r['SHA256'],'parent_current_representation_hold':r['known_parent_hold'],'family':'WHOLE_NATIVE_SOURCE_PARENT_DAY_ALIASES_RETAINED_UNCLEARED','parts':parts,'exact_inverse_UTF8_SHA256':hashlib.sha256(''.join(x['raw_text'] for x in parts).encode()).hexdigest(),'new_admissions':0}
   name=f"source-{r['source_id']}-row-{r['ordinal']:06}-parts.json";write(out,name,result,a.start);rows.append({'source_id':r['source_id'],'ordinal':r['ordinal'],'parts':len(parts),'candidate_groups':sum(x['kind']=='QUESTION_ANSWER_GROUP' for x in parts),'file':name,'SHA256':h(out/name)})
  verify(a);write(out,'result.json',{'status':'COMPLETE_TWO_REVIEWED_SOURCE_DEVELOPMENT_PARTITIONS_NO_ADMISSION','sources':rows,'source_bytes':sum(r['bytes'] for r in p['sources']),'whole_source_quality_verdicts_preserved':True,'daughter_group_quality_language_count_rights_custody':'ALL_UNCLEARED','new_admissions':0},a.start,True)
 except BaseException as exc:
  raw=(json.dumps({'status':'PARTIAL_SOURCE_PARTITION_NO_RETRY_NO_ADMISSION','error_class':type(exc).__name__,'error':str(exc)[:1000],'completed_source_count':len(rows),'new_admissions':0})+'\n').encode()
  with (out/'result.json').open('r+b') as f:f.write(raw+b' '*(SLOT-len(raw)));f.flush();os.fsync(f.fileno())
  raise

def supervise(a):
 child=None;created=False;out=None;peak=0
 for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,alarm)
 try:
  p=verify(a);out=Path(p['output'])
  if out.exists() or out.is_symlink():raise ValueError('once_only_output')
  if tree_size.census(ROOT)+CAP>64000000000 or shutil.disk_usage(ROOT).free<FREE+CAP:raise ValueError('combined_disk_preflight')
  out.mkdir();created=True
  for n in ['result.json','supervisor.json']:(out/n).write_bytes(b' '*SLOT)
  cmd=[sys.executable,'-B',str(HERE/'run.py'),'--worker','--start',str(START),'--parent',str(os.getpid()),'--profile-sha256',a.profile_sha256,'--code-pins-sha256',a.code_pins_sha256]
  child=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  write(out,'ownership.json',{'supervisor_PID':os.getpid(),'worker_PID':child.pid,'start':START,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256},START)
  while child.poll() is None:
   guard(out,START);snap=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
   if len(snap.stdout)>1048576:raise ValueError('RSS_snapshot_bytes')
   if child.poll() is None:peak=max(peak,rss(snap.stdout,os.getpid(),child.pid))
   if peak>1000000000:raise ValueError('RSS_cap')
   time.sleep(.05)
  code=child.wait(timeout=1)
  if code:raise ValueError('worker_failed_exit_'+str(code))
  verify(a);write(out,'supervisor.json',{'status':'COMPLETE_DEVELOPMENT_ONLY','worker_reaped':True,'worker_PID':child.pid,'elapsed_seconds':clk()-START,'peak_observed_RSS':peak,'result_SHA256':h(out/'result.json'),'output_bytes':tree_size.census(out),'new_admissions':0},START,True);return 0
 except BaseException as e:
  signal.setitimer(signal.ITIMER_REAL,max(.001,START+60-clk()))
  if child is not None and child.poll() is None:
   os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=2)
  if created:
   raw=(json.dumps({'status':'PARTIAL_NO_RETRY_NO_ADMISSION','error':type(e).__name__+':'+str(e)[:1000],'worker_reaped':child is None or child.poll() is not None})+'\n').encode()
   with (out/'supervisor.json').open('r+b') as f:f.write(raw+b' '*(SLOT-len(raw)));f.flush();os.fsync(f.fileno())
  raise
 finally:
  if child is not None and child.poll() is None:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=2)
  signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--worker',action='store_true');ap.add_argument('--start',type=float);ap.add_argument('--parent',type=int);ap.add_argument('--profile-sha256',required=True);ap.add_argument('--code-pins-sha256',required=True);a=ap.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a);signal.setitimer(signal.ITIMER_REAL,0);print('STATIC_ONLY_NO_SOURCE_BODY_READ_NETWORK_OR_LEDGER')
