"""Independent saved coverage/identity/match proof, never reruns corpus matching."""
import pathlib,json,hashlib,sqlite3,os,sys,collections,time,signal
BASE=pathlib.Path(__file__).resolve().parents[1];P=BASE/'gutenberg-language17-custody-preparation-v1';O=BASE/'m2-intake/gutenberg-language17-current-custody-v1'
def sha(p):
 with pathlib.Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def objsha(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_text())
def main():
 signal.signal(signal.SIGALRM,lambda *a:(_ for _ in ()).throw(TimeoutError('120sec verifier')));signal.alarm(120);start=time.monotonic()
 dest=BASE/'m2-intake/gutenberg-language17-independent-terminal-verification-v1';assert not dest.exists()
 pins=read(P/'code-pins.json')['input_SHA256'];assert len(pins)==915 and sha(P/'code-pins.json')=='af90bd72653ad24caf3c00d931d0879d3751efa51712f59d9d68b4b518c5f82c'
 for p,h in pins.items():assert sha(p)==h,p
 r=read(O/'result.json');s=read(O/'supervisor.json');own=read(O/'ownership.json');assert r['status']=='COMPLETE_TARGETED_SCREEN_NOT_ADMISSION_OR_UNKNOWN_ANCESTRY_CLEARANCE' and s['status']=='COMPLETE_TARGETED_CUSTODY_SCREEN_NO_ADMISSION' and s['worker_exit_code']==0 and s['result_SHA256']==sha(O/'result.json')
 for k in ['supervisor_PID','worker_PID']:
  try:os.kill(own[k],0)
  except ProcessLookupError:pass
  else:raise AssertionError('PID not absent '+str(own[k]))
 assert s['elapsed_seconds']<570 and s['peak_observed_process_tree_RSS_bytes']<=1250000000 and s['output_bytes']<=32000000
 assert s['output_bytes']==sum(f.stat().st_size for f in O.rglob('*') if f.is_file())
 c=read(P/'candidates.json');byid={x['ebook_ID']:x for x in c};entries=read(P/'body-sources-semantic.json');coverage=read(O/'source-coverage.json');rows=coverage['retained_body_sources'];assert len(rows)==len(entries)==837
 final=sqlite3.connect((BASE/'m2-intake/wikibooks-global-finalization-v3/finalized.sqlite3').as_uri()+'?mode=ro',uri=True)
 def signature(e):return [e['physical_source_SHA256'],e['adapter'],e.get('table'),e['required_current_candidate_body_coverage'],e['coverage_role'],e['semantic_coverage_role']]
 owners={};ownerproofs={};union=set();bodycount=0;owner_count=0;alias_count=0
 for e,v in zip(entries,rows):
  assert e['path']==v['path'] and e['adapter']==v['adapter'];sig=tuple(signature(e))
  if sig in owners:
   if e['semantic_coverage_role']=='CURRENT_WIKIBOOKS_FINALIZED_RENDERED':
    proof=ownerproofs[sig];assert v['exact_physical_alias_of']==owners[sig]['path'] and v['validated_owner_proof_SHA256']==objsha(proof) and v['validated_rows_inherited']==proof['validated_rows'] and v['role_and_body_coverage_inherited_from_complete_owner'] is True;alias_count+=1
   else:assert v['exact_file_alias_of']==owners[sig]['path']
   continue
  owners[sig]=e;bodycount+=v['body_records_observed']
  if e['semantic_coverage_role']!='CURRENT_WIKIBOOKS_FINALIZED_RENDERED':continue
  proof=v['WB_validated_owner_proof'];ownerproofs[sig]=proof;owner_count+=1
  db=sqlite3.connect(pathlib.Path(e['WB_canonical_paths'][0]).as_uri()+'?mode=ro',uri=True);ids=[x[0] for x in db.execute('select source_ordinal from rendered order by source_ordinal')];db.close();assert not union.intersection(ids);union.update(ids)
  role_rows=[];identities=[]
  for i in ids:
   page,rev,fam,body,prior,active,holds=final.execute('select p.page_id,p.revision_id,p.family,p.text_sha256,p.holds,p.active,f.holds from pages p join final_pages f on p.source_ordinal=f.source_ordinal where p.source_ordinal=?',(i,)).fetchone()
   role_rows.append(dict(source_ordinal=i,page_id=page,revision_id=rev,family=fam,text_sha256=body,prior_holds=json.loads(prior),active=active,global_final_holds=json.loads(holds)));identities.append([i,page,rev,fam,body])
  assert proof['source_signature']==signature(e) and proof['owner_path']==e['path'] and proof['complete_role_coverage'] is True and proof['complete_body_comparison'] is True and proof['all_prior_finalizer_holds_preserved'] is True
  assert proof['expected_ordinal_set_SHA256']==objsha(ids) and proof['identity_set_SHA256']==objsha(identities) and proof['final_role_binding_SHA256']==objsha(role_rows) and proof['validated_rows']==len(ids)==v['body_records_observed']
 assert len(union)==89758 and owner_count==12 and alias_count==4 and union=={x[0] for x in final.execute('select p.source_ordinal from pages p join final_pages f on p.source_ordinal=f.source_ordinal')};final.close()
 st=r['stats'];assert st['body_occurrences']==432499+8841+bodycount-st['metadata_only_external_body_references_reconciled'];assert st['legacy_rows']==432499 and r['historical_heldout']==252750 and r['protected_units']==8841 and r['M0_roles']=={'current_train':72116,'current_development':3999,'current_test':3923};assert coverage['current_Wikibooks_89758_finalized_body_identities_hashes_and_holds_reconciled']==89758
 holds=[json.loads(x) for x in (O/'coverage-holds.jsonl').read_text().splitlines()];assert sum(x['required_current_candidate_or_protected_coverage'] for x in holds)==r['coverage_holds_must_be_reviewed']==st.get('body_coverage_holds',0);assert sum(not x['required_current_candidate_or_protected_coverage'] for x in holds)==st.get('optional_raw_context_limits',0)
 sys.path.insert(0,str(P));import overlap_core as core
 norms=[core.normalized(pathlib.Path(x['file']).read_text()) for x in c];assert (O/'normalized-candidates.txt').read_text()==('\n'.join(norms)+'\n')
 matches=[json.loads(x) for x in (O/'body-matches.jsonl').read_text().splitlines()];assert len(matches)==st['matched_body_occurrences'];dispositions=collections.Counter()
 for m in matches:
  cand=byid[m['candidate_ebook_ID']];assert m['candidate_current_SHA256']==cand['text_SHA256'] and m['candidate_family_component_ID']==cand['family_component_ID'];path,key=m['source_identity'].rsplit('#',1);assert key=='file','New non-file match requires targeted independent source-body proof';norm=core.normalized(pathlib.Path(path).read_text());assert core.sha(norm.encode())==m['source_normalized_sha256']
  # One-candidate frozen matcher reproof changes only its local array index.
  assert core.Index([pathlib.Path(cand['file']).read_text()]).compare(norm).get(0)==m['match'];protected=m['source_role'] in ['historical_heldout','current_development','current_test','explicit_protected'];assert core.disposition(protected,path in [cand['file'],cand['captured_raw_source_ancestor']['path']])==m['disposition'];dispositions[m['disposition']]+=1
 family=read(O/'family-custody.json');frame=sqlite3.connect((BASE/'m2-intake/gutenberg-complete-English-metadata-frame-v2/frame.sqlite3').as_uri()+'?mode=ro',uri=True)
 assert len(family['candidate_components'])==17
 for cand,f in zip(c,family['candidate_components']):
  expected=[dict(ebook_ID=x,component_ID=y,roles=json.loads(z)) for x,y,z in frame.execute('select ebook_ID,component_ID,roles from families where component_ID=?',(cand['family_component_ID'],))];assert f['candidate']==cand['ebook_ID'] and f['component_ID']==cand['family_component_ID'] and f['conservative_component_members']==expected and f['not_proven_work_equivalence'] is True
 frame.close();protected_components=sorted({m['candidate_family_component_ID'] for m in matches if m['disposition']=='PROTECTED_FAMILY_HOLD'});assert family['protected_hits_propagate_whole_components']==r['protected_component_holds']==protected_components
 old=BASE/'m2-intake/individual-salvage-v1/overlap-v1';original_lines=(old/'protections.tsv').read_text().splitlines();actual_lines=(O/'protections-disjoint.tsv').read_text().splitlines();assert len(original_lines)==len(actual_lines)==8841
 protected_norm={}
 for i,(a,b) in enumerate(zip(original_lines,actual_lines)):
  _,n=a.split('\t',1);pid,n2=b.split('\t',1);assert int(pid)==1000000+i and n==n2;protected_norm[int(pid)]=n
 cpp=[]
 for l in (O/'CPP-containment.tsv').read_text().splitlines():
  ci,pid,t=l.split('\t',2);ci=int(ci);pid=int(pid);assert 1<=ci<=17 and pid in protected_norm and ' '+t+' ' in ' '+norms[ci-1]+' ' and ' '+t+' ' in ' '+protected_norm[pid]+' ';cpp.append(ci)
 assert r['CPP_Python_protected_agreement'] is True
 if not protected_components:assert not cpp
 assert r['all_inputs_rechecked'] is True and r['new_admitted_documents']==r['new_admitted_tokens']==0
 for p,h in pins.items():assert sha(p)==h,p
 report=dict(status='PASS_INDEPENDENT_TERMINAL_SOURCE_COVERAGE_AND_SAVED_MATCH_REPROOF',input_pins_verified_before_after=915,source_adapters=837,WB_owner_proofs=owner_count,WB_exact_alias_proofs=alias_count,WB_exact_finalizer_identities=len(union),body_occurrences=st['body_occurrences'],saved_matches_reproved=len(matches),match_dispositions=dict(dispositions),required_coverage_holds=r['coverage_holds_must_be_reviewed'],optional_scope_holds=holds,candidate_family_components_verified=17,protected_CPP_saved_hits_verified=len(cpp),terminal=s,elapsed_seconds=time.monotonic()-start,output_hashes={f.name:sha(f) for f in O.iterdir() if f.is_file()},scope=['No full-corpus rematch or reexecution; producer complete codepath plus exact source/role coverage reconciled','All saved matches re-read from exact file bodies and independently re-evaluated with pinned frozen matcher','12 canonical metadata identity/final-role digests recomputed; body-comparison completeness bound to completed audited worker lifecycle','Protected normalized8841 disjoint inventory exact; saved CPP proofs reconciled; producer certifies full Python/CPP hitset equality','No semantic/rights/unknown-ancestry clearance or admission follows solely from literal checks'])
 dest.mkdir();(dest/'verification.json').write_text(json.dumps(report,indent=2)+'\n');(dest/'manifest.json').write_text(json.dumps({'verification.json':sha(dest/'verification.json')},indent=2)+'\n');print(json.dumps({'verification_SHA256':sha(dest/'verification.json'),'manifest_SHA256':sha(dest/'manifest.json'),'summary':{k:v for k,v in report.items() if k not in ['output_hashes','scope','optional_scope_holds']}}));signal.alarm(0)
if __name__=='__main__':main()
