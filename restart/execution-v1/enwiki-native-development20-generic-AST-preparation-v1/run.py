import time,signal
ENTRY_START=time.monotonic()
def initial_alarm(*a):raise TimeoutError('shared_entry_deadline')
signal.signal(signal.SIGALRM,initial_alarm);signal.setitimer(signal.ITIMER_REAL,60)
import argparse,hashlib,json,os,pathlib,platform,shutil,signal,subprocess,sys,time,importlib,unicodedata
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'enwiki-native-development20-generic-AST-v1'
POLICY=BASE/'enwiki-generic-AST-policy-preparation-v4';SOURCE=ROOT/'enwiki-native-development20-maintext-v1';TARGET=BASE/'tool-dependencies/mwparserfromhell-0.7.2'
LIMITS={'worker_seconds':55,'external_seconds':60,'output_bytes':16000000,'observed_tree_RSS_bytes':1000000000,'exact_records':20,'exact_source_bytes':448915,'rendered_pending_records':11,'preserved_redirects':2,'preserved_nonarticles':2,'preserved_disambiguation':5}
FREE=53474836480;SLOTS={'result.json':65536,'supervisor.json':32768};CLOCK=time.monotonic

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def runtime():return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'platform':platform.platform()}
def expected_inventory():
 paths={HERE/x for x in ['run.py','checks.py','profile.json','runtime.json','pins.py','inputs.json']}
 paths|={POLICY/x for x in ['policy_core.py','policy.json','input-pins.json','manifest.json','check-results.json']}
 pp=json.loads((POLICY/'input-pins.json').read_text());paths|={REPO/x for x in pp['isolated_parser_files']}
 paths|={BASE/'disk-budget.json',BASE/'enwiki-native-development20-parent-whole-review-v1/review.json',BASE/'enwiki-retained-prefix-frame-preparation-v2/tree_size.py',pathlib.Path(sys.executable).resolve()}
 paths|={pathlib.Path(x) for x in json.loads((HERE/'inputs.json').read_text())['metadata_sources']}
 for m in [argparse,hashlib,json,shutil,signal,subprocess,platform,importlib,unicodedata]:
  if getattr(m,'__file__',None):paths.add(pathlib.Path(m.__file__).resolve())
 return {str(p.resolve()) for p in paths}
def parser_preflight():
 sys.path.insert(0,str(TARGET));sys.path.insert(0,str(POLICY))
 m=importlib.import_module('mwparserfromhell');core=importlib.import_module('policy_core')
 if m.__version__!='0.7.2' or not pathlib.Path(m.__file__).resolve().is_relative_to(TARGET.resolve()) or not m.parser.use_c:raise ValueError('isolated_C_parser_origin')
 if pathlib.Path(importlib.import_module('mwparserfromhell.parser._tokenizer').__file__).resolve()!=TARGET/'mwparserfromhell/parser/_tokenizer.cpython-312-darwin.so':raise ValueError('compiled_extension_exact_origin')
 if pathlib.Path(core.__file__).resolve()!=POLICY/'policy_core.py':raise ValueError('policy_origin')
 fixture='One [[word|word]].\n\n== Whole ==\nSecond paragraph.';r=core.sections(fixture,m)
 if not r['exact_roundtrip'] or ''.join(s['raw'] for s in r['sections'])!=fixture:raise ValueError('actual_runtime_synthetic_preflight')
 return m,core

def selection(rows,read_sources=False):
 if len(rows)!=20 or len({r['row_ordinal'] for r in rows})!=20 or len({r['page_ID'] for r in rows})!=20:raise ValueError('exact20distinctrow_pageidentities')
 review=json.loads((BASE/'enwiki-native-development20-parent-whole-review-v1/review.json').read_text());dis={x['page_ID']:x for x in review['reviews'] if x['development_assessment']=='DISAMBIGUATION_NONPROSE'}
 native=json.loads((SOURCE/'records.json').read_text())['records'];by={r['original_global_page_ordinal']:r for r in native};ready=[];counts={k:0 for k in ['pending','redirect','nonarticle','disambiguation']}
 for r in rows:
  q=by[r['row_ordinal']];raw=SOURCE/r['file'];st=raw.stat(follow_symlinks=False)
  if raw.is_symlink() or [st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]!=r['stat']:raise ValueError('exact_source_stat')
  if raw.name!=f"page-{r['row_ordinal']:08d}-{r['page_ID']}.wikitext.utf8" or raw.parent!=SOURCE:raise ValueError('literal_source_binding')
  if hashlib.sha256(json.dumps(q,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()!=r['source_record_SHA256']:raise ValueError('exact_native_record')
  if q['native_page_ID']!=r['page_ID'] or q['native_revision_IDs']!=[r['revision_ID']] or q['native_namespace']!=r['namespace'] or q['native_redirect']!=r['redirect'] or q['actual_main_text_SHA256']!=r['SHA256'] or q['actual_main_text_UTF8_bytes']!=r['bytes'] or q['native_model']!='wikitext' or q['native_format']!='text/x-wiki' or q['extraction_holds'] or q['page_semantic_holds']:raise ValueError('native_identity_model_source_status')
  if read_sources and sha(raw)!=r['SHA256']:raise ValueError('source_body_pin')
  role=r['role']
  expected_role='redirect' if q['native_redirect'] is not None else 'nonarticle' if q['native_namespace']!=0 else 'disambiguation' if q['native_page_ID'] in dis else 'pending'
  if role!=expected_role or role=='disambiguation' and dis[r['page_ID']]['SHA256']!=r['SHA256']:raise ValueError('parent_role_and_hash_binding')
  if role not in counts:raise ValueError('unknown_role')
  if role=='redirect' and r['redirect'] is None or role=='nonarticle' and r['namespace']==0 or role in ['pending','disambiguation'] and (r['namespace']!=0 or r['redirect'] is not None):raise ValueError('role_native_contradiction')
  counts[role]+=1
  record={'selected_index_row':{'row_ordinal':r['row_ordinal']},'native_page_id':r['page_ID'],'native_revision':{'id':r['revision_ID']},'native_title':r['title'],'status':'EXACT_NATIVE_MAIN_WIKITEXT_ONLY_PROSE_AND_QUALITY_UNREVIEWED','holds':r['prior_holds'],'source_text':{'bytes':r['bytes'],'local_SHA256':r['SHA256']},'source_binding':r}
  ready.append({'record':record,'source':raw,'role':role})
 if counts!={'redirect':2,'nonarticle':2,'disambiguation':5,'pending':11} or sum(r['bytes'] for r in rows)!=448915:raise ValueError('fixed_roles_or_bytes')
 return ready

def verify(a):
 import pins;pins.verify(a.code_pins_sha256)
 if sha(HERE/'profile.json')!=a.profile_sha256:raise ValueError('external_profile_digest')
 p=json.loads((HERE/'profile.json').read_text())
 if p['limits']!=LIMITS or p['output']!=str(OUT) or json.loads((HERE/'runtime.json').read_text())!=runtime():raise ValueError('fixed_limits_runtime_output')
 m,core=parser_preflight();rows=json.loads((HERE/'inputs.json').read_text())['records'];return selection(rows,bool(getattr(a,'execute',False) or getattr(a,'worker',False))),m,core

def size(p):
 if not p.exists():return 0
 spec=importlib.util.spec_from_file_location('bounded_census',BASE/'enwiki-retained-prefix-frame-preparation-v2/tree_size.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod.census(p)
def disk():
 if size(ROOT)+16000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+16000000:raise ValueError('processedcap_weights_scratch_freefloor')
def guard(start,n=0):
 if CLOCK()-start>=LIMITS['worker_seconds']:raise TimeoutError('worker55seconds')
 if size(OUT)+n>LIMITS['output_bytes']-131072 or shutil.disk_usage(ROOT).free<FREE+n:raise ValueError('output16MB_freefloor')
def write(name,obj,start):
 raw=(json.dumps(obj,indent=2,ensure_ascii=False)+'\n').encode();guard(start,len(raw))
 with (OUT/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
def terminal(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('reserved_terminal_slot')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def worker(a):
 start=float(a.start);done=[];old={}
 def stop(s,f):raise TimeoutError('worker_deadline_or_signal')
 try:
  for s in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[s]=signal.signal(s,stop)
  remaining=LIMITS['worker_seconds']-(CLOCK()-start)
  if remaining<=0:raise TimeoutError('worker_expired_before_preflight')
  signal.setitimer(signal.ITIMER_REAL,remaining)
  rows,m,core=verify(a)
  if os.getppid()!=a.supervisor_pid:raise ValueError('owned_parent_required')
  for item in rows:
   guard(start);r=item['record'];row=r['selected_index_row']['row_ordinal'];role=item['role']
   result={'row_ordinal':row,'native_page_ID':r['native_page_id'],'native_revision_ID':r['native_revision']['id'],'native_title':r['native_title'],'prior_status':r['status'],'prior_holds':r['holds'],'preserved_role':role,'source_text_SHA256':r['source_text']['local_SHA256'],'existing_source_rights_quality_leakage_holds_retained':True,'no_admission':True,'source_binding':r.get('source_binding')}
   if role=='pending':
    raw=item['source'].read_bytes()
    if len(raw)!=r['source_text']['bytes'] or hashlib.sha256(raw).hexdigest()!=r['source_text']['local_SHA256']:raise ValueError('read_payload_sourcehash_size')
    frame=core.sections(raw.decode('utf8'),m)
    if ''.join(s['raw'] for s in frame['sections']).encode('utf8')!=raw:raise ValueError('allsourcebytes_inverse')
    result['frame']=frame;result['status']='DEVELOPMENT_STRUCTURAL_SECTIONS_ONLY_NO_ADMISSION'
   else:result['status']='PRIOR_REDIRECT_NONARTICLE_OR_DISAMBIGUATION_WHOLEPAGE_HOLD_NO_EXTRACTION'
   write(f'row-{row}.json',result,start);done.append({'row':row,'role':role,'file':f'row-{row}.json','SHA256':sha(OUT/f'row-{row}.json')})
  verify(a);guard(start)
  terminal('result.json',{'status':'COMPLETE_NATIVE20_DEVELOPMENT_AST_SECTIONS_ONLY','records':done,'records_count':len(done),'negative_wholepage_roles_preserved':9,'diagnostic_pending_pages':11,'disambiguation_wholepage_holds':5,'elapsed_seconds':CLOCK()-start,'network_requests':0,'global_ledger_writes':0,'new_admitted_documents':0,'new_admitted_tokens':0})
 except BaseException as e:
  terminal('result.json',{'status':'PARTIAL_NO_RETRY_NO_ADMISSION','error':type(e).__name__+':'+str(e)[:1000],'completed_records':len(done),'new_admitted_documents':0});raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  for s,h in old.items():signal.signal(s,h)
def kill(child):
 if child.poll() is None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 child.wait(timeout=3)
def parse_rss_snapshot(text,root):
 rows={}
 for line in text.splitlines():
  fields=line.split()
  if not fields:continue
  if len(fields)!=3 or any(not x.isascii() or not x.isdecimal() for x in fields):raise ValueError('invalid_RSS_snapshot_row')
  pid,parent,rss=map(int,fields)
  if pid<=0 or parent<0 or pid==parent or pid in rows:raise ValueError('invalid_or_duplicate_RSS_PID')
  rows[pid]=(parent,rss)
 if root not in rows or rows[root][1]<=0:raise ValueError('missing_or_zero_supervisor_RSS_snapshot')
 owned={root}
 while True:
  updated=owned|{pid for pid,(parent,rss) in rows.items() if parent in owned}
  if updated==owned:break
  owned=updated
 return sum(rows[pid][1]*1024 for pid in owned)
def tree_rss():
 p=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
 return parse_rss_snapshot(p.stdout,os.getpid())
def supervise(a):
 start=ENTRY_START;child=None;created=False;peak=0;old={}
 def stop(s,f):raise TimeoutError('external60seconds_or_signal')
 try:
  for s in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[s]=signal.signal(s,stop)
  remaining=LIMITS['external_seconds']-(CLOCK()-start)
  if remaining<=0:raise TimeoutError('expired_before_preflight')
  signal.setitimer(signal.ITIMER_REAL,remaining)
  verify(a)
  if OUT.exists() or OUT.is_symlink():raise ValueError('once_only_output_exists')
  disk();OUT.mkdir();created=True
  for n,k in SLOTS.items():(OUT/n).write_bytes(b' '*k)
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,'-I','-B',str(HERE/'run.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  write('ownership.json',{'supervisor_PID':os.getpid(),'worker_PID':child.pid,'started_monotonic':start},start)
  while child.poll() is None:
   if CLOCK()-start>=LIMITS['external_seconds']:raise TimeoutError('external60seconds')
   if size(OUT)>LIMITS['output_bytes']:raise ValueError('external_output16MB')
   rss=tree_rss();peak=max(peak,rss)
   if rss>LIMITS['observed_tree_RSS_bytes']:raise ValueError('tree_RSS1GB')
   time.sleep(.1)
  child.wait(timeout=3);peak=max(peak,tree_rss())
  if peak>LIMITS['observed_tree_RSS_bytes'] or size(OUT)>LIMITS['output_bytes']:raise ValueError('terminal_RSS_or_output_bound')
  r=json.loads((OUT/'result.json').read_text());ok=child.returncode==0 and r.get('status')=='COMPLETE_NATIVE20_DEVELOPMENT_AST_SECTIONS_ONLY' and CLOCK()-start<LIMITS['external_seconds']
  terminal('supervisor.json',{'status':'COMPLETE_DEVELOPMENT_ONLY' if ok else 'PARTIAL_NO_RETRY','worker_exit_code':child.returncode,'worker_receipt_SHA256':sha(OUT/'result.json'),'peak_observed_tree_RSS_bytes':peak,'elapsed_seconds':CLOCK()-start,'output_bytes':size(OUT),'new_admitted_documents':0});return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  if created:
   raw={'status':'PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'child_reaped':child is None or child.poll() is not None,'new_admitted_documents':0}
   if (OUT/'supervisor.json').exists():terminal('supervisor.json',raw)
   else:write('supervisor.json',raw,start)
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  for s,h in old.items():signal.signal(s,h)
if __name__=='__main__':
 sys.path.insert(0,str(HERE));p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--start');p.add_argument('--supervisor-pid',type=int);p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);a=p.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a);print('READY_STATIC_PREFLIGHT_SYNTHETIC_ONLY_NO_NATIVE_PARSE')
