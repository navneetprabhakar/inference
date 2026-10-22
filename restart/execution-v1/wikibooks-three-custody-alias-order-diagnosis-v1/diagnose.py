from pathlib import Path
import json,sqlite3,hashlib
P=Path(__file__).resolve().parent;B=P.parent;F=B/'wikibooks-three-renewed-custody-preparation-v1';T=B/'m2-intake/wikibooks-three-renewed-custody-v1';H=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
entries=json.loads((F/'body-sources.json').read_text());pins=json.loads((F/'code-pins.json').read_text())['input_SHA256'];groups={}
for n,e in enumerate(entries):
 signature=(pins[e['path']],e['adapter'],e.get('table'),e['required_current_candidate_body_coverage']);groups.setdefault(signature,[]).append((n,e))
def wbpath(p):return any('/'+g+'/' in p for g in ['wikibooks-sharded-render-v2','wikibooks-residual-render-v1'])
def metadata(p):
 d=sqlite3.connect(Path(p).as_uri()+'?mode=ro',uri=True)
 try:return set(d.execute('select source_ordinal,page_id,revision_id,family from rendered'))
 finally:d.close()
skipped=[];actually_bound=set();all_original=set();samples=[]
for signature,rows in groups.items():
 originals=[(n,e) for n,e in rows if wbpath(e['path']) and e['adapter']=='sqlite_json_data' and e.get('table')=='rendered']
 if not originals:continue
 owner_n,owner=rows[0];owner_rows=metadata(owner['path']);all_original|=owner_rows
 if wbpath(owner['path']):actually_bound|=owner_rows
 else:
  for n,e in originals:assert metadata(e['path'])==owner_rows
  skipped.append({'signature':list(signature),'earliest_owner_entry_index0':owner_n,'earliest_owner':owner['path'],'earliest_owner_role':owner['coverage_role'],'skipped_originals':[{'entry_index0':n,'path':e['path'],'coverage_role':e['coverage_role']} for n,e in originals],'metadata_rows':len(owner_rows),'ordinal_range':[min(r[0] for r in owner_rows),max(r[0] for r in owner_rows)],'exact_SQL_metadata_equality':True})
  samples.extend(sorted(owner_rows)[:2])
d=sqlite3.connect((B/'m2-intake/wikibooks-global-finalization-v3/finalized.sqlite3').as_uri()+'?mode=ro',uri=True)
expected=set(d.execute('select p.source_ordinal,p.page_id,p.revision_id,p.family from pages p join final_pages f on p.source_ordinal=f.source_ordinal'));d.close();assert all_original==expected
missing=expected-actually_bound;assert len(missing)==sum(x['metadata_rows'] for x in skipped)
# Production order/signature/continue path isolated with rows standing for bound bodies.
fixture=[{'path':'/x/wikibooks-sharded-render-v2-verification-v1/shard-1/recovered.sqlite3','sig':'same','rows':[(1,10,100,'family')]},{'path':'/x/wikibooks-sharded-render-v2/shard-1/rendered.sqlite3','sig':'same','rows':[(1,10,100,'family')]}]
seen=set();compared=[];bound=[]
for e in sorted(fixture,key=lambda e:e['path']):
 if e['sig'] in seen:continue
 seen.add(e['sig'])
 for row in e['rows']:
  if wbpath(e['path']):bound.append(row)
  compared.append(row)
assert compared==fixture[0]['rows'] and bound==[]
x={'status':'CONFIRMED_PRODUCTION_ALIAS_ORDER_PROVENANCE_GAP_NO_MATCHING_RERUN','inputs':{str(p):H(p) for p in [F/'audit.py',F/'sources.py',F/'body-sources.json',F/'code-pins.json',T/'result.json',T/'supervisor.json']},'actual_terminal':json.loads((T/'result.json').read_text()),'frozen_adapter_entries':len(entries),'skipped_alias_groups':skipped,'metadata_only_SQL_observations':{'original_and_alias_rows_equal_without_reading_data_body':True,'complete_original_source_union_matches_finalizer_metadata':True,'expected_finalized_rows':len(expected),'controlflow_inferred_bound_residual_rows':len(actually_bound),'controlflow_inferred_missing_initial_rows':len(missing),'missing_ordinal_sample':[list(x) for x in sorted(missing)[:8]],'no_actual_runtime_wb_seen_capture_claim':True},'minimal_synthetic_production_order':{'fixture':fixture,'compared_rows':compared,'reconciled_rows':bound,'assertion_passed':True},'root_cause':'Full string lexicographic sorting places verification-v1 recovered path before original directory slash. Same SHA/table/adapter/required-body signature suppresses original. WB row reconciliation tests only original path prefixes, so equivalent copy body was compared without current identity/hash/family/final-hold reconciliation. It is not a harmless missing counter.','required_repair':['Bind WB adapter provenance to exact reviewed original DB digest/table/columns and byte-identical alias owner, not directory sorting','On every streamed WB-role row require exact ordinal/page/revision/family plus SHA256(text) and current finalizer holds/active binding before match dispositions or coverage credit','If comparison inherited by whole-file alias, inherit only from a proven validated role-compatible row ledger with exact ordinal-set coverage; otherwise perform bounded row reconciliation without pretending unvalidated aliases are covered','Preserve all final/prior holds and protected role priority; reconcile89758 exact identities and no missing/duplicate ambiguity; include recovered-copy-before-original synthetic lifecycle fixture','Keep terminal partial and all prior artifacts; new reviewed version/dispatch required, no matching rerun here'],'scan_and_admission_effect':{'retained_matching_reruns':0,'tokens_recomputed':0,'new_admitted_documents':0,'actual_scan_complete_claim':False},'audit_gap_acknowledgement':'Prior47 controls tested per-row role lookup and aliases independently but missed actual sorted adapter order interacting with whole-file alias skip and path-scoped provenance reconciliation.'}
(P/'diagnosis.json').write_text(json.dumps(x,indent=2)+'\n');(P/'manifest.json').write_text(json.dumps({'files':{p.name:H(p) for p in P.iterdir() if p.is_file() and p.name!='manifest.json'}},indent=2)+'\n');print(json.dumps(x['metadata_only_SQL_observations']));print('diagnosis',H(P/'diagnosis.json'));print('manifest',H(P/'manifest.json'))
