from pathlib import Path
import json,hashlib,sqlite3,subprocess,importlib.util,signal,time
signal.signal(signal.SIGALRM,lambda s,f:(_ for _ in ()).throw(TimeoutError('verification60sec')));signal.alarm(60)
O=Path(__file__).resolve().parent;B=O.parent;P=B/'wikibooks-three-composed-closure-preparation-v1';D=B/'m2-intake/wikibooks-three-composed-closure-v1';OLD=B/'wikibooks-three-renewed-custody-preparation-v1';PART=B/'m2-intake/wikibooks-three-renewed-custody-v1';FINAL=B/'m2-intake/wikibooks-global-finalization-v3/finalized.sqlite3'
def H(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def shao(x):return hashlib.sha256(json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def ro(p):return sqlite3.connect(Path(p).as_uri()+'?mode=ro',uri=True)
ready=json.loads((P/'readiness.json').read_text());assert H(P/'code-pins.json')==ready['codepins_SHA256'] and H(P/'profile.json')==ready['profile_SHA256'];pins=json.loads((P/'code-pins.json').read_text())['SHA256']
for path,digest in pins.items():assert H(path)==digest,path
r=json.loads((D/'result.json').read_text());sup=json.loads((D/'supervisor.json').read_text());assert r['status']=='COMPLETE_SEPARATE_COMPOSED_LITERAL_COVERAGE_ROLE_DELTA_NOT_PRODUCER_RERUN_OR_ADMISSION' and sup['status']=='COMPLETE' and sup['child_reaped'] and sup['returncode']==0
for f,h in r['output_SHA256'].items():assert H(D/f)==h
absence=[]
for parent in [D,PART]:
 own=json.loads((parent/'ownership.json').read_text())
 for key in ['supervisor_PID','worker_PID']:
  pid=own[key];z=subprocess.run(['ps','-p',str(pid),'-o','pid='],capture_output=True,text=True,timeout=2);assert z.returncode==1 and not z.stdout.strip();absence.append({'receipt':str(parent/'ownership.json'),'PID':pid,'absent':True})
assert r['original_producer_result_SHA256']==H(PART/'result.json') and json.loads((PART/'result.json').read_text())['status']=='TERMINAL_PARTIAL_CUSTODY_SCREEN_NO_RETRY_NO_ZERO_CLAIM'
db=ro(FINAL);db.execute('pragma cache_size=-2048');roles={}
for ordinal,page,revision,family,digest,prior,active,final in db.execute('select p.source_ordinal,p.page_id,p.revision_id,p.family,p.text_sha256,p.holds,p.active,f.holds from pages p join final_pages f using(source_ordinal)'):
 roles[ordinal]={'source_ordinal':ordinal,'page_id':page,'revision_id':revision,'family':family,'text_sha256':digest,'prior_holds':json.loads(prior),'active':active,'global_final_holds':json.loads(final)}
assert len(roles)==89758
roleproof=json.loads((D/'role-only-proofs.json').read_text());fresh=set()
for p in roleproof['role_only_owner_proofs']:
 d=ro(p['owner_path']);metadata=list(d.execute('select source_ordinal,page_id,revision_id,family from rendered order by source_ordinal'));d.close();ids=[row[0] for row in metadata];assert not fresh&set(ids);fresh.update(ids)
 for ordinal,page,rev,family in metadata:assert (page,rev,family)==tuple(roles[ordinal][k] for k in ['page_id','revision_id','family'])
 ordered=[roles[i] for i in ids];identity=[[v[k] for k in ['source_ordinal','page_id','revision_id','family','text_sha256']] for v in ordered]
 assert len(ids)==p['validated_rows'] and shao(ids)==p['expected_ordinal_set_SHA256'] and shao(identity)==p['identity_set_SHA256'] and shao(ordered)==p['final_role_binding_SHA256'] and p['complete_role_coverage'] and not p['complete_body_comparison'] and p['all_prior_finalizer_holds_preserved']
residual=set(roles)-fresh;assert len(fresh)==50457 and len(residual)==39301 and shao(sorted(fresh))==roleproof['fresh_ordinal_set_SHA256'] and shao(sorted(residual))==roleproof['residual_ordinal_set_SHA256'] and shao(sorted(roles))==roleproof['union_ordinal_set_SHA256']
# Inspect only the ten frozen positive witnesses; never construct matcher index or search full sources.
spec=importlib.util.spec_from_file_location('frozen_normalizer',OLD/'overlap_core.py');core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
candidates={c['source_ordinal']:c for c in json.loads((OLD/'candidates.json').read_text())};old=[json.loads(l) for l in (PART/'body-matches.jsonl').read_text().splitlines()];new=json.loads((D/'match-reconciliation.json').read_text());assert len(old)==len(new)==10
witnesses=[]
for a,b in zip(old,new):
 assert (a['candidate_source_ordinal'],a['source_identity'],a['disposition'])==(b['candidate_source_ordinal'],b['source_identity'],b['original_disposition_preserved']) and b['saved_match_reproduced'] and b['protected_priority_preserved']
 c=candidates[a['candidate_source_ordinal']];raw=Path(c['captured_raw_source_ancestor']['path']).read_bytes();iv=c['original_source_interval'];candidate=Path(c['file']).read_bytes();assert H(c['file'])==c['text_SHA256'] and candidate==raw[iv['start']:iv['end_exclusive']]
 path=a['source_identity'].split('#',1)[0];current=b['new_role']
 if current:
  d=ro(path);page,rev,family,payload=d.execute('select page_id,revision_id,family,data from rendered where source_ordinal=?',(current['source_ordinal'],)).fetchone();d.close();obj=json.loads(payload);text=obj['text'];base=roles[current['source_ordinal']];assert all(current[k]==v for k,v in base.items());assert (page,rev,family)==tuple(base[k] for k in ['page_id','revision_id','family']);assert hashlib.sha256(text.encode()).hexdigest()==base['text_sha256']==obj['extracted_text_sha256'] and obj['family_id']==base['family']
 else:text=Path(path).read_bytes().decode();assert path in [c['file'],c['captured_raw_source_ancestor']['path']]
 norm=core.normalized(text);cn=core.normalized(candidate.decode());assert core.sha(norm.encode())==a['source_normalized_sha256'];match=a['match'];contain=match.get('containment')
 if contain:
  words=norm.split();offset=contain['source_word_offset'];assert ' '.join(words[offset:offset+contain['words']])==contain['text'] and ' '+contain['text']+' ' in ' '+cn+' '
 if match.get('normalized_exact'):assert norm==cn
 if 'fivegram_Jaccard_gte_0p8' in match:
  def grams(s):w=s.split();return set(tuple(w[i:i+5]) for i in range(len(w)-4))
  x,y=grams(norm),grams(cn);j=match['fivegram_Jaccard_gte_0p8'];assert len(x&y)==j['intersection'] and len(x|y)==j['union'] and len(x&y)/len(x|y)==j['jaccard']>=.8
 witnesses.append({'candidate':c['source_ordinal'],'identity':a['source_identity'],'saved_witness_exact':True,'disposition':b['new_source_role_bound_disposition'],'same_family_pending_parent':b['same_conservative_family_body_match_pending_parent_adjudication']})
families=json.loads((D/'family-custody.json').read_text());assert len(families)==3
for f in families:
 rows=[{'source_ordinal':r[0],'page_id':r[1],'revision_id':r[2],'title':r[3],'text_SHA256':r[4],'active':r[5],'prior_holds':json.loads(r[6]),'final_holds':json.loads(r[7])} for r in db.execute('select p.source_ordinal,p.page_id,p.revision_id,p.title,p.text_sha256,p.active,p.holds,f.holds from pages p join final_pages f using(source_ordinal) where p.family=? order by p.source_ordinal',(f['conservative_family_ID'],))]
 assert rows==f['all_current_metadata_members'] and not f['split_assigned'] and f['unresolved_import_transclusion_component_rights_holds_preserved']
db.close();assert r['protected_match_holds']==0 and r['unresolved_match_custody_holds']==1 and r['new_admitted_documents']==0
out={'status':'PASS_INDEPENDENT_COMPOSED_CLOSURE_VERIFICATION_NOT_ADMISSION','pins_rehashed':len(pins),'owned_PIDs_absent':absence,'terminal_output_pins':{str(p):H(p) for p in D.iterdir() if p.is_file()},'role_union':{'fresh_role_only':len(fresh),'prior_residual':len(residual),'full_exact_union':len(roles),'all_per_owner_identity_and_final_role_digests_recomputed':True,'fresh_text_body_rehash_not_repeated_role_producer_receipts_and_physical_store_pins_bound':True},'saved_positive_witnesses_verified':witnesses,'full_matcher_or_negative_source_search_rerun':False,'family_member_counts':{f['candidate_source_ordinal']:len(f['all_current_metadata_members']) for f in families},'remaining_hold':'One same-family held print/aggregate containment match remains parent adjudication; no protected component hit. Source/import/rights and individual quality gates not cleared.','original_producer_remains_partial':True,'new_admitted_documents':0};(O/'verification.json').write_text(json.dumps(out,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'files':{p.name:H(p) for p in O.iterdir() if p.is_file() and p.name!='manifest.json'}},indent=2)+'\n');print('verification',H(O/'verification.json'));print('manifest',H(O/'manifest.json'));signal.alarm(0)
