"""Once-only300 native-rsync source profile; no model/training/admission."""
import time,signal
START=time.clock_gettime(time.CLOCK_MONOTONIC)
def alarm(*a):raise TimeoutError('whole_profile_absolute_deadline_or_signal')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,21595)
import argparse,hashlib,json,os,shutil,stat,subprocess,sys,threading
from pathlib import Path
import controller,transport,validate,tree_size,attempt_deadline
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';FREE=53474836480
LIMITS={'books':300,'file_bytes':2400000,'received_bytes_each':2500000,'received_total':750000000,'output_bytes':800000000,'connections':300,'pace_seconds':2,'per_file_external_seconds':60,'per_file_active_seconds':55,'profile_external_seconds':21600,'RSS_bytes':1000000000}
SLOTS={'result.json':1048576,'inventory.json':1048576,'controller.json':32768,'ownership.json':32768}
clk=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def small(path):
 p=Path(path)
 if p.is_symlink() or not stat.S_ISREG(p.stat().st_mode) or p.stat().st_size>16000000:raise ValueError('bounded_regular_metadata')
 b=p.read_bytes()
 if len(b)>16000000:raise ValueError('metadata_limit')
 return b
def required(profile):return {str(HERE/n) for n in ['run.py','controller.py','transport.py','validate.py','sandbox.py','tree_size.py','checks.py','attempt_deadline.py','profile.json','contract.json']}|set(profile['input_paths'])
def verify(a):
 if sha(HERE/'profile.json')!=a.profile_sha256 or sha(HERE/'code-pins.json')!=a.code_pins_sha256:raise ValueError('external_pins')
 p=json.loads(small(HERE/'profile.json'));pins=json.loads(small(HERE/'code-pins.json'))['SHA256']
 if set(pins)!=required(p) or p['limits']!=LIMITS:raise ValueError('exact_inventory_limits')
 for path,digest in pins.items():
  if sha(path)!=digest:raise ValueError('frozen_input_changed')
 if str(Path(sys.executable).resolve())!=p['python'] or p['host']!='rsync.ibiblio.org' or p['port']!=873:raise ValueError('runtime_fixedhost')
 frozen=json.loads(small(p['planned_files']))['records']
 if p['records']!=frozen or len(frozen)!=300 or len({r['ebook_ID'] for r in frozen})!=300:raise ValueError('frozen300_identity')
 for i,r in enumerate(frozen):
  if r['ordinal']!=i or r['module']!='gutenberg-epub' or r['source_relative_path']!=transport.path_for(r['ebook_ID']):raise ValueError('literal_path_scope')
 return p

def terminal(out,name,obj):
 raw=controller.encode(obj);cap=SLOTS[name]
 if len(raw)>cap:raise ValueError('reserved_terminal_slot')
 with (Path(out)/name).open('r+b') as f:f.write(raw+b' '*(cap-len(raw)));f.flush();os.fsync(f.fileno())
def rss(root):
 r=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rows={}
 if len(r.stdout)>1048576:raise ValueError('RSS_snapshot_limit')
 for line in r.stdout.splitlines():
  fs=line.split()
  if not fs:continue
  if len(fs)!=3 or any(not v.isascii() or not v.isdigit() for v in fs):raise ValueError('RSS_malformed')
  pid,ppid,n=map(int,fs)
  if pid<=0 or pid==ppid or pid in rows:raise ValueError('RSS_identity')
  rows[pid]=(ppid,n)
 if root not in rows or rows[root][1]<=0:raise ValueError('RSS_missing_root')
 owned={root}
 while True:
  more=owned|{pid for pid,(ppid,n) in rows.items() if ppid in owned}
  if more==owned:break
  owned=more
 return sum(rows[pid][1]*1024 for pid in owned)
def helpers():
 sys.path.insert(0,str(REPO/'src'));sys.path.insert(0,str(BASE));import acquire_sources
 from slm.data.intake_ledger import IntakeLedger
 if Path(acquire_sources.__file__).resolve()!=BASE/'acquire_sources.py':raise ValueError('ledger_origin')
 return IntakeLedger,acquire_sources.CONTRACT

def execute(a):
 out=None;created=False;ledger=None;profile=None;output_charged=False;peak=0;last_check=[0.];owned={};lock=threading.Lock();result=None;error=None
 for sig in (signal.SIGTERM,signal.SIGINT):signal.signal(sig,alarm)
 try:
  profile=verify(a);out=Path(profile['output'])
  if out.exists() or out.is_symlink():raise ValueError('once_only_output')
  if tree_size.census(ROOT)+800000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+800000000:raise ValueError('combined_intake_free_weights_reserve')
  peak=rss(os.getpid())
  if peak>1000000000:raise ValueError('initial_RSS')
  Ledger,contract=helpers();ledger=Ledger(ROOT/'charges',contract) # exclusive global writer lock held through entire profile/reconciliation
  if any(ledger.db.execute('SELECT 1 FROM attempts WHERE key=?',(profile['ledger_prefix']+suffix,)).fetchone() for suffix in ['output']+[f'body-{i:03}' for i in range(300)]):raise ValueError('prior_profile_charge_refuses_replay')
  ledger.reserve(profile['ledger_prefix']+'output',output_bytes=800000000);output_charged=True
  out.mkdir();created=True
  for name,n in SLOTS.items():(out/name).write_bytes(b' '*n)
  ownership={'controller_PID':os.getpid(),'active_owned_PIDs':owned,'shared_start':START,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256}
  terminal(out,'ownership.json',ownership)
  def check(extra=0,pid=None,register_only=False,unregister_only=False,role=None):
   nonlocal peak
   if clk()>=START+21595:raise TimeoutError('whole_profile_deadline')
   if pid is not None:
    with lock:
     if unregister_only:owned.pop(str(pid),None)
     elif str(pid) not in owned:
      stamp=subprocess.run(['/bin/ps','-p',str(pid),'-o','pid=,ppid=,pgid=,lstart=,comm='],capture_output=True,text=True,check=True,timeout=1).stdout.strip()
      if not stamp:raise ValueError('owned_child_registration_missing')
      owned[str(pid)]={'role':role,'ps_identity':stamp}
     terminal(out,'ownership.json',ownership)
   if register_only or unregister_only:return
   if threading.current_thread() is not threading.main_thread():raise ValueError('resource_or_ledger_check_from_thread')
   ledger.check_time();now=clk()
   if extra or now-last_check[0]>=.2:
    current=tree_size.census(out);remaining=max(0,800000000-current)
    if extra<0 or current+extra>800000000 or tree_size.census(ROOT)+remaining>64000000000 or shutil.disk_usage(ROOT).free<FREE+remaining:raise ValueError('output_aggregate_free_hard_limit')
    peak=max(peak,rss(os.getpid()))
    if peak>1000000000:raise ValueError('observed_owned_tree_RSS')
    last_check[0]=now
  controller.write(out,'planned-files.json',{'records':profile['records']},check,cap=1000000)
  result=controller.execute(profile,out,ledger,check,attempt_guard=lambda:attempt_deadline.Guard(START+21595));check();verify(a)
  if owned:raise ValueError('owned_children_still_registered')
  terminal(out,'inventory.json',controller.inventory(out,check));terminal(out,'result.json',{**result,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256,'elapsed_seconds':clk()-START});controller.finish_pending(ledger,profile['ledger_prefix']+'output',b'')
  terminal(out,'controller.json',{'status':'COMPLETE_FINITE_PROFILE_TERMINAL_RAW_DISCOVERY_NO_ADMISSION','elapsed_seconds':clk()-START,'peak_observed_owned_RSS_bytes':peak,'result_SHA256':sha(out/'result.json'),'inventory_SHA256':sha(out/'inventory.json'),'ledger_totals':ledger.totals(),'no_refunds_or_retries':True,'owned_children_controlled_reaped':True,'new_admitted_documents':0});return 0
 except BaseException as exc:
  error=exc;signal.setitimer(signal.ITIMER_REAL,max(.001,START+21600-clk()))
  # transport finally owns nativegroup/resolver/socket cleanup before returning here.
  if ledger is not None and profile is not None and output_charged:
   keys=[profile['ledger_prefix']+'output']+[profile['ledger_prefix']+f'body-{i:03}' for i in range(300)]
   for key in keys:
    r=ledger.db.execute('SELECT state FROM attempts WHERE key=?',(key,)).fetchone()
    if r and r[0]=='pending':ledger.finish(key,raw=None)
  if created:
   terminal(out,'result.json',{'status':'PARTIAL_FINITE_PROFILE_NO_RETRY_NO_ADMISSION','error_class':type(exc).__name__,'error':str(exc)[:1000],'partial':getattr(exc,'profile_partial',None),'elapsed_seconds':clk()-START,'new_admitted_documents':0})
   partial_entries=[]
   for parent,dirs,files in os.walk(out,followlinks=False):
    for name in files:
     path=Path(parent)/name
     try:statrow=path.stat(follow_symlinks=False);partial_entries.append({'path':str(path.relative_to(out)),'bytes':statrow.st_size,'mode':statrow.st_mode})
     except FileNotFoundError:raise ValueError('terminal_partial_inventory_changed')
   terminal(out,'inventory.json',{'status':'PARTIAL_STAT_INVENTORY_NO_ALL_ARTIFACT_HASH_CLAIM','files':partial_entries,'declared_inventory':'All surviving ownedregular/temporaryfiles retained; no sourcecompleteness/admission.','terminal_slots':SLOTS})
   terminal(out,'controller.json',{'status':'PARTIAL_FINITE_PROFILE_PRESERVED_NO_RETRY','elapsed_seconds':clk()-START,'peak_observed_owned_RSS_bytes':peak,'result_SHA256':sha(out/'result.json'),'owned_children_cleanup_returned':getattr(exc,'cleanup_complete',True),'charges_retained':True,'new_admitted_documents':0})
  raise
 finally:
  if ledger is not None:ledger.close()
  signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--profile-sha256',required=True);parser.add_argument('--code-pins-sha256',required=True);args=parser.parse_args()
 if args.execute:raise SystemExit(execute(args))
 else:verify(args);signal.setitimer(signal.ITIMER_REAL,0);print('STATIC_ONLY_NO_NETWORK_OR_GLOBAL_LEDGER_WRITES')
