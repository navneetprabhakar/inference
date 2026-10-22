"""Terminal-only independent PB filter metadata verifier; no raw bodies or policy execution."""
import time,signal
START=time.monotonic()
def alarm(*a):raise TimeoutError('shared_verifier_deadline_or_signal')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,1195)
import argparse,sys,os,stat,json,hashlib,subprocess,shutil
from pathlib import Path
import core
HERE=Path(__file__).resolve().parent;BASE=HERE.parent;PRODUCER=BASE/'pressbooks-full-raw-filter-preparation-v1';sys.path.insert(0,str(PRODUCER));import pilot as producer
# Importing the reviewed producer establishes its larger alarm; restore our own remaining budget immediately.
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,max(.001,START+1195-time.monotonic()))
LIMITS={'worker_seconds':1140,'external_seconds':1200,'RSS_bytes':1000000000,'output_bytes':16000000};SLOTS={'result.json':262144,'supervisor.json':262144}
def ident(path):return producer.source_guard.ident(Path(path).stat(follow_symlinks=False))
def load(path):return json.loads(producer.source_guard.small(path),object_pairs_hook=core.unique)
def sha(path):return core.sha(path)
def verify(a):
 core.require(sha(HERE/'profile.json')==a.profile_sha256 and sha(HERE/'code-pins.json')==a.code_pins_sha256,'external_code_profile_pins');p=load(HERE/'profile.json');registry=load(HERE/'code-pins.json')['SHA256'];required=set(p['input_paths'])|{str(HERE/n) for n in ['runner.py','core.py','checks.py','profile.json']};core.require(set(registry)==required and p['limits']==LIMITS,'exact_required_inventory_and_limits')
 for path,digest in registry.items():core.require(sha(path)==digest,'code_runtime_policy_pin')
 core.require(str(Path(sys.executable).resolve())==p['python'],'exact_runtime');return p

def bound(a,p):
 core.require(a.binding and a.binding_sha256 and sha(a.binding)==a.binding_sha256,'external_terminal_binding_pin');b=load(a.binding);core.require(b['status']=='PARENT_REVIEWED_COMPLETE_PB_FULL_FILTER_TERMINAL_BINDING' and b['producer_exec_exit']==0 and b['producer_reaped']is True,'COMPLETE_parent_gate');folder=Path(p['producer_output']);required={'candidate.sqlite','candidate.sqlite-journal','progress.metadata.jsonl','fresh-review-selection.json','ownership.json','result.json','supervisor.json'};core.require(set(b['files'])==required and {x.name for x in folder.iterdir()}==required,'terminal_exact_output_inventory')
 for name,proof in b['files'].items():core.require(not (folder/name).is_symlink() and ident(folder/name)==proof['stat'],'bound_terminal_stat')
 r=load(folder/'result.json');s=load(folder/'supervisor.json');o=load(folder/'ownership.json')
 core.require(r['status']=='COMPLETE_FULL_PRESSBOOKS_RAW_FILTER_AND_FRESH_SELECTION_NO_ADMISSION' and s['status']=='COMPLETE_FULL_RAW_FILTER_FRESH400_NO_ADMISSION' and s['worker_exit_code']==0 and s['result_SHA256']==sha(folder/'result.json'),'complete_reaped_producer_status')
 core.require(r['profile_SHA256']==p['producer_profile_SHA256'] and r['codepins_SHA256']==p['producer_codepins_SHA256'] and b['producer_profile_SHA256']==p['producer_profile_SHA256'] and b['producer_codepins_SHA256']==p['producer_codepins_SHA256'],'exact_producer_binding')
 for name in ['worker_PID','supervisor_PID']:
  try:os.kill(o[name],0)
  except ProcessLookupError:pass
  else:raise ValueError('producer_PID_still_live')
 core.require(s['peak_observed_RSS_bytes']<=1000000000 and s['elapsed_seconds']<=1860 and s['all_output_bytes']<=1000000000,'producer_resource_receipt')
 return b,r,s

def guard(out,prewrite=False):
 core.require((0 if prewrite else producer.size(out))<=16000000 and producer.size(producer.ROOT)+16000000<=64000000000 and shutil.disk_usage(producer.ROOT).free>=producer.FREE+16000000,'metadata_output_and_protected_disk_reserves')
def terminal(out,name,value):
 raw=(json.dumps(value,sort_keys=True)+'\n').encode();cap=SLOTS[name];core.require(len(raw)<=cap,'terminal_slot_cap')
 with (out/name).open('r+b')as f:f.write(raw+b' '*(cap-len(raw)));f.flush();os.fsync(f.fileno())
def worker(a):
 owned=False;out=None;signal.setitimer(signal.ITIMER_REAL,max(.001,a.start+1140-time.monotonic()));fds=[];dbs=[]
 try:
  p=verify(a);b,r,s=bound(a,p);out=Path(p['output']);end=min(time.monotonic()+3,a.start+1140)
  while not (out/'ownership.json').exists() and time.monotonic()<end:time.sleep(.01)
  o=load(out/'ownership.json');core.require(o=={'supervisor_PID':a.supervisor_pid,'worker_PID':os.getpid(),'shared_start':a.start,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256} and os.getppid()==a.supervisor_pid,'verifier_owned_worker');owned=True;last=[0.]
  def check():
   now=time.monotonic();core.require(now<a.start+1140,'worker_deadline')
   if now-last[0]>=1:guard(out);last[0]=now
  pp=producer.verify(argparse.Namespace(profile_sha256=p['producer_profile_SHA256'],code_pins_sha256=p['producer_codepins_SHA256']));folder=Path(p['producer_output']);hashes={}
  for name,proof in b['files'].items():hashes[name]=core.sha(folder/name,check);core.require(hashes[name]==proof['SHA256'],'terminal_artifact_hash')
  for name,proof in r['artifacts'].items():core.require(hashes[name]==proof['SHA256'] and ident(folder/name)[2]==proof['bytes'],'producer_artifact_HASH_size')
  core.require(sum(x['stat'][2] for x in b['files'].values())==s['all_output_bytes'],'exact_terminal_total_bytes');core.require(ident(folder/'progress.metadata.jsonl')[2]==r['progress_bytes'],'exact_progress_metadata_bytes')
  for item,receipt in zip(pp['sources'],r['sources'],strict=True):
   c=receipt['counts'];core.require(receipt['source_id']==item['source_id'] and receipt['rows']==item['frame']['rows'] and receipt['ordered_line_locator_SHA256']==item['frame']['ordered_line_locator_SHA256'] and c['compressed_bytes']==item['raw']['bytes'] and c['compressed_SHA256']==item['raw']['SHA256'] and c['gzip_CRC_EOF_members']>0 and c['trailing_absent']is True and c['decoded_bytes']<=2000000000,'inherited_all_source_CRC_SHA_receipt_bindings')
  def opened(path,expected,digest):
   fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);fds.append((path,fd,expected));core.require(producer.source_guard.ident(os.fstat(fd))==expected==ident(path),'SQL_FD_before_custody');core.require(core.sha(path,check)==digest,'metadata_SQL_file_hash');db=core.dbopen(path);dbs.append(db);return db
  frames={item['source_id']:opened(Path(item['frame']['path']),item['frame']['stat'],item['frame']['inherited_SHA256']) for item in pp['sources']}
  family=opened(Path(pp['family_frame']['path']),pp['family_frame']['stat'],pp['family_frame']['inherited_SHA256']);tokens=opened(Path(pp['token_frame']['path']),pp['token_frame']['stat'],pp['token_frame']['inherited_SHA256']);candidate=opened(folder/'candidate.sqlite',b['files']['candidate.sqlite']['stat'],hashes['candidate.sqlite']);selection=load(folder/'fresh-review-selection.json')
  result=core.verify(candidate,frames,family,tokens,r,pp,selection,check)
  for path,fd,expected in fds:require(producer.source_guard.ident(os.fstat(fd))==expected==ident(path),'SQL_FD_after_custody')
  for name,proof in b['files'].items():require(ident(folder/name)==proof['stat'],'terminal_post_custody')
  verify(a);bound(a,p);result.update({'status':'COMPLETE_INDEPENDENT_STORED_PB_FILTER_AND_FRESH400_VERIFICATION_NO_ADMISSION','output_hashes':hashes,'source_body_reads':0,'source_policy_classifier_or_tokenizer_operations':0,'original_source_policy_and_preimage_recomputation':False,'elapsed_seconds':time.monotonic()-a.start,'terminal_binding_SHA256':a.binding_sha256});terminal(out,'result.json',result)
 except BaseException as e:
  if owned:terminal(out,'result.json',{'status':'PARTIAL_STORED_METADATA_VERIFICATION_NO_RETRY','error_class':type(e).__name__})
  raise
 finally:
  for db in dbs:db.close()
  for _,fd,_ in fds:os.close(fd)
  signal.setitimer(signal.ITIMER_REAL,0)
def supervise(a):
 child=None;out=None;created=False;signal.setitimer(signal.ITIMER_REAL,max(.001,START+1195-time.monotonic()))
 for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,alarm)
 try:
  p=verify(a);bound(a,p);out=Path(p['output']);core.require(not out.exists() and not out.is_symlink(),'once_only_output');guard(out,prewrite=True);out.mkdir();created=True
  for name,size in SLOTS.items():(out/name).write_bytes(b' '*size)
  child=subprocess.Popen([sys.executable,'-B',str(HERE/'runner.py'),'--worker','--start',str(START),'--supervisor-pid',str(os.getpid()),'--profile-sha256',a.profile_sha256,'--code-pins-sha256',a.code_pins_sha256,'--binding',a.binding,'--binding-sha256',a.binding_sha256],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  with (out/'ownership.json').open('xb')as f:f.write((json.dumps({'supervisor_PID':os.getpid(),'worker_PID':child.pid,'shared_start':START,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256})+'\n').encode());f.flush();os.fsync(f.fileno())
  peak=0
  while child.poll() is None:
   guard(out);core.require(time.monotonic()<START+1200,'external_deadline');ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rss=producer.tree_rss(ps.stdout,os.getpid(),child.pid if child.poll() is None else None);peak=max(peak,rss);core.require(rss<=1000000000,'tree_RSS');time.sleep(.2)
  child.wait(timeout=3);guard(out);ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);peak=max(peak,producer.tree_rss(ps.stdout,os.getpid()));core.require(peak<=1000000000,'terminal_RSS');r=load(out/'result.json');ok=child.returncode==0 and r['status']=='COMPLETE_INDEPENDENT_STORED_PB_FILTER_AND_FRESH400_VERIFICATION_NO_ADMISSION';terminal(out,'supervisor.json',{'status':'COMPLETE_STORED_METADATA_VERIFICATION' if ok else 'PARTIAL_VERIFICATION','worker_exit_code':child.returncode,'worker_reaped':True,'peak_tree_RSS_bytes':peak,'elapsed_seconds':time.monotonic()-START,'result_SHA256':sha(out/'result.json')});return 0 if ok else 1
 except BaseException as e:
  signal.setitimer(signal.ITIMER_REAL,max(.001,START+1200-time.monotonic()))
  if child is not None:producer.kill(child)
  if created:terminal(out,'supervisor.json',{'status':'PARTIAL_VERIFICATION','error_class':type(e).__name__,'worker_reaped':child is None or child.poll() is not None})
  raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':
 q=argparse.ArgumentParser();q.add_argument('--profile-sha256',required=True);q.add_argument('--code-pins-sha256',required=True);q.add_argument('--binding');q.add_argument('--binding-sha256');q.add_argument('--execute',action='store_true');q.add_argument('--worker',action='store_true');q.add_argument('--start',type=float);q.add_argument('--supervisor-pid',type=int);a=q.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a);print('STATIC_ONLY_TERMINAL_COMPLETE_BINDING_REQUIRED_NO_SQL_OR_SOURCE_READ')
