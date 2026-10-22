import argparse,hashlib,json,os,pathlib,platform,shutil,signal,subprocess,sys,time,importlib,unicodedata,re,html,datetime,_datetime,collections
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'enwiki-native20-integrated-companions-development-v5'
SAVED=ROOT/'enwiki-native20-generic-AST-development-v4';REF=BASE/'enwiki-page-local-reference-preparation-v2';RULES=BASE/'enwiki-structural-companion-policy-preparation-v1'
SHORT=BASE/'enwiki-short-footnote-preparation-v2';YEAR=BASE/'enwiki-literal-year-qualifier-preparation-v1'
POLICY=BASE/'enwiki-generic-AST-policy-preparation-v4';SOURCE=ROOT/'enwiki-native-20row-capture-v1';TARGET=BASE/'tool-dependencies/mwparserfromhell-0.7.2'
LIMITS={'worker_seconds':55,'external_seconds':60,'output_bytes':5000000,'observed_tree_RSS_bytes':1000000000,'exact_records':20,'exact_source_bytes':114599,'rendered_pending_records':5,'preserved_redirects':9,'preserved_nonarticles':6}
FREE=53474836480;SLOTS={'result.json':65536,'supervisor.json':32768};CLOCK=time.monotonic

def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def runtime():return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'platform':platform.platform()}
def expected_inventory():
 pp=json.loads((POLICY/'input-pins.json').read_text())
 paths={REPO/x for x in list(pp['native20_files'])+list(pp['isolated_parser_files'])}
 paths|={HERE/x for x in ['run.py','checks.py','core_checks.py','integrated_core.py','profile.json','runtime.json','pins.py']}
 paths|={REF/x for x in ['reference_core.py','proposal.json','profile.json','code-pins.json','readiness.json']}
 paths|={SHORT/x for x in ['short_core.py','proposal.json','profile.json','code-pins.json','readiness.json']}
 paths|={YEAR/x for x in ['qualifier_core.py','proposal.json','code-pins.json','readiness.json']}
 paths|={RULES/x for x in ['rules.py','proposal.json','manifest.json']}
 paths|={q for q in SAVED.glob('row-*.json')}|{SAVED/'result.json',SAVED/'supervisor.json'}
 paths|={POLICY/x for x in ['input-pins.json','policy.json','policy_core.py','manifest.json','check-results.json']}
 paths|={BASE/'disk-budget.json',pathlib.Path(sys.executable).resolve()}
 for m in [argparse,hashlib,json,shutil,signal,subprocess,platform,importlib,unicodedata,re,html,datetime,_datetime,collections]:
  if getattr(m,'__file__',None):paths.add(pathlib.Path(m.__file__).resolve())
 return {str(p.resolve()) for p in paths}
def parser_preflight():
 sys.path.insert(0,str(TARGET));sys.path.insert(0,str(POLICY))
 m=importlib.import_module('mwparserfromhell');core=importlib.import_module('policy_core')
 if m.__version__!='0.7.2' or not pathlib.Path(m.__file__).resolve().is_relative_to(TARGET.resolve()) or not m.parser.use_c:raise ValueError('isolated_C_parser_origin')
 if pathlib.Path(core.__file__).resolve()!=POLICY/'policy_core.py':raise ValueError('policy_origin')
 fixture='One [[word|word]].\n\n== Whole ==\nSecond paragraph.';r=core.sections(fixture,m)
 if not r['exact_roundtrip'] or ''.join(s['raw'] for s in r['sections'])!=fixture:raise ValueError('actual_runtime_synthetic_preflight')
 return m,core

def selection(rows):
 if len(rows)!=20 or len({r['selected_index_row']['row_ordinal'] for r in rows})!=20:raise ValueError('exact20distinctrowidentities')
 counts={'redirect':0,'nonarticle':0,'pending':0};total=0;ready=[]
 for r in rows:
  row=r['selected_index_row']['row_ordinal'];q=json.loads((SOURCE/f'row-{row}.json').read_text())
  if q!=r:raise ValueError('all20_vs_exact_individual_native_record')
  raw=SOURCE/r['source_text_file']
  if raw.name!=f'row-{row}.source-text.utf8' or raw.parent!=SOURCE:raise ValueError('literal_source_file_binding')
  if raw.stat().st_size!=r['source_text']['bytes'] or sha(raw)!=r['source_text']['local_SHA256']:raise ValueError('exactsourcehash_size')
  total+=raw.stat().st_size
  if r['native_redirect_attributes'] is not None:role='redirect'
  elif r['native_ns']!='0':role='nonarticle'
  elif r['holds']==[] and r['native_revision']['model']=='wikitext' and r['native_revision']['format']=='text/x-wiki' and r['status']=='NATIVE_SOURCE_CAPTURED_PENDING_QUALITY_RIGHTS_DEPENDENCY_REVIEW':role='pending'
  else:raise ValueError('unexpected_role_no_replacement')
  counts[role]+=1;ready.append({'record':r,'source':raw,'role':role})
 if counts!={'redirect':9,'nonarticle':6,'pending':5} or total!=114599:raise ValueError('fixednegativecounts_or_sourcebytes')
 return ready

def verify(a):
 import pins;pins.verify(a.code_pins_sha256)
 if sha(HERE/'profile.json')!=a.profile_sha256:raise ValueError('external_profile_digest')
 p=json.loads((HERE/'profile.json').read_text())
 if p['limits']!=LIMITS or p['output']!=str(OUT) or json.loads((HERE/'runtime.json').read_text())!=runtime():raise ValueError('fixed_limits_runtime_output')
 m,core=parser_preflight();integrated,reference,rules=integration_preflight(m,core);rows=json.loads((SOURCE/'all20-native-decisions.json').read_text());return selection(rows),m,core,integrated,reference,rules

def integration_preflight(m,literal):
 sys.path.insert(0,str(REF));sys.path.insert(0,str(RULES));sys.path.insert(0,str(SHORT));sys.path.insert(0,str(YEAR));sys.path.insert(0,str(HERE))
 integrated=importlib.import_module('integrated_core');reference=importlib.import_module('reference_core');rules=importlib.import_module('rules');short=importlib.import_module('short_core');year=importlib.import_module('qualifier_core')
 if pathlib.Path(short.__file__).resolve()!=SHORT/'short_core.py' or pathlib.Path(year.__file__).resolve()!=YEAR/'qualifier_core.py':raise ValueError('exact_shortnote_and_year_origins')
 if pathlib.Path(integrated.__file__).resolve()!=HERE/'integrated_core.py' or pathlib.Path(reference.__file__).resolve()!=REF/'reference_core.py' or pathlib.Path(rules.__file__).resolve()!=RULES/'rules.py':raise ValueError('exact_integrated_dependency_origins')
 r=integrated.develop_page('Complete prose<ref>Literal source.</ref>.',m,literal,reference,rules)
 if r['sections'][0]['provisional_prose_preview']!='Complete prose⟦ref:g0:1⟧.':raise ValueError('actual_integrated_synthetic_runtime_preflight')
 q=integrated.develop_page('A<ref>{{cite web|title={{unknown}}}}</ref>.',m,literal,reference,rules)
 if q['sections'][0]['provisional_prose_preview']!='A⟦ref:g0:1⟧.' or not q['sections'][0]['reference_semantic_companion_holds']:raise ValueError('actual_component_hold_union_runtime_preflight')
 q=integrated.develop_page('A<ref>{{cite web|title=T|url=https://example.org}}</ref> {{As of|2011}}, statement{{sfn|Smith|2020|p=2}}.\n== Sources ==\n* {{cite book|last=Smith|year=2020|title=T}}',m,literal,reference,rules)
 if q['sections'][0]['provisional_prose_preview']!='A⟦ref:g0:1⟧ As of 2011, statement⟦sfn:1⟧.\n':raise ValueError('combined_shortnote_year_owned_reference_runtime_preflight')
 return integrated,reference,rules

def saved_regions(record):
 row=record['selected_index_row']['row_ordinal'];r=json.loads((SAVED/f'row-{row}.json').read_text())
 if r['preserved_role']!='pending' or r['source_text_SHA256']!=record['source_text']['local_SHA256'] or r['native_page_ID']!=record['native_page_id'] or r['native_revision_ID']!=record['native_revision']['id']:raise ValueError('saved_v4_identity')
 return [s['source_char_span'] for s in r['frame']['sections']]

def size(p):return sum(x.stat().st_size for x in p.rglob('*') if x.is_file())
def disk():
 if size(ROOT)+5000000>64000000000 or shutil.disk_usage(ROOT).free<FREE+5000000:raise ValueError('processedcap_weights_scratch_freefloor')
def guard(start,n=0):
 if CLOCK()-start>=LIMITS['worker_seconds']:raise TimeoutError('worker55seconds')
 if size(OUT)+n>LIMITS['output_bytes']-131072 or shutil.disk_usage(ROOT).free<FREE+n:raise ValueError('output5MB_freefloor')
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
  rows,m,core,integrated,reference,rules=verify(a)
  if os.getppid()!=a.supervisor_pid:raise ValueError('owned_parent_required')
  for item in rows:
   guard(start);r=item['record'];row=r['selected_index_row']['row_ordinal'];role=item['role']
   result={'row_ordinal':row,'native_page_ID':r['native_page_id'],'native_revision_ID':r['native_revision']['id'],'native_title':r['native_title'],'prior_status':r['status'],'prior_holds':r['holds'],'preserved_role':role,'source_text_SHA256':r['source_text']['local_SHA256'],'existing_source_rights_quality_leakage_holds_retained':True,'no_admission':True}
   if role=='pending':
    raw=item['source'].read_bytes()
    if len(raw)!=r['source_text']['bytes'] or hashlib.sha256(raw).hexdigest()!=r['source_text']['local_SHA256']:raise ValueError('read_payload_sourcehash_size')
    frame=integrated.develop_page(raw.decode('utf8'),m,core,reference,rules,saved_regions(r))
    if ''.join(s['raw'] for s in frame['sections']).encode('utf8')!=raw:raise ValueError('allsourcebytes_inverse')
    result['frame']=frame;result['status']='DEVELOPMENT_SOURCE_BOUND_PROSE_COMPANION_BUNDLES_NO_ADMISSION'
   else:result['status']='PRIOR_REDIRECT_OR_NONARTICLE_PRESERVED_NO_EXTRACTION'
   write(f'row-{row}.json',result,start);done.append({'row':row,'role':role,'file':f'row-{row}.json','SHA256':sha(OUT/f'row-{row}.json')})
  verify(a);guard(start)
  terminal('result.json',{'status':'COMPLETE_NATIVE20_INTEGRATED_COMPANIONS_DEVELOPMENT_ONLY','records':done,'records_count':len(done),'no_extraction_of_negative15':True,'rendered_pending5':5,'elapsed_seconds':CLOCK()-start,'network_requests':0,'global_ledger_writes':0,'new_admitted_documents':0,'new_admitted_tokens':0})
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
 start=CLOCK();child=None;created=False;peak=0;old={}
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
   if size(OUT)>LIMITS['output_bytes']:raise ValueError('external_output5MB')
   rss=tree_rss();peak=max(peak,rss)
   if rss>LIMITS['observed_tree_RSS_bytes']:raise ValueError('tree_RSS1GB')
   time.sleep(.1)
  child.wait(timeout=3);r=json.loads((OUT/'result.json').read_text());ok=child.returncode==0 and r.get('status')=='COMPLETE_NATIVE20_INTEGRATED_COMPANIONS_DEVELOPMENT_ONLY' and CLOCK()-start<LIMITS['external_seconds']
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
