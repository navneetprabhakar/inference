"""Undispatchable until fresh completed fullarchive receipt+stat binding reviewed."""
import argparse,hashlib,json,re,os,pathlib,shutil,signal,subprocess,sys,time,xml.parsers.expat as expat,platform
import frame_core as core,freeze_index_v2
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'enwiki-native-first16-stream-frame-v2'
SOURCE=ROOT/'enwiki-native-full-XML-20260801-v3/enwiki-20260801-pages-articles-multistream.xml.bz2';WR=SOURCE.parent/'worker-result.json';SR=SOURCE.parent/'supervisor-result.json';PLAN=ROOT/'enwiki-first16-index-groups-v2/groups.json'
URL='https://dumps.wikimedia.org/enwiki/20260801/'+SOURCE.name;SIZE=26668484995;MD5='b6c5a530175db4f5a46cc1439cdac27d';SHA1='dd27f408e60d3bc864d42547fb0a0d7408249c13'
LIMITS={**core.LIMITS,'offset_groups':16,'output_bytes':16000000,'worker_seconds':115,'external_seconds':120,'observed_RSS_bytes':1000000000,'additional_full_archive_verification_read_bytes':0}
FREE=53474836480;SLOTS={'result.json':65536,'supervisor.json':32768}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file())
def runtime():return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'expat':expat.EXPAT_VERSION,'platform':platform.platform()}
def stat_id(s):return {k:getattr(s,k) for k in ['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns']}
def inventory():
 paths=[HERE/n for n in ['pilot.py','frame_core.py','checks.py','lifecycle_checks.py','code_guard.py','profile.json','focused_checks.py','freeze_index_v2.py','index-freeze-v2-input-pins.json']]+[PLAN,BASE/'disk-budget.json',ROOT/'enwiki-native-index-assessment-v1/result.json',ROOT/'enwiki-native-index-assessment-v1/supervisor.json',BASE/'enwiki-native-full-acquisition-preparation-v3/profile.json',BASE/'enwiki-native-full-acquisition-preparation-v3/readiness.json',pathlib.Path(sys.executable)]
 paths += [pathlib.Path(m.__file__) for m in [expat,subprocess,hashlib,json] if getattr(m,'__file__',None)]
 return {str(x.resolve()) for x in paths}
def verify_plan(p):
 groups=p['groups']
 if len(groups)!=16 or p['index_SHA256']!=freeze_index_v2.SHA or p['verification_bytes']!=freeze_index_v2.SIZE:raise ValueError('frozen16groups_fullverifiedindex_custody')
 prior=0;total=0
 for i,g in enumerate(groups):
  if g['start']<prior or g['end_exclusive']<=g['start'] or (i and g['start']!=prior):raise ValueError('group_offset_contiguity')
  for r in g['rows']:
   actual=freeze_index_v2.parse_line(bytes.fromhex(r['raw_line_hex']),r['row_ordinal'])
   if actual!=r or r['offset']!=g['start']:raise ValueError('raw_index_line_identity_hash')
  prior=g['end_exclusive'];total+=len(g['rows'])
 if prior!=p['boundary_first_row']['offset'] or prior!=p['XML_prefix_end_exclusive'] or prior>LIMITS['compressed_prefix_bytes'] or total!=1600 or prior!=17948470 or groups[0]['start']!=570 or p['XML_prefix_start']!=0:raise ValueError('frozen_prefix_budget_or_boundary')
 return p

def verify(code,profile):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=profile:raise ValueError('external_profile_pin')
 p=json.loads((HERE/'profile.json').read_text())
 if p['limits']!=LIMITS or p['source_archive']!=str(SOURCE) or p['frozen_plan_SHA256']!=sha(PLAN):raise ValueError('fixed_scope_limits_source_plan')
 return verify_plan(json.loads(PLAN.read_text()))
def verify_binding(path,expected,profile):
 # No current archive contents are opened or repeatedly26GBhashed by this guard.
 if path is None or expected is None:raise ValueError('NOT_DISPATCHABLE_FRESH_COMPLETED_SOURCE_BINDING_REQUIRED')
 q=pathlib.Path(path)
 if q.is_symlink() or q.stat().st_size>65536 or sha(q)!=expected:raise ValueError('external_source_binding_pin')
 b=json.loads(q.read_text())
 if not isinstance(b.get('archive_SHA256'),str) or not re.fullmatch('[a-f0-9]{64}',b['archive_SHA256']):raise ValueError('exact_fullsource_SHA256_format')
 if b['status']!='PARENT_VERIFIED_COMPLETE_SOURCE_READY_FOR_PREFIX' or b['profile_SHA256']!=profile or b['archive_path']!=str(SOURCE) or b['archive_bytes']!=SIZE or b['publisher_MD5']!=MD5 or b['publisher_SHA1']!=SHA1 or b['pilot_full_archive_rehash_bytes']!=0:raise ValueError('source_binding_policy')
 if any(x.is_symlink() or not x.is_file() or x.stat().st_size>1048576 for x in [WR,SR]):raise ValueError('bounded_regular_terminal_receipts')
 if sha(WR)!=b['worker_receipt_SHA256'] or sha(SR)!=b['supervisor_receipt_SHA256']:raise ValueError('fresh_receipt_hashes')
 w=json.loads(WR.read_text());s=json.loads(SR.read_text());v=s.get('independent_final_file_verification',{})
 if w.get('status')!='COMPLETE_PUBLISHER_VERIFIED_COMPRESSED_XML_ONLY_NO_ADMISSION' or s.get('status')!='COMPLETE_XML_ARCHIVE_ACQUISITION_NO_ADMISSION' or s.get('worker_exit_code')!=0 or s.get('worker_receipt_SHA256')!=sha(WR):raise ValueError('fullarchive_both_terminal_COMPLETE_required')
 if w.get('file')!='assembled.partial' or w['URL']!=URL or w['bytes']!=SIZE or w['MD5']!=MD5 or w['SHA1']!=SHA1 or not w['publisher_checksums_match'] or v['bytes']!=SIZE or v['MD5']!=MD5 or v['SHA1']!=SHA1 or v['SHA256']!=w['SHA256'] or b['archive_SHA256']!=w['SHA256']:raise ValueError('publisher_and_independent_supervisor_fullhash_binding')
 if SOURCE.is_symlink() or stat_id(SOURCE.stat())!=b['source_stat'] or SOURCE.stat().st_size!=SIZE:raise ValueError('immutable_completed_source_stat')
 return b

def guard(start,n=0,seconds=115):
 if clk()-start>=seconds:raise TimeoutError('shared_deadline_'+str(seconds)+'seconds')
 if size(OUT)+n>16000000-131072 or shutil.disk_usage(ROOT).free<FREE+n:raise ValueError('output16MB_or_protected_free_floor')
def write(name,obj,start):
 raw=obj if isinstance(obj,bytes) else (json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode();guard(start,len(raw))
 with (OUT/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def emit(record,start):
 b=(json.dumps(record,ensure_ascii=False)+'\n').encode();guard(start,len(b))
 with (OUT/'pages.jsonl').open('ab') as f:f.write(b);f.flush()
def terminal(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('terminal_slot')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def worker(a):
 start=float(a.start);framer=None;segments=[]
 def stop(s,f):raise TimeoutError('worker_alarm')
 signal.signal(signal.SIGALRM,stop)
 try:
  remaining=115-(clk()-start)
  if remaining<=0:raise TimeoutError('expired_before_worker_preflight')
  signal.setitimer(signal.ITIMER_REAL,remaining)
  plan=verify(a.code_pins_sha256,a.profile_sha256);binding=verify_binding(a.source_binding,a.source_binding_sha256,a.profile_sha256)
  if os.getppid()!=a.supervisor_pid:raise ValueError('parent_identity')
  framer=core.Framer(lambda p:emit(p,start));groups=plan['groups'];sequence=[]
  if groups[0]['start']:sequence.append({'kind':'header','start':0,'end_exclusive':groups[0]['start'],'rows':[]})
  sequence.extend({'kind':'indexed_group','group':i+1,**g} for i,g in enumerate(groups));compressed=0
  fd=os.open(SOURCE,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd,'rb') as f:
   if stat_id(os.fstat(f.fileno()))!=binding['source_stat']:raise ValueError('opened_descriptor_source_identity')
   for segment in sequence:
    guard(start);n=segment['end_exclusive']-segment['start']
    if f.tell()!=segment['start'] or compressed+n>LIMITS['compressed_prefix_bytes']:raise ValueError('compressed_prefix_budget_or_seek')
    raw=f.read(n);compressed+=len(raw)
    if len(raw)!=n:raise ValueError('truncated_source_prefix')
    before=len(framer.pages);framer.segment={k:segment[k] for k in ['kind','group','start','end_exclusive'] if k in segment};framer.segment['decoded_start']=framer.decoded
    receipt=core.segment_decode(raw,framer.feed,128000000-framer.decoded,lambda:guard(start));seen=framer.pages[before:];expected=[(r['page_ID'],r['title']) for r in segment['rows']]
    if [(r['page_ID'],r['title']) for r in seen]!=expected:raise ValueError('exact_native_page_ID_title_order_vs_index_group')
    if framer.active is not None or len(framer.stack)!=1:raise ValueError('indexed_group_ends_inside_native_element')
    segments.append({'kind':segment['kind'],'group':segment.get('group'),'start':segment['start'],'end_exclusive':segment['end_exclusive'],'indexed_rows':len(expected),'native_pages':len(seen),**receipt})
   if f.tell()!=plan['XML_prefix_end_exclusive'] or stat_id(os.fstat(f.fileno()))!=binding['source_stat']:raise ValueError('source_prefix_end_or_stat_changed')
  report=framer.finish();guard(start);verify_binding(a.source_binding,a.source_binding_sha256,a.profile_sha256);verify(a.code_pins_sha256,a.profile_sha256)
  write('captured-original-header-prefix.xml',framer.header,start);write('header-and-siteinfo.json',report,start);write('segment-reconciliation.json',segments,start)
  terminal('result.json',{'status':'COMPLETE_PREFIX_ONLY_NATIVE_FRAME_NO_ADMISSION','scope':'First16fixedindexgroups; no globalXMLvalidity/uniqueIDs/articles/English/proseyield claim; no inventedrootclosing or namespace','source_archive_SHA256_inherited_verified_completion':binding['archive_SHA256'],'source_binding_SHA256':a.source_binding_sha256,'profile_SHA256':a.profile_sha256,'code_pins_SHA256':a.code_pins_sha256,'additional_full_archive_verification_read_bytes':0,'compressed_prefix_bytes_read':compressed,'decoded_prefix_bytes':framer.decoded,'indexed_groups':16,'native_pages':len(framer.pages),'all_types_counts':dict(framer.counts),'all_selected_members_CRC_EOF_verified':True,'all_index_groups_exact_native_ID_title_reconciled':True,'prefix_page_revision_IDs_unique_only':True,'root_left_open':not framer.root_closed,'elapsed_seconds':clk()-start,'new_admitted_documents':0,'new_admitted_tokens':0})
 except BaseException as e:
  terminal('result.json',{'status':'TERMINAL_PARTIAL_PREFIX_NO_RETRY_NO_GLOBALCLAIM','error':type(e).__name__+':'+str(e)[:1500],'completed_segments':len(segments),'completed_pages':len(framer.pages) if framer is not None else 0,'new_admitted_documents':0});raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
def kill(c):
 if c.poll() is None:
  try:os.killpg(c.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 c.wait(timeout=3)
def supervise(a):
 start=clk();child=None;created=False;peak=0;old={}
 def stop(s,f):raise TimeoutError('external120seconds_or_signal')
 try:
  for s in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[s]=signal.signal(s,stop)
  remaining=120-(clk()-start)
  if remaining<=0:raise TimeoutError('expired_before_preflight')
  signal.setitimer(signal.ITIMER_REAL,remaining)
  verify(a.code_pins_sha256,a.profile_sha256);verify_binding(a.source_binding,a.source_binding_sha256,a.profile_sha256)
  if OUT.exists() or OUT.is_symlink():raise ValueError('once_only_output')
  if size(ROOT)+16000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+16000000:raise ValueError('disk_intake_reserves')
  OUT.mkdir();created=True
  for name,n in SLOTS.items():(OUT/name).write_bytes(b' '*n)
  child=subprocess.Popen([sys.executable,str(HERE/'pilot.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256,'--source-binding',a.source_binding,'--source-binding-sha256',a.source_binding_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  write('ownership.json',{'worker_PID':child.pid,'supervisor_PID':os.getpid(),'start':start},start)
  while child.poll() is None:
   guard(start,seconds=120);ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],text=True,capture_output=True,check=True,timeout=1);rows=[tuple(map(int,l.split())) for l in ps.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
   while True:
    n=owned|{p for p,q,r in rows if q in owned}
    if n==owned:break
    owned=n
   rss=sum(r*1024 for p,q,r in rows if p in owned);peak=max(peak,rss)
   if rss>1000000000:raise ValueError('process_tree_RSS1GB')
   time.sleep(.2)
  child.wait(timeout=3);r=json.loads((OUT/'result.json').read_text());ok=child.returncode==0 and r.get('status')=='COMPLETE_PREFIX_ONLY_NATIVE_FRAME_NO_ADMISSION' and clk()-start<120
  terminal('supervisor.json',{'status':'COMPLETE_PREFIX_ONLY_FRAME_NO_ADMISSION' if ok else 'PARTIAL_PREFIX_NO_RETRY','worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,'result_SHA256':sha(OUT/'result.json'),'output_bytes':size(OUT),'new_admitted_documents':0});return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  if created:
   r={'status':'PARTIAL_PREFIX_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'new_admitted_documents':0}
   if (OUT/'supervisor.json').exists():terminal('supervisor.json',r)
   else:write('supervisor.json',r,start)
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  for s,h in old.items():signal.signal(s,h)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--supervisor-pid',type=int);p.add_argument('--start');p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);p.add_argument('--source-binding');p.add_argument('--source-binding-sha256');a=p.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a.code_pins_sha256,a.profile_sha256);print('PREPARED_STATIC_ONLY_NOT_DISPATCHABLE_UNTIL_FRESH_COMPLETE_SOURCE_BINDING')
