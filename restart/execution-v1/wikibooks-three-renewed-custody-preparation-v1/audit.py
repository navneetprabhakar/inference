"""Three exact Wikibooks component derivatives: frozen-M1 recount and renewed literal custody screen."""
import argparse,collections,hashlib,json,os,pathlib,re,shutil,signal,sqlite3,subprocess,sys,time
import overlap_core as core,sources
import pyarrow,pyarrow._parquet,pyarrow.lib
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'wikibooks-three-renewed-custody-v1';M0=BASE/'m0-registry-v1';LEGACY=REPO/'restart/corpus-audit-v1/audit.sqlite';OLD=ROOT/'individual-salvage-v1/overlap-v1';FREE=53474836480
LIMITS={'worker_seconds':540,'external_seconds':570,'output_bytes':32000000,'observed_RSS_bytes':1000000000,'max_document_UTF8_bytes':8000000,'max_document_words':200000,'allowlisted_large_WB_word_cap':240742,'max_unique_body_hashes':1200000,'max_records':2000000,'max_JSONL_line':16000000}
SLOTS={'result.json':131072,'supervisor.json':32768,'progress.json':8192};START=None
sha=lambda p:hashlib.file_digest(pathlib.Path(p).open('rb'),'sha256').hexdigest()
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def size(p):return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
def environment():return {'python':sys.version,'launcher':sys.executable,'prefix':sys.prefix,'pyarrow':pyarrow.__version__}
def inventory():
 p=[HERE/n for n in ['audit.py','overlap_core.py','sources.py','checks.py','code_guard.py','profile.json','candidates.json','body-sources.json','metadata-coverage.json','adapter_cases.py','lifecycle_cases.py','memory_cases.py','revision_cases.py']]+[BASE/'gutenberg-overlap-preparation-v3/audit.py',BASE/'gutenberg-overlap-preparation-v3/check_M0_roles.py',REPO/'src/slm/restart/edu_filter.py',M0/'registry.json',LEGACY,REPO/'restart/corpus-audit-v1/receipt.json',REPO/'restart/corpus-audit-v1/containment',REPO/'restart/corpus-audit-v1/containment.cpp',OLD/'protections.tsv',OLD/'protection-identities.json',ROOT/'wikibooks-global-finalization-v3/finalized.sqlite3',ROOT/'wikibooks-global-finalization-v3/result.json',ROOT/'wikibooks-canonical-candidates-v1/canonical.sqlite3',ROOT/'wikibooks-language-token-v1/screening.sqlite3',BASE/'disk-budget.json']
 p += [BASE/'wikibooks-three-component-separation-preparation-v1/code-pins.json',BASE/'wikibooks-three-component-separation-preparation-v1/profile.json',ROOT/'wikibooks-three-component-independent-verification-v1/verification.json',BASE/'wikibooks-language-token-preparation-v1/rules.py',BASE/'wikibooks-language-token-preparation-v1/profile.json',BASE/'tokenizer-8192/core.json',BASE/'tokenizer-8192/manifest.json',BASE/'tokenizer-receipt.json',BASE/'gutenberg-four-longWB-delta-preparation-v1/measurement.json',ROOT/'gutenberg-post1900-first-complete-units-v1/documents.json']
 import tokenizers,tokenizers.tokenizers
 p += [pathlib.Path(tokenizers.__file__),pathlib.Path(tokenizers.tokenizers.__file__),pathlib.Path(sys.executable).resolve()]
 for c in json.loads((HERE/'candidates.json').read_text()):p += [pathlib.Path(c['file']),pathlib.Path(c['captured_raw_source_ancestor']['path']),pathlib.Path(c['components_sidecar'])]
 p += [pathlib.Path(pyarrow.__file__),pathlib.Path(pyarrow._parquet.__file__),pathlib.Path(pyarrow.lib.__file__)]
 p += [M0/'artifacts'/n for n in ['admitted-documents.jsonl','historical-heldout.jsonl','protected-text-units.jsonl','m1-loss-assignments.jsonl','diagnostics.json']]
 p += [pathlib.Path(e['path']) for e in json.loads((HERE/'body-sources.json').read_text())]
 return {str(x.resolve()) for x in p}
def verify(code,profile):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=profile:raise ValueError('explicit_profile_pin')
 p=json.loads((HERE/'profile.json').read_text());c=json.loads((HERE/'candidates.json').read_text())
 if p['limits']!=LIMITS or [x['source_ordinal'] for x in c]!=[61485,40765,72377]:raise ValueError('exact_three_current_units_profile')
 current,_=sources.discover();frozen=json.loads((HERE/'body-sources.json').read_text())
 if current!=frozen:raise ValueError('retained_source_inventory_changed_no_silent_coverage_drift')
 for x in c:
  if sha(x['file'])!=x['text_SHA256'] or pathlib.Path(x['file']).stat().st_size!=x['bytes']:raise ValueError('candidate_current_text_hash')
 return c

def count_text(text,tok):
 encoding=tok.encode(text,add_special_tokens=False)
 if any(not 0<=i<8182 for i in encoding.ids):raise ValueError('M1_content_ID_convention')
 return len(encoding.ids)

def approved_large_WB(norm,metadata):
 observed=metadata.get('source_ordinal')
 records=json.loads((BASE/'gutenberg-four-longWB-delta-preparation-v1/measurement.json').read_text())['records']
 for r in records:
  if observed==r['source_ordinal'] and metadata.get('page_id')==r['source_outer_page_id'] and metadata.get('revision_id')==r['source_outer_revision_id'] and metadata.get('family_id',metadata.get('family'))==r['source_family']:
   return core.sha(norm.encode())==r['normalized_SHA256'] and len(norm.split())==r['normalized_words']<=240742
 return False

def own_ancestor(c,identity,metadata):
 path=identity.split('#',1)[0]
 if path in [c['file'],c['captured_raw_source_ancestor']['path']]:return True
 role=metadata.get('current_global_finalizer_role')
 return bool(role and metadata.get('source_ordinal')==c['source_ordinal'] and role['page_id']==c['page_id'] and role['revision_id']==c['revision_id'] and role['text_sha256']==c['captured_raw_source_ancestor']['SHA256'] and role['family']==c['family_ID'])

def guard(additional=0):
 if START is not None and clk()-START>=540:raise TimeoutError('worker540seconds')
 if size(OUT)+additional>32000000-1048576:raise ValueError('output_prewrite_32MB')
 if shutil.disk_usage(ROOT).free<FREE+additional:raise ValueError('protected_disk_reserve')
def write(name,data):
 b=data if isinstance(data,bytes) else (json.dumps(data,indent=2,ensure_ascii=False)+'\n').encode();guard(len(b))
 with (OUT/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def terminal(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('terminal_receipt_cap')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def emit(name,obj):
 b=(json.dumps(obj,ensure_ascii=False)+'\n').encode();guard(len(b))
 with (OUT/name).open('ab') as f:f.write(b);f.flush()

def progress(phase,stats,adapter=None):
 terminal('progress.json',{'phase':phase,'stats_so_far':dict(stats),'current_adapter':adapter,'elapsed_seconds':clk()-START,'partial_evidence_only':True})

def current_wikibooks_role(db,ordinal):
 row=db.execute('select p.page_id,p.revision_id,p.family,p.text_sha256,p.holds,p.active,f.holds from pages p join final_pages f on p.source_ordinal=f.source_ordinal where p.source_ordinal=?',(ordinal,)).fetchone()
 if row is None:return None
 page,revision,family,digest,prior,active,final=row
 return {'page_id':page,'revision_id':revision,'family':family,'text_sha256':digest,'prior_holds':json.loads(prior),'global_final_holds':json.loads(final),'active':active}

def worker(a):
 global START
 START=float(a.start);candidates=verify(a.code_pins_sha256,a.profile_sha256);stats=collections.Counter();coverage=[];familyholds=set();completed=False
 if os.getppid()!=a.supervisor_pid:raise ValueError('parent_identity')
 try:
  registry=json.loads((M0/'registry.json').read_text())
  for name,h in registry['files'].items():
   if sha(M0/'artifacts'/name)!=h:raise ValueError('M0_artifact_pin')
  if sha(LEGACY)!=registry['input_sha256']['restart/corpus-audit-v1/audit.sqlite']:raise ValueError('legacy_DB_M0_binding')
  roles={};family_splits={}
  with (M0/'artifacts/admitted-documents.jsonl').open() as f:
   for line in f:
    v=json.loads(line);ident=int(v['audit_id'])
    if ident in roles:raise ValueError('M0_duplicateID')
    roles[ident]={k:v[k] for k in ['family_id','split','normalized_sha256']};family_splits.setdefault(v['family_id'],set()).add(v['split'])
  if len(roles)!=80038 or any(len(x)!=1 for x in family_splits.values()) or sum(v['split'] in ['development','test'] for v in roles.values())!=7922:raise ValueError('M0_count_role_or_family_split')
  historical={}
  with (M0/'artifacts/historical-heldout.jsonl').open() as f:
   for line in f:
    v=json.loads(line);historical[int(v['audit_id'])]=v['normalized_sha256']
  if len(historical)!=252750:raise ValueError('historical_heldout_count')
  identities=json.loads((OLD/'protection-identities.json').read_text());lines=(OLD/'protections.tsv').read_text().splitlines();units=[json.loads(l) for l in (M0/'artifacts/protected-text-units.jsonl').read_text().splitlines()];protections=core.reconcile_protections(lines,identities,units)
  if len(protections)!=8841:raise ValueError('protected8841_reconciliation')
  if any(pid in range(1,5) for pid,identity,norm in protections):raise ValueError('C++candidate_protection_namespace_collision')
  for c in candidates:
   ancestor=c['captured_raw_source_ancestor'];raw=pathlib.Path(ancestor['path']).read_bytes();bounds=c['original_source_interval']
   if core.sha(raw)!=ancestor['SHA256'] or core.sha(raw[bounds['start']:bounds['end_exclusive']])!=c['text_SHA256']:raise ValueError('known_current_raw_ancestor_interval_binding')
  from importlib.util import spec_from_file_location,module_from_spec
  spec=spec_from_file_location('pinned_token_rules',BASE/'wikibooks-language-token-preparation-v1/rules.py');rules=module_from_spec(spec);spec.loader.exec_module(rules)
  tp=json.loads((BASE/'wikibooks-language-token-preparation-v1/profile.json').read_text());tok=rules.load_tokenizer(tp);counts=[]
  for c in candidates:
   text=pathlib.Path(c['file']).read_text();n=count_text(text,tok)
   counts.append({'source_ordinal':c['source_ordinal'],'text_SHA256':c['text_SHA256'],'content_tokens':n,'targets_plus_one_EOS':n+1,'provisional_not_admitted':True})
  write('candidate-token-counts.json',{'tokenizer_core_SHA256':rules.sha(tp['tokenizer_core']['path']),'per_candidate':counts,'sum_content_tokens':sum(c['content_tokens'] for c in counts),'no_fit_no_weights_no_admission':True})
  del tok
  index=core.Index([pathlib.Path(c['file']).read_text() for c in candidates]);progress('legacy_start',stats)
  internal=[]
  for i,norm in enumerate(index.norms):
   for j,match in index.compare(norm).items():
    if j<i:internal.append({'left':candidates[j]['source_ordinal'],'right':candidates[i]['source_ordinal'],'matches':match,'custody':'Crosscandidate family review required; no automatic independent split'})
  write('three-internal-overlap.json',internal)
  write('preflight.json',{'M0_admitted':80038,'legacy_expected':432499,'M0_devtest':7922,'upstream_historical':252750,'protected_units':8841,'candidate_text_hashes':{str(c['source_ordinal']):c['text_SHA256'] for c in candidates},'source_body_adapters':len(json.loads((HERE/'body-sources.json').read_text())),'existing_frozen_M1_recount_no_fitting':True})
  active_adapter=['legacy_database']
  def examine(text,identity,role,metadata,already_normalized=False,required=True):
   guard();stats['body_occurrences']+=1
   if stats['body_occurrences']>LIMITS['max_records']:raise ValueError('record_bound')
   if text is None or len(text.encode())>LIMITS['max_document_UTF8_bytes']:
    stats['body_coverage_holds' if required else 'optional_raw_context_limits']+=1;emit('coverage-holds.jsonl',{'identity':identity,'role':role,'required_current_candidate_or_protected_coverage':required,'reason':'missing_native_body_or_perdocument_byte_cap','metadata':metadata});return
   norm=text if already_normalized else core.normalized(text)
   if len(norm.split())>LIMITS['max_document_words'] and not approved_large_WB(norm,metadata):
    stats['body_coverage_holds' if required else 'optional_raw_context_limits']+=1;emit('coverage-holds.jsonl',{'identity':identity,'role':role,'required_current_candidate_or_protected_coverage':required,'reason':'document_word_cap','metadata':metadata});return
   digest=core.sha(norm.encode())
   if stats['body_occurrences']%10000==0:progress('body_stream_progress',stats,active_adapter[0])
   for i,match in index.compare(norm).items():
    c=candidates[i];protected=role in ['historical_heldout','current_development','current_test','explicit_protected'];kind=core.disposition(protected,own_ancestor(c,identity,metadata))
    if protected:familyholds.add(c['family_ID'])
    emit('body-matches.jsonl',{'candidate_source_ordinal':c['source_ordinal'],'candidate_current_SHA256':c['text_SHA256'],'candidate_family_ID':c['family_ID'],'source_identity':identity,'source_role':role,'source_metadata':metadata,'source_normalized_sha256':digest,'disposition':kind,'match':match});stats['matched_body_occurrences']+=1
   hay=json.dumps(metadata,ensure_ascii=False).casefold()
   for i,pattern in enumerate(PATTERNS):
    if pattern.search(hay):emit('metadata-aliases.jsonl',{'candidate_source_ordinal':candidates[i]['source_ordinal'],'source_identity':identity,'source_role':role,'metadata':metadata,'disposition':'LEXICAL_METADATA_LEAD_NOT_PROVEN_WORK_EQUIVALENCE_OR_ZERO_ANCESTRY'});stats['metadata_alias_leads']+=1
  db=sqlite3.connect(LEGACY.as_uri()+'?mode=ro',uri=True);db.execute('pragma cache_size=-4096');seen_roles=collections.Counter();historical_seen=0
  try:
   for ident,source,norm,held,families,reference in db.execute('select id,source,normalized,held,families,reference from docs'):
    r=roles.get(ident);role=core.legacy_role(bool(held),r['split'] if r else None)
    if r:
     if core.sha(norm.encode())!=r['normalized_sha256']:raise ValueError('admitted_normalized_hash_not_DB_text')
     seen_roles[role]+=1
    if held:
     if historical.get(ident)!=core.sha(norm.encode()):raise ValueError('historical_ID_hash_role_not_DB_text')
     historical_seen+=1
    examine(norm,'legacy:'+str(ident),role,{'source':source,'families':families,'reference':reference,'M0':r},True);stats['legacy_rows']+=1
  finally:db.close()
  if stats['legacy_rows']!=432499 or historical_seen!=252750 or dict(seen_roles)!={'current_train':72116,'current_development':3999,'current_test':3923}:raise ValueError('legacy_M0_currentrole_fullscan_reconciliation')
  del roles,historical,family_splits
  active_adapter[0]='explicit_protected_units';progress('legacy_complete_protected_start',stats)
  pyprotected=set()
  for pid,identity,norm in protections:
   guard()
   for i in index.containment(norm.split()):pyprotected.add(i+1)
   examine(norm,'protected:'+identity,'explicit_protected',{'identity':identity,'disjoint_CPP_ID':pid},True)
  write('protections-disjoint.tsv',''.join(str(pid)+'\t'+norm+'\n' for pid,identity,norm in protections).encode());write('normalized-candidates.txt',('\n'.join(index.norms)+'\n').encode());guard()
  subprocess.run([str(REPO/'restart/corpus-audit-v1/containment'),str(OUT/'protections-disjoint.tsv'),str(OUT/'normalized-candidates.txt'),str(OUT/'CPP-containment.tsv')],check=True,timeout=max(.01,540-(clk()-START)),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  cpp=[];protection_by_id={pid:norm for pid,identity,norm in protections}
  for line in (OUT/'CPP-containment.tsv').read_text().splitlines():
   ci,pid,text=line.split('\t',2)
   if not 1<=int(ci)<=3 or int(pid) not in protection_by_id or ' '+text+' ' not in ' '+index.norms[int(ci)-1]+' ' or ' '+text+' ' not in ' '+protection_by_id[int(pid)]+' ':raise ValueError('CPP_ID_or_containment_proof')
   cpp.append(int(ci))
  # C++ excludes <12word strings; equality for those remains Python-only.
  if set(cpp)!=pyprotected-{i+1 for i,n in enumerate(index.norms) if len(n.split())<12}:raise ValueError('CPP_independent_protected_hitset_disagreement')
  del protections,protection_by_id,identities,lines,units
  import gc;gc.collect()
  entries=json.loads((HERE/'body-sources.json').read_text());file_aliases={};required_paths={e['path'] for e in entries if e['required_current_candidate_body_coverage'] and e['adapter']=='native_or_plain_UTF8_file'}
  wbdb=sqlite3.connect((ROOT/'wikibooks-global-finalization-v3/finalized.sqlite3').as_uri()+'?mode=ro',uri=True)
  wbdb.execute('pragma query_only=ON');wbdb.execute('pragma cache_size=-2048');wb_seen=set()
  if wbdb.execute('select count(*) from pages p join final_pages f on p.source_ordinal=f.source_ordinal').fetchone()[0]!=89758:raise ValueError('current_Wikibooks_global_role_inventory89758')
  for e in entries:
   active_adapter[0]=e['path'];progress('retained_adapter_start',stats,e['path'])
   guard();signature=sources.alias_signature(e,sha(e['path']))
   if signature in file_aliases:
    coverage.append({'path':e['path'],'adapter':e['adapter'],'exact_file_alias_of':file_aliases[signature],'scope':'Same exact bytes/table/adapter; body pass inherited, occurrences not new independent supply'});continue
   file_aliases[signature]=e['path'];before=stats['body_occurrences'];rows=0
   for identity,text,metadata in sources.stream(e,guard,required_paths=required_paths):
    rows+=1
    if metadata.get('body_reference_alias'):
     stats['metadata_only_external_body_references_reconciled']+=1;continue
    if e['adapter']=='sqlite_json_data' and e.get('table')=='rendered' and any('/'+group+'/' in e['path'] for group in ['wikibooks-sharded-render-v2','wikibooks-residual-render-v1']):
     ordinal=int(metadata['source_ordinal']);current=current_wikibooks_role(wbdb,ordinal)
     if current is None or metadata['page_id']!=current['page_id'] or metadata['revision_id']!=current['revision_id'] or metadata['family']!=current['family'] or core.sha(text.encode())!=current['text_sha256']:raise ValueError('current_Wikibooks_body_hash_identity_family_finalizer_binding')
     wb_seen.add(ordinal);metadata['current_global_finalizer_role']=current
    examine(text,e['path']+'#'+identity,e['coverage_role'],metadata,required=e['required_current_candidate_body_coverage'])
   coverage.append({'path':e['path'],'adapter':e['adapter'],'table':e.get('table'),'required_current_candidate_body_coverage':e['required_current_candidate_body_coverage'],'body_records_observed':rows,'scope':'Literal retainedbody matching only; no semantic rendering or originalEnglish inference'})
  expected_wb={int(x[0]) for x in wbdb.execute('select p.source_ordinal from pages p join final_pages f on p.source_ordinal=f.source_ordinal')}
  wbdb.close()
  if wb_seen!=expected_wb:raise ValueError('current_Wikibooks_finalized_body_coverage_gap')
  del expected_wb;progress('all_retained_adapters_complete',stats)
  # Metadata family components are conservative custody components, not proven equivalence.
  family_members=[]
  frame=sqlite3.connect((ROOT/'wikibooks-global-finalization-v3/finalized.sqlite3').as_uri()+'?mode=ro',uri=True)
  for c in candidates:
   members=[dict(source_ordinal=x,page_id=y,revision_id=z,title=t) for x,y,z,t in frame.execute('select source_ordinal,page_id,revision_id,title from pages where family=? order by source_ordinal',(c['family_ID'],))]
   if not any(m['source_ordinal']==c['source_ordinal'] for m in members):raise ValueError('WB_conservative_family_self_missing')
   family_members.append({'candidate':c['source_ordinal'],'family_ID':c['family_ID'],'conservative_members':members,'not_proven_transclusion_or_external_import_resolution':True})
  frame.close();guard();verify(a.code_pins_sha256,a.profile_sha256)
  write('source-coverage.json',{'retained_body_sources':coverage,'metadata_only_or_unavailable':json.loads((HERE/'metadata-coverage.json').read_text()),'known_zero_not_claimed_for_unavailable_source_coverage':True,'current_Wikibooks_89758_finalized_body_identities_hashes_and_holds_reconciled':len(wb_seen),'raw_non_candidate_scope_exclusions_are_not_clearance_requirements':True})
  write('family-custody.json',{'candidate_components':family_members,'protected_hits_propagate_whole_components':sorted(familyholds),'assigned_splits':0,'unknown_upstream_ancestry_semantic_paraphrase_not_cleared':True})
  terminal('result.json',{'status':'COMPLETE_TARGETED_SCREEN_NOT_ADMISSION_OR_UNKNOWN_ANCESTRY_CLEARANCE','stats':dict(stats),'M0_roles':dict(seen_roles),'protected_units':8841,'historical_heldout':historical_seen,'protected_component_holds':sorted(familyholds),'distinct_normalized_body_hashes':None,'normalized_alias_count':None,'non_disposition_counts_omitted_for_memory_bound':'No global seen-digest set; every source occurrence still compared; no dedup skipping or new unique-supply claim','CPP_Python_protected_agreement':True,'elapsed_seconds':clk()-START,'all_inputs_rechecked':True,'coverage_holds_must_be_reviewed':stats['body_coverage_holds'],'new_admitted_documents':0,'new_admitted_tokens':0});completed=True
 except BaseException as e:
  terminal('result.json',{'status':'TERMINAL_PARTIAL_CUSTODY_SCREEN_NO_RETRY_NO_ZERO_CLAIM','error':type(e).__name__+':'+str(e)[:1800],'stats':dict(stats),'new_admitted_documents':0,'new_admitted_tokens':0});raise
PATTERNS=[] # No narrative-author lexical shortcuts for these WB families.

def strict_tree_rss(pid):
 v=subprocess.run(['ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=2).stdout
 rows={}
 for line in v.splitlines():
  f=line.split()
  if len(f)!=3:raise ValueError('RSS_malformed')
  i,parent,rss=map(int,f)
  if i in rows or i<=0 or parent<0 or rss<0 or i==parent:raise ValueError('RSS_invalid')
  rows[i]=(parent,rss)
 if pid not in rows or rows[pid][1]<=0:raise ValueError('RSS_root_missing')
 found={pid}
 while True:
  more={i for i,(parent,rss) in rows.items() if parent in found}
  if more<=found:break
  found|=more
 return sum(rows[i][1]*1024 for i in found)

def kill(child):
 if child.poll() is None:
  try:os.killpg(child.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 child.wait(timeout=3)
def supervise(a):
 global START
 START=clk();child=None;created=False;peak=0;reason=None
 def stop(signum,frame):
  if child is not None:kill(child)
  raise TimeoutError('armed_preflight_deadline_or_termination_signal_'+str(signum))
 old={sig:signal.signal(sig,stop) for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]}
 signal.setitimer(signal.ITIMER_REAL,570)
 try:
  # The real external timer and termination handlers precede every pin,
  # discovery/schema and disk preflight, not only the subprocess wait.
  verify(a.code_pins_sha256,a.profile_sha256)
  if OUT.exists() or OUT.is_symlink():raise ValueError('existing_output_no_rerun')
  if shutil.disk_usage(ROOT).free<FREE+32000000:raise ValueError('weights_scratch_free_floor')
  OUT.mkdir();created=True
  for name,n in SLOTS.items():(OUT/name).write_bytes(b' '*n)
  with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen([sys.executable,str(HERE/'audit.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(START),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  write('ownership.json',{'supervisor_PID':os.getpid(),'worker_PID':child.pid,'shared_start':START,'code_pins_SHA256':a.code_pins_sha256,'profile_SHA256':a.profile_sha256})
  while child.poll() is None:
   if clk()-START>=540:reason='worker540seconds';break
   peak=max(peak,strict_tree_rss(os.getpid()))
   if peak>1000000000:reason='process_tree_RSS1GB';break
   if size(OUT)>32000000 or shutil.disk_usage(ROOT).free<FREE:reason='output_or_diskcap';break
   time.sleep(.5)
  if reason:kill(child)
  else:child.wait(timeout=3)
  text=(OUT/'result.json').read_text();result=json.loads(text) if text.strip() else {};okay=child.returncode==0 and reason is None and result.get('status')=='COMPLETE_TARGETED_SCREEN_NOT_ADMISSION_OR_UNKNOWN_ANCESTRY_CLEARANCE' and clk()-START<570
  terminal('supervisor.json',{'status':'COMPLETE_TARGETED_CUSTODY_SCREEN_NO_ADMISSION' if okay else 'PARTIAL_SCREEN_NO_RETRY_NO_ZERO_CLAIM','worker_exit_code':child.returncode,'reason':reason,'elapsed_seconds':clk()-START,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':size(OUT),'result_SHA256':sha(OUT/'result.json'),'new_admitted_documents':0,'new_admitted_tokens':0});return 0 if okay else 1
 except BaseException as e:
  if child is not None:kill(child)
  if created:
   receipt={'status':'PARTIAL_SCREEN_NO_RETRY_NO_ZERO_CLAIM','error':type(e).__name__+':'+str(e)[:1200],'new_admitted_documents':0,'new_admitted_tokens':0}
   if (OUT/'supervisor.json').exists():terminal('supervisor.json',receipt)
   else:write('supervisor.json',receipt)
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  for sig,handler in old.items():signal.signal(sig,handler)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--supervisor-pid',type=int);p.add_argument('--start');p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);a=p.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:
  signal.signal(signal.SIGALRM,lambda s,f:(_ for _ in ()).throw(TimeoutError('preflight540seconds')));signal.setitimer(signal.ITIMER_REAL,540)
  try:verify(a.code_pins_sha256,a.profile_sha256);print('READY_NO_SCAN_NO_COUNTS')
  finally:signal.setitimer(signal.ITIMER_REAL,0)
