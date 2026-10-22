"""Fixed20 metadata-selected Wikibooks exact whole-text capture. No rendering/counting."""
import argparse,hashlib,json,re,os,pathlib,platform,shutil,signal,subprocess,sys,time,sqlite3,_sqlite3
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'wikibooks-heading-context-development-whole20-v1'
SELECTION=HERE;SCREEN=ROOT/'wikibooks-language-token-v1/screening.sqlite3';FINAL=ROOT/'wikibooks-global-finalization-v3/finalized.sqlite3'
LIMITS={'worker_seconds':55,'external_seconds':60,'output_bytes':5000000,'observed_tree_RSS_bytes':1000000000,'exact_records':20,'exact_source_bytes':60972,'stored_M1_tokens':20313,'per_document_UTF8_cap':2000000,'per_source_JSON_cap':4000000}
FREE=53474836480;SLOTS={'supervisor.json':32768,'result.json':65536};CLOCK=lambda:time.clock_gettime(time.CLOCK_MONOTONIC)
PROPOSAL_SHA='d8de7019d16a47b1bf89eac49d6a940ceceb0068c7fd125d8178e3f7d142e90d'
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  while chunk:=f.read(65536):h.update(chunk)
 return h.hexdigest()
def runtime():return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'platform':platform.platform(),'sqlite':sqlite3.sqlite_version}
def ro(p):
 c=sqlite3.connect(pathlib.Path(p).resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;c.execute('pragma query_only=ON');c.execute('pragma cache_size=-2048');return c
def source_database_paths():
 return set(json.loads((HERE/'selected.metadata.json').read_text())['source_DB_SHA256_inherited_completed_triage_not_rehashed_in_preparation'])
def expected_inventory():
 paths={HERE/x for x in ['capture.py','checks.py','hash_cases.py','extra_checks.py','profile.json','runtime.json','pins.py','prepare_metadata.py','selected.metadata.json','evidence-pins.json']}
 paths|={pathlib.Path(x) for x in source_database_paths()}
 paths|={pathlib.Path(x) for x in json.loads((HERE/'evidence-pins.json').read_text())}
 paths|={BASE/'disk-budget.json',pathlib.Path(sys.executable).resolve()}
 for m in [argparse,hashlib,json,shutil,signal,subprocess,platform,sqlite3,_sqlite3]:
  if getattr(m,'__file__',None):paths.add(pathlib.Path(m.__file__).resolve())
 return {str(p.resolve()) for p in paths}
def verify(a,metadata_only=False):
 import pins;pins.verify(a.code_pins_sha256,metadata_only=metadata_only)
 if sha(HERE/'profile.json')!=a.profile_sha256 or sha(HERE/'selected.metadata.json')!=PROPOSAL_SHA:raise ValueError('external_profile_or_selection_digest')
 profile=json.loads((HERE/'profile.json').read_text());prop=json.loads((HERE/'selected.metadata.json').read_text())
 if profile['limits']!=LIMITS or profile['output']!=str(OUT) or json.loads((HERE/'runtime.json').read_text())!=runtime():raise ValueError('fixed_limits_runtime_output')
 selected=prop['selected']
 if len(selected)!=20 or len({r['source_ordinal'] for r in selected})!=20 or sum(r['utf8_bytes'] for r in selected)!=60972 or sum(r['content_tokens'] for r in selected)!=20313 or prop['strata']!={'empty_heading':10,'definition_metadata_without_empty_heading':5,'neither_diagnostic':5}:raise ValueError('fixed20_metadata_frame')
 for row in selected:
  if not row.get('expected_finalizer_page') or not row.get('expected_finalizer_role') or row['source_shard']['SHA256']!=prop['source_DB_SHA256_inherited_completed_triage_not_rehashed_in_preparation'][row['source_shard']['path']]:raise ValueError('all_selected_source_owner_and_holds_bound')
 return selected
class SelectedHold(Exception):pass
def same(expected,actual,fields,label):
 if any(expected[k]!=actual[k] for k in fields):raise SelectedHold(label)
def read_one(expected):
 """Called only after worker pins+parent dispatch; preparation fixtures synthetic."""
 ordinal=expected['source_ordinal'];observed={}
 with ro(SCREEN) as c:
  row=c.execute('select * from docs where source_ordinal=?',(ordinal,)).fetchone()
  if row is None:raise SelectedHold('current_language_metadata_missing')
  screen=dict(row)
 same(expected,screen,list(screen),'screening_metadata_changed')
 with ro(FINAL) as c:
  row=c.execute('select * from pages where source_ordinal=?',(ordinal,)).fetchone();f=c.execute('select * from final_pages where source_ordinal=?',(ordinal,)).fetchone()
  if row is None or f is None:raise SelectedHold('current_finalizer_identity_unavailable')
  final=dict(row);finalrole=dict(f)
 same(expected['expected_finalizer_page'],final,list(final),'current_finalizer_page_holds_or_identity_changed')
 same(expected['expected_finalizer_role'],finalrole,list(finalrole),'current_finalizer_role_holds_or_owner_changed')
 same(expected,final,['source_ordinal','page_id','revision_id','family','title','text_sha256','characters','utf8_bytes'],'current_finalizer_metadata_changed')
 with ro(expected['source_shard']['path']) as c:
  row=c.execute('select source_ordinal,page_id,revision_id,family,length(cast(data as blob)) as JSON_bytes from rendered where source_ordinal=?',(ordinal,)).fetchone()
  if row is None:raise SelectedHold('selected_original_renderer_row_unavailable')
  same(expected,dict(row),['source_ordinal','page_id','revision_id','family'],'renderer_index_identity_changed')
  if row['JSON_bytes']>LIMITS['per_source_JSON_cap']:raise SelectedHold('native_JSON_exceeds_frozen4MB_recordcap')
  if expected['utf8_bytes']>LIMITS['per_document_UTF8_cap']:raise SelectedHold('whole_original_document_exceeds2MB_no_crop')
  JSON_bytes=row['JSON_bytes'];value=c.execute('select data from rendered where source_ordinal=?',(ordinal,)).fetchone()[0]
  if not isinstance(value,str):raise SelectedHold('native_JSON_not_text')
  native=value.encode('utf8');obj=json.loads(value)
  if len(native)!=JSON_bytes:raise SelectedHold('native_JSON_length_changed')
  blockrows=[dict(x) for x in c.execute('select * from blocks where source_ordinal=? order by ordinal limit 100001',(ordinal,))]
  if len(blockrows)>100000:raise SelectedHold('source_block_inventory_exceeds100000_no_truncation')
 if not isinstance(obj,dict) or not isinstance(obj.get('text'),str):raise SelectedHold('native_text_missing_or_wrong_type')
 text=obj['text'];body=text.encode('utf8')
 if len(body)>LIMITS['per_document_UTF8_cap']:raise SelectedHold('actual_whole_text_exceeds2MB_no_crop')
 if (obj.get('canonical_source_ordinal'),obj.get('page_id'),obj.get('revision_id'),obj.get('family_id'),obj.get('title'),obj.get('extracted_text_sha256'),obj.get('text_unicode_characters'),obj.get('text_UTF8_bytes'),obj.get('training_admitted'))!=(ordinal,expected['page_id'],expected['revision_id'],expected['family'],expected['title'],expected['text_sha256'],expected['characters'],expected['utf8_bytes'],False):raise SelectedHold('native_record_metadata_binding')
 if hashlib.sha256(body).hexdigest()!=expected['text_sha256'] or len(body)!=expected['utf8_bytes'] or len(text)!=expected['characters']:raise SelectedHold('whole_text_hash_length_binding')
 for n,b in enumerate(blockrows):
  if b['ordinal']!=n or b['source_ordinal']!=ordinal or b['start']!=(0 if n==0 else blockrows[n-1]['end']+2) or not 0<=b['start']<=b['end']<=len(text) or b['characters']!=b['end']-b['start'] or hashlib.sha256(text[b['start']:b['end']].encode()).hexdigest()!=b['hash']:raise SelectedHold('block_offset_hash_length_binding')
 if '\n\n'.join(text[b['start']:b['end']] for b in blockrows)!=text:raise SelectedHold('whole_block_partition_and_separators')
 return native,body,{'screening':screen,'finalizer_page':final,'finalizer_role':finalrole,'blocks':blockrows,'original_source_location_fields':{k:obj.get(k) for k in ['archive_sha256','member','member_ordinal','line','record_sha256','record_bytes','html_sha256','wikitext_sha256','renderer_sha256','url','revision_url','license_original_metadata','structural_holds','prior_v3_holds']},'native_record_SHA256':hashlib.sha256(native).hexdigest()}

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

def write_raw(name,data,start):
 guard(start,len(data))
 with (OUT/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def worker(a):
 start=float(a.start);done=[];old={}
 def stop(s,f):raise TimeoutError('worker_deadline_or_signal')
 try:
  for s in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:old[s]=signal.signal(s,stop)
  remaining=LIMITS['worker_seconds']-(CLOCK()-start)
  if remaining<=0:raise TimeoutError('worker_expired_before_preflight')
  signal.setitimer(signal.ITIMER_REAL,remaining);selected=verify(a)
  if os.getppid()!=a.supervisor_pid:raise ValueError('owned_parent_required')
  for expected in selected:
   guard(start);ordinal=expected['source_ordinal'];receipt={'selection':expected,'source_ordinal':ordinal,'status':'HELD_NOT_CAPTURED','not_acceptance':True,'original_holds_preserved':True,'no_tokenization_or_language_rerun':True,'new_admitted_documents':0}
   try:
    native,body,metadata=read_one(expected)
    # Reserve all this unit's evidence and metadata before either original is written.
    estimated=len(native)+len(body)+len(json.dumps(metadata,ensure_ascii=False).encode())+len(json.dumps(expected,ensure_ascii=False).encode())+20000
    if size(OUT)+estimated>LIMITS['output_bytes']-131072:raise SelectedHold('aggregate5MB_whole_capture_cannot_fit_no_partial_body')
   except SelectedHold as e:receipt['hold_reason']=str(e)
   else:
    receipt.update(status='WHOLE_ORIGINAL_TEXT_CAPTURED_DEVELOPMENT_ONLY',body_file=f'{ordinal}.txt',native_record_file=f'{ordinal}.native.json',metadata=metadata,body_SHA256=hashlib.sha256(body).hexdigest(),body_bytes=len(body),native_record_bytes=len(native))
    write_raw(receipt['native_record_file'],native,start);write_raw(receipt['body_file'],body,start)
   write(f'{ordinal}.json',receipt,start);done.append({'ordinal':ordinal,'status':receipt['status'],'receipt_file':f'{ordinal}.json','receipt_SHA256':sha(OUT/f'{ordinal}.json')})
  verify(a);guard(start)
  terminal('result.json',{'status':'COMPLETE_FIXED20_WHOLE_CAPTURE_DEVELOPMENT_ONLY','records':done,'selected_count':20,'whole_captured':sum(x['status']=='WHOLE_ORIGINAL_TEXT_CAPTURED_DEVELOPMENT_ONLY' for x in done),'held_outcomes':sum(x['status']=='HELD_NOT_CAPTURED' for x in done),'all20_fixed_outcomes_no_replacements':True,'whole_text_captured_bytes':sum((OUT/(str(x['ordinal'])+'.txt')).stat().st_size for x in done if x['status']=='WHOLE_ORIGINAL_TEXT_CAPTURED_DEVELOPMENT_ONLY'),'selected_stored_M1_tokens_diagnostic':20313,'not_retokenized':True,'all_inputs_rechecked':True,'development_context':'Frozen10emptyheading+5definitionmetadataonly+5neither;dd/dtdefinitionflags_semanticneutral_notacceptance','elapsed_seconds':CLOCK()-start,'network_requests':0,'global_ledger_writes':0,'new_admitted_documents':0,'new_admitted_tokens':0})
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
def parse_rss_snapshot(snapshot,root,required_worker=None):
 if not isinstance(snapshot,str) or len(snapshot)>1048576:raise ValueError('invalid_or_unbounded_RSS_snapshot')
 rows={}
 for line in snapshot.splitlines():
  if not line.strip():continue
  fields=line.split()
  if len(fields)!=3 or any(re.fullmatch('[0-9]+',v) is None for v in fields):raise ValueError('malformed_RSS_snapshot')
  pid,ppid,rss=map(int,fields)
  if pid<=0 or pid==ppid or pid in rows:raise ValueError('invalid_duplicate_or_selfparent_RSS_PID')
  rows[pid]=(ppid,rss)
 if root not in rows or rows[root][1]<=0:raise ValueError('missing_or_zero_root_RSS')
 owned={root}
 while True:
  n=owned|{p for p,(q,r) in rows.items() if q in owned}
  if n==owned:break
  owned=n
 if required_worker is not None and (required_worker not in owned or rows[required_worker][1]<=0):raise ValueError('missing_unowned_or_zero_live_worker_RSS')
 return sum(rows[p][1]*1024 for p in owned)
def tree_rss(child=None):
 p=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
 return parse_rss_snapshot(p.stdout,os.getpid(),child.pid if child is not None and child.poll() is None else None)
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
  child=subprocess.Popen([sys.executable,'-I','-B',str(HERE/'capture.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  write('ownership.json',{'supervisor_PID':os.getpid(),'worker_PID':child.pid,'started_monotonic':start},start)
  while child.poll() is None:
   if CLOCK()-start>=LIMITS['external_seconds']:raise TimeoutError('external60seconds')
   if size(OUT)>LIMITS['output_bytes']:raise ValueError('external_output5MB')
   rss=tree_rss(child);peak=max(peak,rss)
   if rss>LIMITS['observed_tree_RSS_bytes']:raise ValueError('tree_RSS1GB')
   time.sleep(.1)
  child.wait(timeout=3);r=json.loads((OUT/'result.json').read_text());ok=child.returncode==0 and r.get('status')=='COMPLETE_FIXED20_WHOLE_CAPTURE_DEVELOPMENT_ONLY' and CLOCK()-start<LIMITS['external_seconds']
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
 else:verify(a,metadata_only=True);print('PREPARED_METADATA_ONLY_SOURCE_DB_DIGESTS_INHERITED_NOT_FRESHLY_REHASHED_NO_SELECTED_BODY_READ')
