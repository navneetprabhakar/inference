"""Once-only offline raw PB language/token diagnostic. No student model/API."""
import time,signal
START=time.monotonic()
def alarm(*a):raise TimeoutError('shared_deadline_or_signal')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,1855)
import argparse,contextlib,hashlib,importlib.util,json,os,sqlite3,shutil,subprocess,sys,stat,unicodedata
from pathlib import Path
import rules,engine,source_guard,tree_size
os.environ['TOKENIZERS_PARALLELISM']='false'
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake';FREE=53474836480
LIMITS={'worker_seconds':1800,'external_seconds':1860,'RSS_bytes':1000000000,'output_bytes':1000000000,'DB_bytes':768000000,'journal_bytes':32000000,'batch_documents':64,'batch_projection_bytes':8388608,'detector_batch_seconds':30,'detector_stdout_bytes':1048576,'documents':106881,'UTF8_bytes':1478854368,'characters':1467598452,'all_windows':1593650,'max_document_UTF8_bytes':2195961,'max_document_characters':2179415,'parsed_record_bytes':4000000,'normalized_UTF8_bytes':64000000,'normalized_words':8000000}
SLOTS={'result.json':1048576,'supervisor.json':1048576}
def sha(path):return rules.sha(path)
def ident(path):
 p=Path(path);s=p.stat(follow_symlinks=False)
 if not stat.S_ISREG(s.st_mode):raise ValueError('regular_input_required')
 return source_guard.ident(s)
def small(path,cap=8000000):
 if ident(path)[2]>cap:raise ValueError('metadata_cap')
 with Path(path).open('rb') as f:b=f.read(cap+1)
 if len(b)>cap:raise ValueError('metadata_cap')
 return b
def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def verify(a):
 if sha(HERE/'profile.json')!=a.profile_sha256 or sha(HERE/'code-pins.json')!=a.code_pins_sha256:raise ValueError('external_pins')
 p=json.loads(small(HERE/'profile.json'));registry=json.loads(small(HERE/'code-pins.json'))['SHA256'];required=set(p['input_paths'])|{str(HERE/n) for n in ['pilot.py','engine.py','rules.py','schema.py','classify.py','source_guard.py','tree_size.py','checks.py','profile.json','measure_capacity.py','capacity.json','known-targets.json']}
 if set(registry)!=required or p['limits']!=LIMITS:raise ValueError('exact_inventory_or_fixed_limits')
 for f,h in registry.items():
  if sha(f)!=h:raise ValueError('pinned_code_runtime_policy_metadata')
 if unicodedata.unidata_version!=p['normalization_diagnostic']['Unicode_version']:raise ValueError('frozen_normalization_Unicode_version')
 if str(Path(sys.executable).resolve())!=p['python']:raise ValueError('runtime_path')
 if (HERE/'rules.py').read_bytes()!=Path(p['original_WB_rules']).read_bytes():raise ValueError('frozen_language_policy_changed')
 p['known_targets']=json.loads(small(HERE/'known-targets.json'))
 if sum(x['rows'] for x in p['sources'])!=106881 or sum(x['text_UTF8_bytes'] for x in p['sources'])!=1478854368 or sum(x['potential_windows'] for x in p['sources'])!=1593650:raise ValueError('full_metadata_denominators')
 for item in p['sources']:
  if ident(item['source']['path'])!=item['source']['stat'] or ident(item['frame']['path'])!=item['frame']['stat']:raise ValueError('source_frame_custody_stat')
  proof=json.loads(small(item['source_integrity_receipt']));r=json.loads(small(item['inventory_result']));v=json.loads(small(item['inventory_verification']));sup=json.loads(small(item['inventory_supervisor']))
  if not proof['status'].startswith('PASS_EXACT_') or not r['status'].startswith('COMPLETE_') or not v['status'].startswith('PASS_') or not sup['status'].startswith('COMPLETE_') or sup['worker_exit_code']!=0:raise ValueError('complete_inventory_terminal_status')
  if any(proof[k]!=item['source'][k] for k in ['path','bytes','SHA256','stat']) or r['rows']!=item['rows'] or r['counts']['compressed_SHA256']!=item['source']['SHA256'] or r['artifacts']['frame.sqlite']['SHA256']!=item['frame']['SHA256'] or v['SQLite_SHA256']!=item['frame']['SHA256']:raise ValueError('complete_source_frame_integrity_evidence')
 overlay=p['family_overlay'];fp=json.loads(small(overlay['profile']));fr=json.loads(small(overlay['result']));fv=json.loads(small(overlay['verification']));fs=json.loads(small(overlay['supervisor']))
 if not fr['status'].startswith('COMPLETE_') or not fv['status'].startswith('PASS_FULL_V2_') or not fs['status'].startswith('COMPLETE_') or fs['worker_exit_code']!=0 or fr['raw_metadata_rows']!=106881 or fv['result_SHA256']!=sha(overlay['result']):raise ValueError('family_v2_completed_metadata_binding')
 cat=fp['cross_source_catalog_hold'];targets=p['known_targets']
 if targets['conflicting_IDs']!=sorted(set(x['id'] for x in fp['conflicting_identity_holds'])) or targets['catalog']['id']!=cat['id'] or targets['catalog']['text_SHA256']!=cat['text_SHA256']:raise ValueError('exact_family_v2_hold_targets')
 return p

def terminal(out,name,obj):
 raw=(json.dumps(obj,sort_keys=True)+'\n').encode();cap=SLOTS[name]
 if len(raw)>cap:raise ValueError('terminal_slot_cap')
 with (Path(out)/name).open('r+b') as f:f.write(raw+b' '*(cap-len(raw)));f.flush();os.fsync(f.fileno())
def guard(out,start,seconds,extra=0):
 current=tree_size.census(out);remaining=max(0,1000000000-current)
 if time.monotonic()>=start+seconds:raise TimeoutError('shared_deadline')
 if extra<0 or current+extra>1000000000 or tree_size.census(ROOT)+remaining>64000000000 or shutil.disk_usage(ROOT).free<FREE+remaining:raise ValueError('output_combined_intake_protected_reserves')

def worker(a):
 owned=False;out=None;active=[];phase='preflight';signal.setitimer(signal.ITIMER_REAL,max(.001,a.start+1800-time.monotonic()))
 try:
  p=verify(a);out=Path(p['output']);until=min(time.monotonic()+3,a.start+1800)
  while not (out/'ownership.json').exists() and time.monotonic()<until:time.sleep(.01)
  o=json.loads(small(out/'ownership.json'))
  if os.getppid()!=a.supervisor_pid or o!={'worker_PID':os.getpid(),'supervisor_PID':a.supervisor_pid,'shared_start':a.start,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256}:raise ValueError('owned_parent_receipt')
  owned=True;last=[0.]
  def check(extra=0):
   now=time.monotonic()
   if now>=a.start+1800:raise TimeoutError('worker_deadline')
   if extra or now-last[0]>=1:
    guard(out,a.start,1800,extra)
    for fn in active:fn()
    last[0]=now
  phase='tokenizer_preflight';tokenizer=rules.load_tokenizer(p);normalizer=module('frozen_edu_normalization',p['normalization_module']).normalized;inventory=module('frozen_PB_inventory',p['inventory_module'])
  with contextlib.ExitStack() as stack:
   def metadata_iterator(item):
    nonlocal phase
    phase='metadata_frame';path=Path(item['frame']['path']);expected=item['frame']['stat'];fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);stack.callback(os.close,fd)
    def custody():
     if source_guard.ident(os.fstat(fd))!=expected or ident(path)!=expected:raise ValueError('frame_FD_path_custody')
    custody();active.append(custody)
    digest=hashlib.sha256()
    with os.fdopen(os.dup(fd),'rb') as f:
     for b in iter(lambda:f.read(1048576),b''):digest.update(b);check()
    if digest.hexdigest()!=item['frame']['SHA256']:raise ValueError('frame_full_metadata_hash')
    db=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True);stack.callback(db.close);db.execute('pragma query_only=ON');db.execute('pragma cache_size=-4096');db.execute('pragma mmap_size=0');db.execute('pragma temp_store=MEMORY')
    phase='raw_source_counting'
    return db.execute('select * from records order by ordinal')
   @contextlib.contextmanager
   def source_context(item,callback):
    with source_guard.opened(item['source'],callback) as read:
     active.append(read.assert_custody)
     try:yield read
     finally:active.remove(read.assert_custody)
   phase='raw_source_counting';result=engine.run(p,out,metadata_iterator,source_context,inventory,check,lambda:a.start+1800-time.monotonic(),tokenizer,normalizer)
  active.clear();phase='postflight';verify(a);check()
  result.update({'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256,'elapsed_shared_seconds':time.monotonic()-a.start,'frozen_M1_manifest_SHA256':p['tokenizer_manifest']['sha256'],'frozen_M1_core_SHA256':p['tokenizer_core']['sha256'],'artifacts':{}})
  for path in out.iterdir():
   if path.is_file() and path.name not in SLOTS:result['artifacts'][path.name]={'bytes':path.stat().st_size,'SHA256':sha(path)};check()
  terminal(out,'result.json',result)
 except BaseException as e:
  if owned:terminal(out,'result.json',{'status':'PARTIAL_PB_LANGUAGE_TOKEN_NO_RETRY_NO_ADMISSION','error_class':type(e).__name__,'phase':phase,'partial':getattr(e,'diagnostic_partial',None),'elapsed_shared_seconds':time.monotonic()-a.start,'new_admitted_documents':0,'new_admitted_tokens':0,'raw_exception_or_CLI_stderr_recorded':False})
  raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)

def tree_rss(snapshot,root,worker=None):
 rows={}
 if type(snapshot) is not str or len(snapshot)>1048576:raise ValueError('RSS_snapshot_cap')
 for line in snapshot.splitlines():
  if not line.strip():continue
  f=line.split()
  if len(f)!=3 or any(not x.isascii() or not x.isdigit() for x in f):raise ValueError('RSS_bad_row')
  pid,ppid,rss=map(int,f)
  if pid<=0 or pid==ppid or pid in rows:raise ValueError('RSS_bad_PID')
  rows[pid]=(ppid,rss)
 if root not in rows or rows[root][1]<=0:raise ValueError('RSS_missing_root')
 owned={root}
 while True:
  new=owned|{p for p,(q,r) in rows.items() if q in owned}
  if new==owned:break
  owned=new
 if worker is not None and (worker not in owned or rows[worker][1]<=0):raise ValueError('RSS_missing_worker')
 return sum(rows[p][1]*1024 for p in owned)
def kill(child):
 if child.poll() is None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 child.wait(timeout=3)
def supervise(a):
 child=None;created=False;out=None;peak=0;signal.setitimer(signal.ITIMER_REAL,max(.001,START+1855-time.monotonic()))
 for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,alarm)
 try:
  p=verify(a);out=Path(p['output'])
  if out.exists() or out.is_symlink():raise ValueError('once_only_output')
  if tree_size.census(ROOT)+1000000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+1000000000:raise ValueError('prewrite_combined_and_free_reserves')
  out.mkdir();created=True
  for name,n in SLOTS.items():(out/name).write_bytes(b' '*n)
  child=subprocess.Popen([sys.executable,'-B',str(HERE/'pilot.py'),'--worker','--start',str(START),'--supervisor-pid',str(os.getpid()),'--profile-sha256',a.profile_sha256,'--code-pins-sha256',a.code_pins_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  with (out/'ownership.json').open('xb') as f:f.write((json.dumps({'worker_PID':child.pid,'supervisor_PID':os.getpid(),'shared_start':START,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256})+'\n').encode());f.flush();os.fsync(f.fileno())
  while child.poll() is None:
   guard(out,START,1860);ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rss=tree_rss(ps.stdout,os.getpid(),child.pid if child.poll() is None else None);peak=max(peak,rss)
   if rss>1000000000:raise ValueError('owned_tree_RSS')
   time.sleep(.2)
  child.wait(timeout=3);guard(out,START,1860);ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);peak=max(peak,tree_rss(ps.stdout,os.getpid()))
  if peak>1000000000:raise ValueError('terminal_RSS')
  r=json.loads(small(out/'result.json'));ok=child.returncode==0 and r.get('status')=='COMPLETE_RAW_PB_LANGUAGE_M1_DIAGNOSTICS_NO_ADMISSION'
  terminal(out,'supervisor.json',{'status':'COMPLETE_PB_TOKEN_LANGUAGE_DIAGNOSTIC_NO_ADMISSION' if ok else 'PARTIAL_PB_DIAGNOSTIC_NO_RETRY','worker_exit_code':child.returncode,'worker_reaped':True,'elapsed_shared_seconds':time.monotonic()-START,'peak_tree_RSS_bytes':peak,'result_SHA256':sha(out/'result.json'),'all_output_bytes':tree_size.census(out),'new_admitted_documents':0});return 0 if ok else 1
 except BaseException as e:
  signal.setitimer(signal.ITIMER_REAL,max(.001,START+1860-time.monotonic()))
  if child is not None:kill(child)
  if created:terminal(out,'supervisor.json',{'status':'PARTIAL_PB_DIAGNOSTIC_NO_RETRY','error_class':type(e).__name__,'worker_reaped':child is None or child.poll() is not None,'elapsed_shared_seconds':time.monotonic()-START,'raw_exception_or_CLI_stderr_recorded':False,'new_admitted_documents':0})
  raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':
 q=argparse.ArgumentParser();q.add_argument('--profile-sha256',required=True);q.add_argument('--code-pins-sha256',required=True);q.add_argument('--execute',action='store_true');q.add_argument('--worker',action='store_true');q.add_argument('--start',type=float);q.add_argument('--supervisor-pid',type=int);a=q.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a);print('STATIC_PREPARATION_ONLY_NO_RAW_PB_CLASSIFIER_OR_TOKEN_PASS')
