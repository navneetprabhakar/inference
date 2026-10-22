"""Bounded verifier of terminal stored metadata only, no native body opens."""
import time,signal
START=time.monotonic()
def alarm(*args):raise TimeoutError('verifier_shared_deadline_or_signal')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,3655)
import argparse,sys,os,json,hashlib,subprocess,stat,importlib.util,shutil
from pathlib import Path
import core
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
PRODUCER=BASE/'enwiki-retained-prefix-frame-preparation-v2';sys.path.insert(0,str(PRODUCER));import pilot as sourcepilot
SLOTS={'result.json':262144,'supervisor.json':262144}
def sha(path):return core.stream_hash(path,lambda:None)[1]
def ident(path):
 p=Path(path);s=p.stat(follow_symlinks=False);core.require(stat.S_ISREG(s.st_mode),'regular_metadata_file');return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def small(path,cap=8000000):
 p=Path(path);core.require(ident(p)[2]<=cap,'small_metadata_cap')
 with p.open('rb') as f:r=f.read(cap+1)
 core.require(len(r)<=cap,'small_metadata_readcap');return r
def load(path,cap=8000000):return core.loads(small(path,cap))
def verify(a):
 core.require(sha(HERE/'profile.json')==a.profile_sha256 and sha(HERE/'code-pins.json')==a.code_pins_sha256,'external_pins')
 p=load(HERE/'profile.json');core.require(p['producer_profile_SHA256']=='51723b60b60c23c9894bb0c92778513a5e7df5315fcb01f09e79683201b6ba8a' and p['producer_codepins_SHA256']=='86a08a0ea827163bc3607c8df34307036eae82acc8c173d5a69327ec68973885','fixed_producer');pins=load(HERE/'code-pins.json')['SHA256'];required=set(p['input_paths'])|{str(HERE/n) for n in ['core.py','runner.py','checks.py','profile.json']}
 core.require(set(pins)==required,'exact_inventory')
 for f,h in pins.items():core.require(sha(f)==h,'code_input_pin')
 core.require(p['limits']=={'worker_seconds':3600,'external_seconds':3660,'RSS_bytes':1000000000,'output_bytes':16000000},'fixed_verifier_limits')
 core.require(str(Path(sys.executable).resolve())==p['python'],'actual_python')
 return p

def bound(a,p):
 core.require(a.binding is not None and a.binding_sha256 is not None and sha(a.binding)==a.binding_sha256,'external_terminal_binding')
 b=load(a.binding);core.require(b['status']=='PARENT_REVIEWED_COMPLETE_TERMINAL_METADATA_BINDING','binding_dispatch_gate')
 folder=Path(p['producer_output']);core.require(b['producer_profile_SHA256']==p['producer_profile_SHA256'] and b['producer_codepins_SHA256']==p['producer_codepins_SHA256'],'binding_producer_identity')
 required={'frame.sqlite','original-header.xml','header-receipt.json','codec.json','header-summary.json','group-receipts.jsonl','exceptions.jsonl','result.json','supervisor.json','ownership.json'}
 core.require(set(b['files'])==required and {x.name for x in folder.iterdir() if x.is_file()}==required,'exact_terminal_output_inventory')
 for name,proof in b['files'].items():core.require(ident(folder/name)==proof['stat'],'terminal_file_stat')
 for name in ['result.json','supervisor.json','ownership.json']:core.require(sha(folder/name)==b['files'][name]['SHA256'],'terminal_receipt_pin')
 r=load(folder/'result.json');s=load(folder/'supervisor.json');own=load(folder/'ownership.json')
 core.require(r['status']=='COMPLETE_RETAINED_PREFIX_FRAGMENT_FRAME_NO_ADMISSION' and s['status']=='COMPLETE_RETAINED_PREFIX_FRAGMENT_NO_ADMISSION' and s['worker_exit_code']==0 and s['result_SHA256']==sha(folder/'result.json'),'producer_complete_terminal')
 core.require(r['profile_SHA256']==p['producer_profile_SHA256'] and r['codepins_SHA256']==p['producer_codepins_SHA256'] and r['whole_publisher_archive_verified'] is False,'producer_scope_and_pins')
 for key in ['worker_PID','supervisor_PID']:
  try:os.kill(own[key],0)
  except ProcessLookupError:pass
  else:raise ValueError('producer_owner_still_live')
 return b,r,s

def resource_guard(out):
 core.require(sourcepilot.size(out)<=16000000 and sourcepilot.size(sourcepilot.ROOT)+16000000<=64000000000 and shutil.disk_usage(sourcepilot.ROOT).free>=sourcepilot.FREE+16000000,'verifier_output_combined_free_reserves')

def terminal(out,name,obj):
 raw=core.transcript(obj);cap=SLOTS[name];core.require(len(raw)<=cap,'terminal_slot_cap')
 with (Path(out)/name).open('r+b') as f:f.write(raw+b' '*(cap-len(raw)));f.flush();os.fsync(f.fileno())
def worker(a):
 out=None;owned=False;signal.setitimer(signal.ITIMER_REAL,max(.001,a.start+3600-time.monotonic()))
 try:
  p=verify(a);b,r,s=bound(a,p);out=Path(p['output']);wait_end=min(time.monotonic()+3,a.start+3600)
  while not (out/'ownership.json').exists() and time.monotonic()<wait_end:time.sleep(.01)
  o=load(out/'ownership.json')
  core.require(os.getppid()==a.supervisor_pid and o['worker_PID']==os.getpid() and o['supervisor_PID']==a.supervisor_pid and o['profile_SHA256']==a.profile_sha256 and o['codepins_SHA256']==a.code_pins_sha256 and o['shared_start']==a.start,'verifier_ownership');owned=True
  last_resource=[0.]
  def check():
   now=time.monotonic();core.require(now<a.start+3600,'shared_worker_deadline')
   if now-last_resource[0]>=1:resource_guard(out);last_resource[0]=now
  prod,binding=sourcepilot.verify(argparse.Namespace(profile_sha256=p['producer_profile_SHA256'],code_pins_sha256=p['producer_codepins_SHA256']))
  native=Path(binding['path']);native_stat=ident(native);core.require(native_stat==binding['stat'],'native_stat_only_custody')
  index=Path(prod['index']['path']);indexstat=ident(index);folder=Path(p['producer_output']);hashes={}
  for name,proof in b['files'].items():
   n,h=core.stream_hash(folder/name,check);core.require(n==proof['stat'][2] and h==proof['SHA256'],'bound_output_file_hash');hashes[name]=h
  for name,entry in r['artifacts'].items():core.require(hashes[name]==entry['SHA256'] and (folder/name).stat().st_size==entry['bytes'],'producer_artifact_hash')
  core.require(b['files']['frame.sqlite']['stat'][2]<=2000000000,'producer_DB_cap')
  core.require(sum(x['stat'][2] for x in b['files'].values())==s['all_output_bytes']<=3000000000 and s['peak_observed_RSS_bytes']<=1000000000 and s['elapsed_seconds']<=21900,'producer_resource_receipts')
  titles=sourcepilot.engine.module('verified_title_decoder',prod['title_decoder']);bridge=load(p['bridge'],cap=8000000);core.require(len(bridge['expected_SQL_fields'])==1600 and len(bridge['expected_groups'])==16,'exact_prior_bridge_coverage')
  fds=[]
  try:
   for path in [index,folder/'frame.sqlite']:
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);fds.append((path,fd));st=os.fstat(fd);core.require([st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]==ident(path),'SQL_FD_path_custody')
   result=core.verify_frame({'max_group_compressed_bytes':prod['limits']['max_group_compressed_bytes'],'source_prefix_bytes':prod['source']['bytes']},r,prod['selection'],index,folder,titles.decode_once,sha(prod['title_decoder']),bridge,check)
   for path,fd in fds:
    st=os.fstat(fd);core.require([st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]==ident(path),'SQL_FD_post_custody')
  finally:
   for _,fd in fds:os.close(fd)
  for name,proof in b['files'].items():core.require(ident(folder/name)==proof['stat'],'output_postflight_stat')
  core.require(ident(index)==indexstat and ident(native)==native_stat,'source_index_postflight_stat');verify(a)
  result.update({'status':'COMPLETE_INDEPENDENT_STORED_FRAGMENT_METADATA_VERIFICATION_NO_ADMISSION','native_source_body_reads':0,'index_metadata_SQL_read':True,'additional_index_wholehash_reads':0,'first1600_oldalgorithm_bridge':True,'publisher_whole_archive_verified':False,'new_admitted_documents':0,'new_admitted_tokens':0,'producer_binding_SHA256':a.binding_sha256,'output_hashes':hashes,'elapsed_seconds':time.monotonic()-a.start})
  terminal(out,'result.json',result)
 except BaseException as e:
  if owned:terminal(out,'result.json',{'status':'PARTIAL_INDEPENDENT_VERIFICATION_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500]})
  raise

def supervise(a):
 out=None;child=None;created=False;signal.setitimer(signal.ITIMER_REAL,max(.001,START+3655-time.monotonic()))
 for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,alarm)
 try:
  p=verify(a);bound(a,p);out=Path(p['output']);core.require(not out.exists() and not out.is_symlink(),'once_only_verifier_output');core.require(sourcepilot.size(sourcepilot.ROOT)+16000000<=64000000000 and shutil.disk_usage(sourcepilot.ROOT).free>=sourcepilot.FREE+16000000,'prewrite_global_reserves');out.mkdir();created=True
  for n,size in SLOTS.items():(out/n).write_bytes(b' '*size)
  child=subprocess.Popen([sys.executable,'-B',str(HERE/'runner.py'),'--worker','--start',str(START),'--supervisor-pid',str(os.getpid()),'--profile-sha256',a.profile_sha256,'--code-pins-sha256',a.code_pins_sha256,'--binding',a.binding,'--binding-sha256',a.binding_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  raw=core.transcript({'worker_PID':child.pid,'supervisor_PID':os.getpid(),'shared_start':START,'profile_SHA256':a.profile_sha256,'codepins_SHA256':a.code_pins_sha256})
  with (out/'ownership.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  peak=0
  while child.poll() is None:
   resource_guard(out)
   core.require(time.monotonic()<START+3660 and sourcepilot.size(out)<=16000000,'external_deadline_or_output')
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rss=sourcepilot.tree_rss(ps.stdout,os.getpid(),child.pid if child.poll() is None else None);peak=max(peak,rss);core.require(rss<=1000000000,'observed_RSS');time.sleep(1)
  child.wait(timeout=3);resource_guard(out);ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);peak=max(peak,sourcepilot.tree_rss(ps.stdout,os.getpid()));core.require(peak<=1000000000,'terminal_RSS');r=load(out/'result.json');ok=child.returncode==0 and r.get('status')=='COMPLETE_INDEPENDENT_STORED_FRAGMENT_METADATA_VERIFICATION_NO_ADMISSION';terminal(out,'supervisor.json',{'status':'COMPLETE_STORED_METADATA_VERIFICATION' if ok else 'PARTIAL_VERIFICATION','worker_exit_code':child.returncode,'elapsed_seconds':time.monotonic()-START,'peak_RSS_bytes':peak,'result_SHA256':sha(out/'result.json')});return 0 if ok else 1
 except BaseException as e:
  signal.setitimer(signal.ITIMER_REAL,max(.001,START+3660-time.monotonic()))
  if child is not None:sourcepilot.kill(child)
  if created:terminal(out,'supervisor.json',{'status':'PARTIAL_VERIFICATION','error':type(e).__name__+':'+str(e)[:1500]})
  raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':
 q=argparse.ArgumentParser();q.add_argument('--profile-sha256',required=True);q.add_argument('--code-pins-sha256',required=True);q.add_argument('--binding');q.add_argument('--binding-sha256');q.add_argument('--execute',action='store_true');q.add_argument('--worker',action='store_true');q.add_argument('--start',type=float);q.add_argument('--supervisor-pid',type=int);a=q.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a);print('STATIC_ONLY_TERMINAL_BINDING_REQUIRED_NO_SQL_OR_NATIVE_READ')
