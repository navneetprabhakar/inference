"""Separate original-three literal-pass + fresh role-only closure, never rerun success."""
import argparse,ast,collections,hashlib,importlib.util,json,os,pathlib,platform,signal,sqlite3,sys,time
import supervisor_core as supervisor
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;ROOT=BASE/'m2-intake'
OLD=BASE/'wikibooks-three-renewed-custody-preparation-v1';PART=ROOT/'wikibooks-three-renewed-custody-v1'
HELPER=BASE/'wikibooks-semantic-provenance-preparation-v1';FINAL=ROOT/'wikibooks-global-finalization-v3/finalized.sqlite3'
LIMITS={'worker_seconds':110,'external_seconds':120,'output_bytes':32000000,'tree_RSS_bytes':1000000000,'role_only_rows':50457,'expected_WB_rows':89758,'previous_rolebound_rows':39301,'source_adapters':837,'original_pins':889,'preserved_matches':10,'max_JSON_carrier_bytes':16000000,'max_text_bytes':8000000}
IDS=[61485,40765,72377]
ERROR='current_Wikibooks_finalized_body_coverage_gap'
ORIGINAL_CODEPINS_SHA256='531ce2ed8a88fd2f739f81b2ef771e0aaa13b07df4f98d558dbb8884028f0e56'
PART_FILES={'ownership.json','protections-disjoint.tsv','result.json','supervisor.json','three-internal-overlap.json','worker.log','coverage-holds.jsonl','candidate-token-counts.json','CPP-containment.tsv','normalized-candidates.txt','progress.json','body-matches.jsonl','preflight.json'}
def sha(p):
 h=hashlib.sha256()
 with pathlib.Path(p).open('rb') as f:
  for b in iter(lambda:f.read(65536),b''):h.update(b)
 return h.hexdigest()
def load(name,p):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def runtime():return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'sqlite':sqlite3.sqlite_version,'platform':platform.platform()}
def additional_inventory():
 paths={HERE/n for n in ['closure.py','supervisor_core.py','checks.py','profile.json','runtime.json']}
 paths|={PART/n for n in PART_FILES}
 paths|={OLD/'code-pins.json',HELPER/'semantic_provenance.py',HELPER/'canonical-stores.json',HELPER/'body-sources-semantic.json',HELPER/'checks.py',BASE/'wikibooks-three-custody-alias-diagnosis-v1/diagnosis.json',pathlib.Path(sys.executable).resolve()}
 import _sqlite3,_hashlib
 for mod in [argparse,ast,collections,hashlib,importlib.util,json,os,pathlib,platform,signal,sqlite3,_sqlite3,_hashlib,supervisor.shutil,supervisor.subprocess]:
  if getattr(mod,'__file__',None):paths.add(pathlib.Path(mod.__file__).resolve())
 return {str(p.resolve()) for p in paths}
def ro(p):
 db=sqlite3.connect(pathlib.Path(p).as_uri()+'?mode=ro',uri=True);db.execute('pragma query_only=ON');db.execute('pragma cache_size=-2048');return db
def postloop_proof(source,log):
 tree=ast.parse(source)
 raises=[n for n in ast.walk(tree) if isinstance(n,ast.Raise) and isinstance(n.exc,ast.Call) and n.exc.args and isinstance(n.exc.args[0],ast.Constant) and n.exc.args[0].value==ERROR]
 loops=[n for n in ast.walk(tree) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=='e' and isinstance(n.iter,ast.Name) and n.iter.id=='entries']
 if len(raises)!=1 or len(loops)!=1 or raises[0].lineno<=loops[0].end_lineno:raise ValueError('not_unique_post_all_adapter_loop_failure')
 # Both statements must occur in one sequential body, not separate branches.
 pairs=[]
 for node in ast.walk(tree):
  for field in ['body','orelse','finalbody']:
   values=getattr(node,field,None)
   if isinstance(values,list) and loops[0] in values:
    for n in values:
     if isinstance(n,ast.If) and raises[0] in list(ast.walk(n)) and values.index(n)>values.index(loops[0]):pairs.append((values.index(loops[0]),values.index(n)))
 if len(pairs)!=1 or ERROR not in log or f'line {raises[0].lineno}, in worker' not in log:raise ValueError('traceback_or_sequential_loop_scope_unproven')
 return {'adapter_loop_lines':[loops[0].lineno,loops[0].end_lineno],'unique_postloop_raise_line':raises[0].lineno,'traceback_bound':True}
def old_role_alias_proof(entries,file_pins):
 groups={}
 for e in entries:
  required=e['required_current_candidate_body_coverage'];role=e['coverage_role']
  if type(required)is not bool or role!=('CURRENT_OR_RETAINED_CANDIDATE_BODY' if required else 'OPTIONAL_RAW_ANCESTOR_OR_NATIVE_CONTEXT_NOT_NEW_CLEARANCE_REQUIREMENT'):raise ValueError('old_adapter_role_not_derived_from_required_or_protected_conflict')
  key=(file_pins[e['path']],e['adapter'],e.get('table'),required);groups.setdefault(key,[]).append(e)
 for entries_in_group in groups.values():
  if len({e['coverage_role'] for e in entries_in_group})!=1:raise ValueError('old_alias_crosses_body_roles')
 return {'adapters':len(entries),'unique_old_alias_groups':len(groups),'old_signature_omits_coverage_role_but_required_determines_it_in_THIS_frozen_frame':True,'protected_development_test_roles_not_adapter_frame_roles':True}
def verify(args):
 if sha(HERE/'code-pins.json')!=args.code_pins_sha256 or sha(HERE/'profile.json')!=args.profile_sha256:raise ValueError('external_registry_profile_digest')
 p=json.loads((HERE/'profile.json').read_text());pins=json.loads((HERE/'code-pins.json').read_text())
 if p['limits']!=LIMITS or json.loads((HERE/'runtime.json').read_text())!=runtime():raise ValueError('limits_runtime')
 if sha(OLD/'code-pins.json')!=ORIGINAL_CODEPINS_SHA256 or set(p['additional_input_paths'])!=additional_inventory() or {q.name for q in PART.iterdir()}!=PART_FILES:raise ValueError('exact_original_manifest_additional_inventory_and_partial_output_frame')
 expected=set(json.loads((OLD/'code-pins.json').read_text())['input_SHA256'])|additional_inventory()
 if set(pins['SHA256'])!=expected or len(json.loads((OLD/'code-pins.json').read_text())['input_SHA256'])!=889:raise ValueError('exact_889_plus_delta_inventory')
 for path,digest in pins['SHA256'].items():
  q=pathlib.Path(path)
  if q.is_symlink() or not q.is_file() or sha(q)!=digest:raise ValueError('frozen_input_changed:'+path)
 for path,digest in json.loads((OLD/'code-pins.json').read_text())['input_SHA256'].items():
  if pins['SHA256'].get(path)!=digest:raise ValueError('original_889_manifest_not_inherited_exactly')
 return p
def source_metadata(ordinal,page,revision,family,obj):
 if obj.get('canonical_source_ordinal')!=ordinal or obj.get('page_id')!=page or obj.get('revision_id')!=revision:raise ValueError('inner_outer_source_identity')
 return {'source_ordinal':ordinal,'page_id':page,'revision_id':revision,'family':family,'family_id':obj.get('family_id'),'extracted_text_sha256':obj.get('extracted_text_sha256')}
def role_delta(role_entries,groups,semantic,finalizer):
 proofs=[];fresh=set();all_meta=set();old_valid=set()
 owner_paths={g['earlier_alias_owner'] for g in groups}
 if len(owner_paths)!=4:raise ValueError('exact_four_missing_owner_stores')
 for e in role_entries:
  if e['semantic_coverage_role']!=semantic.WB:continue
  if e['path'] not in owner_paths and '/wikibooks-residual-render-v1/' not in e['path']:continue
  db=ro(e['path']);expected={int(r[0]) for r in db.execute('select source_ordinal from rendered')}
  if all_meta&expected:raise ValueError('canonical_store_ordinal_overlap')
  all_meta|=expected
  if e['path'] not in owner_paths:
   old_valid|=expected;db.close();continue
  proof=semantic.WBRoleProof(e,sorted(expected))
  for ordinal,page,revision,family,length in db.execute('select source_ordinal,page_id,revision_id,family,length(cast(data as blob)) from rendered order by source_ordinal'):
   if length>16000000:raise ValueError('role_JSON_carrier_bound')
   obj=json.loads(db.execute('select data from rendered where source_ordinal=?',(ordinal,)).fetchone()[0]);text=obj.get('text')
   if not isinstance(text,str) or len(text.encode())>8000000:raise ValueError('role_body_bound_or_missing')
   proof.observe(source_metadata(ordinal,page,revision,family,obj),text,finalizer)
   fresh.add(ordinal)
  receipt=proof.finish();db.close()
  if receipt['complete_body_comparison']:raise ValueError('role_only_delta_cannot_claim_fresh_body_comparison')
  proofs.append(receipt)
 if len(fresh)!=50457 or len(old_valid)!=39301 or len(all_meta)!=89758 or fresh&old_valid:raise ValueError('50457_plus39301_coverage_reconciliation')
 actual={r[0] for r in finalizer.execute('select source_ordinal from pages p join final_pages f using(source_ordinal)')}
 if all_meta!=actual:raise ValueError('canonical_metadata_union_not_full_current_finalizer')
 return {'fresh_role_only_rows':len(fresh),'previous_residual_rows_rolebound_in_preserved_producer':len(old_valid),'canonical_union_rows':len(all_meta),'fresh_ordinal_set_SHA256':semantic.sha_obj(sorted(fresh)),'residual_ordinal_set_SHA256':semantic.sha_obj(sorted(old_valid)),'union_ordinal_set_SHA256':semantic.sha_obj(sorted(all_meta)),'role_only_owner_proofs':proofs,'fresh_matcher_pass_claimed':False}
def match_reproof(candidates,records,core,finalizer,role_entries):
 index=core.Index([pathlib.Path(c['file']).read_text() for c in candidates]);by_id={c['source_ordinal']:(n,c) for n,c in enumerate(candidates)};qualified={e['path']:e for e in role_entries if e['semantic_coverage_role']=='CURRENT_WIKIBOOKS_FINALIZED_RENDERED'};out=[]
 for old in records:
  i,c=by_id[old['candidate_source_ordinal']];identity=old['source_identity'];path=identity.split('#',1)[0];metadata=old['source_metadata'];current=None
  if path in qualified:
   ordinal=metadata['source_ordinal'];db=ro(path);row=db.execute('select source_ordinal,page_id,revision_id,family,data from rendered where source_ordinal=?',(ordinal,)).fetchone();db.close()
   if row is None:raise ValueError('saved_match_source_missing')
   ordinal,page,rev,family,payload=row;obj=json.loads(payload);text=obj['text'];r=finalizer.execute('select page_id,revision_id,family,text_sha256,holds,active,title from pages where source_ordinal=?',(ordinal,)).fetchone();f=finalizer.execute('select holds from final_pages where source_ordinal=?',(ordinal,)).fetchone()
   source_metadata(ordinal,page,rev,family,obj)
   if r is None or f is None or (page,rev,family)!=(r[0],r[1],r[2]) or hashlib.sha256(text.encode()).hexdigest()!=r[3] or obj.get('title')!=r[6] or obj.get('family_id')!=r[2] or obj.get('extracted_text_sha256')!=r[3]:raise ValueError('saved_WBmatch_identity_hash_title')
   current={'source_ordinal':ordinal,'page_id':r[0],'revision_id':r[1],'family':r[2],'text_sha256':r[3],'prior_holds':json.loads(r[4]),'active':r[5],'global_final_holds':json.loads(f[0]),'title':r[6],'native_url':obj.get('url')}
  elif path in [c['file'],c['captured_raw_source_ancestor']['path']]:text=pathlib.Path(path).read_text()
  else:raise ValueError('saved_match_unexpected_source_requires_review_not_auto_closure')
  norm=core.normalized(text);actual=index.compare(norm).get(i)
  if core.sha(norm.encode())!=old['source_normalized_sha256'] or actual!=old['match'] or old['candidate_current_SHA256']!=c['text_SHA256']:raise ValueError('saved_literal_match_not_exactly_reproduced')
  protected=old['source_role'] in ['historical_heldout','current_development','current_test','explicit_protected']
  own=path in [c['file'],c['captured_raw_source_ancestor']['path']] or bool(current and current['source_ordinal']==c['source_ordinal'] and current['page_id']==c['page_id'] and current['revision_id']==c['revision_id'] and current['family']==c['family_ID'] and current['text_sha256']==c['captured_raw_source_ancestor']['SHA256'])
  samefamily=bool(current and current['family']==c['family_ID'] and not own)
  out.append({'candidate_source_ordinal':c['source_ordinal'],'source_identity':identity,'original_source_role':old['source_role'],'original_disposition_preserved':old['disposition'],'new_source_role_bound_disposition':core.disposition(protected,own),'same_conservative_family_body_match_pending_parent_adjudication':samefamily,'currently_held_print_or_aggregate_source':bool(current and 'print_or_aggregate_page' in current['prior_holds']+current['global_final_holds']),'new_role':current,'saved_match_reproduced':True,'protected_priority_preserved':True})
 return out
def worker(args):
 supervisor.arm(110-(time.clock_gettime(time.CLOCK_MONOTONIC)-args.start));out=pathlib.Path(args.output)
 try:
  p=verify(args)
  if str(out)!=p['output'] or os.getppid()!=args.supervisor_pid:raise ValueError('owned_output_parent')
  semantic=load('closure_semantic',HELPER/'semantic_provenance.py');core=load('closure_frozen_matcher',OLD/'overlap_core.py');sources=load('closure_frozen_sources',OLD/'sources.py')
  entries=json.loads((OLD/'body-sources.json').read_text());current,_=sources.discover()
  if current!=entries or len(entries)!=837:raise ValueError('current_body_scope_not_exact_frozen837')
  original_pins=json.loads((OLD/'code-pins.json').read_text())['input_SHA256'];old_alias=old_role_alias_proof(entries,original_pins)
  result=json.loads((PART/'result.json').read_text());sup=json.loads((PART/'supervisor.json').read_text());own=json.loads((PART/'ownership.json').read_text())
  if result['status']!='TERMINAL_PARTIAL_CUSTODY_SCREEN_NO_RETRY_NO_ZERO_CLAIM' or result['error']!='ValueError:'+ERROR or result['stats']['body_occurrences']!=915133 or result['stats']['legacy_rows']!=432499 or result['stats']['matched_body_occurrences']!=10 or result['stats'].get('body_coverage_holds',0)!=0 or result['stats'].get('optional_raw_context_limits')!=1 or result['stats'].get('metadata_only_external_body_references_reconciled')!=122 or sup['worker_exit_code']!=1 or sup['result_SHA256']!=sha(PART/'result.json'):raise ValueError('preserved_partial_run_scope_or_terminal_not_exact')
  for key in ['supervisor_PID','worker_PID']:
   ps=supervisor.subprocess.run(['ps','-p',str(own[key]),'-o','pid='],capture_output=True,text=True)
   if ps.returncode!=1 or ps.stdout.strip():raise ValueError('original_process_not_proven_absent')
  control=postloop_proof((OLD/'audit.py').read_text(),(PART/'worker.log').read_text())
  producer_source=(OLD/'audit.py').read_text();prelude={}
  for label in ['protected8841_reconciliation','legacy_M0_currentrole_fullscan_reconciliation','CPP_independent_protected_hitset_disagreement']:
   if producer_source.count(label)!=1:raise ValueError('unique_prelude_guard_not_bound')
   line=producer_source[:producer_source.index(label)].count('\n')+1
   if line>=control['adapter_loop_lines'][0]:raise ValueError('protected_M0_prelude_not_before_complete_adapter_pass')
   prelude[label]=line
  control['passed_sequential_protected_M0_CPP_prelude_guard_lines']=prelude
  holds=[json.loads(l) for l in (PART/'coverage-holds.jsonl').read_text().splitlines()]
  if len(holds)!=1 or holds[0]['required_current_candidate_or_protected_coverage']is not False or holds[0]['reason']!='document_word_cap':raise ValueError('original_required_or_optional_coverage_holds_not_exact')
  if (PART/'CPP-containment.tsv').read_bytes()!=b'':raise ValueError('unexpected_protected_CPP_hits')
  pre=json.loads((PART/'preflight.json').read_text())
  if {k:pre[k] for k in ['M0_admitted','legacy_expected','M0_devtest','upstream_historical','protected_units','source_body_adapters']}!={'M0_admitted':80038,'legacy_expected':432499,'M0_devtest':7922,'upstream_historical':252750,'protected_units':8841,'source_body_adapters':837}:raise ValueError('original_registry_counts')
  role_entries=semantic.annotate(entries,json.loads((HELPER/'canonical-stores.json').read_text()),original_pins)
  if role_entries!=json.loads((HELPER/'body-sources-semantic.json').read_text()):raise ValueError('frozen_semantic_role_frame')
  diagnosis=json.loads((BASE/'wikibooks-three-custody-alias-diagnosis-v1/diagnosis.json').read_text());db=ro(FINAL)
  roleproof=role_delta(role_entries,diagnosis['alias_skip_cases'],semantic,db)
  candidates=json.loads((OLD/'candidates.json').read_text());matches=[json.loads(l) for l in (PART/'body-matches.jsonl').read_text().splitlines()]
  if [c['source_ordinal'] for c in candidates]!=IDS or len(matches)!=10:raise ValueError('three_and10_exact')
  counts=json.loads((PART/'candidate-token-counts.json').read_text())
  if counts['sum_content_tokens']!=974 or [(r['source_ordinal'],r['content_tokens'],r['text_SHA256']) for r in counts['per_candidate']]!=[(c['source_ordinal'],n,c['text_SHA256']) for c,n in zip(candidates,[95,216,663])]:raise ValueError('preserved_token_receipt_not_exact')
  for c in candidates:
   raw=pathlib.Path(c['captured_raw_source_ancestor']['path']).read_bytes();interval=c['original_source_interval'];a,b=interval['start'],interval['end_exclusive']
   if hashlib.sha256(raw).hexdigest()!=c['captured_raw_source_ancestor']['SHA256'] or hashlib.sha256(raw[a:b]).hexdigest()!=c['text_SHA256'] or pathlib.Path(c['file']).read_bytes()!=raw[a:b]:raise ValueError('candidate_exact_parent_interval_changed')
  renewed=match_reproof(candidates,matches,core,db,role_entries)
  family_rows=[]
  for c in candidates:
   rows=[{'source_ordinal':r[0],'page_id':r[1],'revision_id':r[2],'title':r[3],'text_SHA256':r[4],'active':r[5],'prior_holds':json.loads(r[6]),'final_holds':json.loads(r[7])} for r in db.execute('select p.source_ordinal,p.page_id,p.revision_id,p.title,p.text_sha256,p.active,p.holds,f.holds from pages p join final_pages f using(source_ordinal) where p.family=? order by p.source_ordinal',(c['family_ID'],))]
   if not any(r['source_ordinal']==c['source_ordinal'] for r in rows):raise ValueError('family_self_missing')
   family_rows.append({'candidate_source_ordinal':c['source_ordinal'],'conservative_family_ID':c['family_ID'],'all_current_metadata_members':rows,'unresolved_import_transclusion_component_rights_holds_preserved':True,'split_assigned':False})
  db.close();verify(args)
  supervisor.write(out,'role-only-proofs.json',supervisor.data(roleproof));supervisor.write(out,'match-reconciliation.json',supervisor.data(renewed));supervisor.write(out,'family-custody.json',supervisor.data(family_rows));supervisor.write(out,'preserved-producer-coverage-proof.json',supervisor.data({'postloop_control':control,'old_alias_role_scope':old_alias,'legacy_M0_protected_prelude_counts':pre,'original_optional_coverage_hold':holds,'literal_body_occurrences_in_preserved_producer':915133,'all889pins_rechecked_before_after':True,'no_fresh_915133body_rematch':True,'only10saved_match_occurrences_reproved':True}))
  protected=[r for r in renewed if r['new_source_role_bound_disposition']=='PROTECTED_FAMILY_HOLD'];unresolved=[r for r in renewed if r['new_source_role_bound_disposition']=='BODY_MATCH_REQUIRES_CUSTODY_REVIEW']
  supervisor.slot(out,'result.json',{'status':'COMPLETE_SEPARATE_COMPOSED_LITERAL_COVERAGE_ROLE_DELTA_NOT_PRODUCER_RERUN_OR_ADMISSION','original_producer_status_preserved':result['status'],'original_producer_result_SHA256':sha(PART/'result.json'),'fresh_role_only_rows':50457,'preserved_residual_rolebound_rows':39301,'combined_role_identity_union':89758,'saved_literal_matches_reproved':10,'protected_match_holds':len(protected),'unresolved_match_custody_holds':len(unresolved),'families_reserved':3,'provisional_M1_tokens_from_unchanged_original_receipt':974,'scope':'Composition of pinned failed producer completed literal loops plus new role-only closure and10match proofs. No fresh915133body pass, no semantic/paraphrase/unknown-ancestry/rights clearance.','output_SHA256':{q.name:sha(q) for q in out.iterdir() if q.is_file() and q.name not in ['result.json','supervisor.json','worker.log','ownership.json']},'all_original_input_and_failed_output_pins_unchanged':True,'new_admitted_documents':0,'new_admitted_tokens':0})
 except BaseException as e:
  supervisor.slot(out,'result.json',{'status':'PARTIAL_COMPOSED_CLOSURE_NO_RETRY_NO_CLEARANCE','error':type(e).__name__+':'+str(e),'original_producer_unchanged':True,'new_admitted_documents':0});raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);p.add_argument('--start',type=float);p.add_argument('--supervisor-pid',type=int);p.add_argument('--output');a=p.parse_args()
 if a.worker:worker(a)
 elif a.execute:
  start=time.clock_gettime(time.CLOCK_MONOTONIC);supervisor.arm(120);out=pathlib.Path(json.loads((HERE/'profile.json').read_text())['output'])
  supervisor.supervise(out,lambda start:[sys.executable,'-B',str(HERE/'closure.py'),'--worker','--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256,'--start',str(start),'--supervisor-pid',str(os.getpid()),'--output',str(out)],lambda:verify(a),started=start)
 else:
  supervisor.arm(110)
  try:verify(a);print('READY_NO_ROLE_DELTA_OR_MATCH_REPROOF')
  finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':main()
