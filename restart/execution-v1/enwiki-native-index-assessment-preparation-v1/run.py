"""Supervised one-pass native index assessment. No network/XML/model operations."""
import argparse,json,pathlib,hashlib,os,subprocess,signal,sys,time,re
import core
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake';OUT=ROOT/'enwiki-native-index-assessment-v1';DOWNLOAD=ROOT/'enwiki-native-index-20260801-v1';INDEX=DOWNLOAD/'enwiki-20260801-pages-articles-multistream-index.txt.bz2';FREE=53474836480
SLOTS={'result.json':32768,'supervisor.json':16384}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def size(p):return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
def inventory():return {str(p.resolve()) for p in [HERE/f for f in ['core.py','run.py','checks.py','code_guard.py','profile.json']]+[DOWNLOAD/'worker-result.json',DOWNLOAD/'supervisor-result.json',ROOT/'enwiki-native-html-option-v1/acquisition-options.json',BASE/'disk-budget.json']}
def verify(code,prof):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=prof:raise ValueError('external_profile_pin')
 p=json.loads((HERE/'profile.json').read_text());w=json.loads((DOWNLOAD/'worker-result.json').read_text())
 if p['limits']!=core.CAPS or w['status']!='COMPLETE_COMPRESSED_NATIVE_INDEX_ONLY_NO_ADMISSION' or w['local_SHA256']!=p['source_SHA256'] or w['bytes']!=p['source_bytes'] or w['MD5']!=p['publisher_MD5'] or w['SHA1']!=p['publisher_SHA1'] or w['url']!=p['source_URL']:raise ValueError('source_receipt_or_caps')
 if INDEX.is_symlink() or not INDEX.is_file() or INDEX.stat().st_size!=p['source_bytes']:raise ValueError('source_index_path_or_size')
 return p

def terminal(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('terminal_slot')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def write(name,obj):
 b=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode()
 if size(OUT)+len(b)>16000000-65536:raise ValueError('evidence_cap')
 with (OUT/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def worker(a):
 p=verify(a.code_pins_sha256,a.profile_sha256);start=float(a.start);stats={}
 if os.getppid()!=a.supervisor_pid:raise ValueError('parent_identity')
 before=INDEX.stat();identity=(before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)
 def check():
  if clk()-start>=570:raise TimeoutError('work570second_cap')
 try:
  with INDEX.open('rb') as f:r=core.assess(f,p['source_SHA256'],p['publisher_MD5'],p['publisher_SHA1'],p['source_bytes'],p['publisher_XML_bytes'],p['sampling_seed_hex'],check=check,progress=stats)
  after=INDEX.stat()
  if identity!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('source_changed_during_stream')
  if len(r['samples'])!=20:raise ValueError('not20_rows_source_too_small')
  verify(a.code_pins_sha256,a.profile_sha256)
  write('selection.json',{'status':'FROZEN20_LOWEST_HASH_COMPLETE_INDEX_ROW_DISCOVERY_NOT_ARTICLES','seed_hex':p['sampling_seed_hex'],'priority_formula':'SHA256(UTF8(enwiki-native-index-row-discovery-v1 + LF + seedhex + LF + sourceSHA256 + LF + decimal1basedRowOrdinal)); ascendinghash thenrowordinal','source_SHA256':p['source_SHA256'],'source_receipt_sha256':sha(DOWNLOAD/'worker-result.json'),'profile_sha256':a.profile_sha256,'all_fullstream_stats':r['stats'],'records':r['samples'],'sample_rows':20,'raw_line_hash_includes_newline_if_present':True,'XML_file_checksums_verified':False,'index_page_ID_uniqueness_proven':False,'namespace_or_revision_known':False,'metadata_only_no_XML_access':True})
  terminal('result.json',{'status':'COMPLETE_ONE_PASS_INDEX_ASSESSMENT_ROW_SAMPLE_NO_ADMISSION','stats':r['stats'],'all_BZ2_EOF_CRC_verified':r['all_bzip2_members_EOF_and_CRC_verified'],'trailingdata_absent':True,'offsets_nondecreasing':True,'source_SHA256':r['source_SHA256'],'publisher_MD5_match':r['source_MD5']==p['publisher_MD5'],'publisher_SHA1_match':r['source_SHA1']==p['publisher_SHA1'],'selection_sha256':sha(OUT/'selection.json'),'elapsed_seconds':clk()-start,'source_passes':1,'source_index_unchanged':True,'counts_are_rows_and_distinct_offset_groups_not_articles':True,'global_page_ID_uniqueness_proven':False,'XML_fullfile_checksums_verified':False,'new_admitted_documents':0,'new_admitted_tokens':0,'network_requests':0,'XML_requests':0,'models_initialized':0})
 except BaseException as e:
  terminal('result.json',{'status':'PARTIAL_INDEX_ASSESSMENT_NO_FULLFRAME_OR_SAMPLE_CLAIM_NO_RETRY','error':type(e).__name__+':'+str(e)[:1500],'observed_partial_stats':stats,'new_admitted_documents':0,'new_admitted_tokens':0});raise

def kill(child):
 if child.poll() is None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 child.wait(timeout=3)
def supervise(a):
 start=clk();verify(a.code_pins_sha256,a.profile_sha256)
 if OUT.exists():raise ValueError('existing_output_no_retry')
 import shutil
 if shutil.disk_usage(ROOT).free<FREE+16000000:raise ValueError('free_weights_scratch_reserves')
 OUT.mkdir()
 for name,n in SLOTS.items():
  with (OUT/name).open('xb') as f:f.write(b' '*n);f.flush();os.fsync(f.fileno())
 child=None;peak=0;reason=None
 def stop(s,f):raise RuntimeError('external_signal_'+str(s))
 old={s:signal.signal(s,stop) for s in [signal.SIGTERM,signal.SIGINT]}
 try:
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,str(HERE/'run.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  write('ownership.json',{'supervisor_pid':os.getpid(),'worker_pid':child.pid,'shared_start':start,'profile_sha256':a.profile_sha256,'code_pins_sha256':a.code_pins_sha256})
  while child.poll() is None:
   if clk()-start>=570:reason='work570second_cap';break
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rows=[tuple(map(int,l.split())) for l in ps.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
   if os.getpid() not in {p for p,q,r in rows}:raise RuntimeError('supervisor_missing_process_snapshot')
   while True:
    more=owned|{p for p,q,r in rows if q in owned}
    if more==owned:break
    owned=more
   rss=sum(r*1024 for p,q,r in rows if p in owned);peak=max(peak,rss)
   if rss>1000000000:reason='RSS1GB';break
   if size(OUT)>16000000 or shutil.disk_usage(ROOT).free<FREE:reason='evidence_or_free_cap';break
   time.sleep(.5)
  if reason:kill(child)
  else:child.wait(timeout=3)
  text=(OUT/'result.json').read_text();r=json.loads(text) if text.strip() else {};ok=child.returncode==0 and reason is None and r.get('status')=='COMPLETE_ONE_PASS_INDEX_ASSESSMENT_ROW_SAMPLE_NO_ADMISSION' and clk()-start<600
  terminal('supervisor.json',{'status':'COMPLETE_NATIVE_INDEX_ROWS_ONLY_NO_ADMISSION' if ok else 'PARTIAL_NATIVE_INDEX_NO_RETRY','reason':reason,'worker_exit_code':child.returncode,'elapsed_seconds':clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':size(OUT),'result_sha256':sha(OUT/'result.json'),'new_admitted_documents':0,'new_admitted_tokens':0});return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  terminal('supervisor.json',{'status':'PARTIAL_NATIVE_INDEX_NO_RETRY','reason':type(e).__name__+':'+str(e)[:1500],'elapsed_seconds':clk()-start,'new_admitted_documents':0});raise
 finally:
  for s,h in old.items():signal.signal(s,h)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');ap.add_argument('--worker',action='store_true');ap.add_argument('--supervisor-pid',type=int);ap.add_argument('--start');ap.add_argument('--code-pins-sha256',required=True);ap.add_argument('--profile-sha256',required=True);a=ap.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a.code_pins_sha256,a.profile_sha256);print('PINNED_ASSESSMENT_PREPARED_NO_DECODE')
