import pathlib,json,hashlib,sqlite3,copy
R=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1'); P=R/'m2-intake/gutenberg-post1900-individual-admissions-v1'; Q=R/'gutenberg-fourteen-individual-admission-preparation-v3'; O=R/'gutenberg-post1900-admissions-independent-verification-v1'
def sha(b):return hashlib.sha256(b).hexdigest()
def h(p):return sha(pathlib.Path(p).read_bytes())
def j(p):return json.loads(pathlib.Path(p).read_text())
def pool(p,expected=None):
 m=j(p/'manifest.json');assert not expected or h(p/'manifest.json')==expected
 actual={str(x.relative_to(p)) for x in p.rglob('*') if x.is_file()};assert actual==set(m['files'])|{'manifest.json'}
 for n,v in m['files'].items():
  x=p/n;assert h(x)==v['SHA256'] and x.stat().st_size==v['bytes'];assert not x.stat().st_mode&0o222
 assert not (p/'manifest.json').stat().st_mode&0o222
 return {'manifest_SHA256':h(p/'manifest.json'),'verified_files':len(actual),'all_files_readonly':True}
verified=pool(P,'f51fd9c50b1deae525a0ba3d49dbb8aad6fcafe110abd9388e4ca210ca206064')
docs=j(P/'documents.json');prop=j(Q/'documents.proposed.json');assert len(docs)==len(prop)==14
assert [d['ebook_ID'] for d in docs]==[3380,33924,9965,29023,9052,6718,6769,17866,1734,1762,3172,18948,22030,7170]
checks=[]
for d,a in zip(docs,prop):
 b=(P/d['body_reference']['path']).read_bytes();old=pathlib.Path(a['body_reference']['path']).read_bytes();s=d['original_source'];raw=pathlib.Path(s['path']).read_bytes();start,end=s['byte_interval'];rec=j(d['strict_language_receipt_reference'])
 assert b==old==raw[start:end] and sha(raw)==s['SHA256'] and sha(b)==d['body_reference']['SHA256']
 assert len(b)==d['body_reference']['UTF8_bytes']==rec['UTF8_bytes'] and sha(b)==rec['unit_SHA256']
 assert rec['M1_content_tokens']==d['M1_content_tokens_existing_receipt'] and d['EOS_separate']==rec['one_EOS_separate']==1
 assert d['strict_language_pass'] and d['whole_unit_readability_coherence_completeness_individual_review'] and d['split']=='train'
 aa=copy.deepcopy(a);dd=copy.deepcopy(d);aa['body_reference']['path']=dd['body_reference']['path']
 for k in ['publication_status','split','primary_genre']:dd.pop(k,None);aa.pop(k,None)
 assert aa==dd,('document_proposal_delta',d['ebook_ID'],set(aa)^set(dd))
 checks.append({'ebook_ID':d['ebook_ID'],'SHA256':sha(b),'bytes':len(b),'existing_content_tokens':rec['M1_content_tokens'],'receipt_SHA256':h(d['strict_language_receipt_reference']),'raw_inverse_exact':True})
assert sum(x['bytes'] for x in checks)==443370 and sum(x['existing_content_tokens'] for x in checks)==144780
assert j(P/'source-attribution-and-components.json')==j(Q/'source-attribution-and-components.proposed.json')
for d,a in zip(docs,j(P/'source-attribution-and-components.json')):
 assert d['ebook_ID']==a['ebook_ID'] and a['main_SHA256']==d['body_reference']['SHA256'] and a['current_raw_SHA256']==d['original_source']['SHA256']
 raw=pathlib.Path(d['original_source']['path']);header=raw.with_name('pg%s-hop1.json'%d['ebook_ID']);assert h(header)==a['current_header_SHA256']
notes=j(P/'external-notes.source-companions.json');prior=j(Q/'external-notes.source-companions.proposed.json');notechecks=[]
for n,a in zip(notes,prior):
 b=(P/n['reference']['path']).read_bytes();assert b==pathlib.Path(a['reference']['path']).read_bytes();raw=(R/'m2-intake/gutenberg-post1900-cohort-raw-v3/pg22030.raw').read_bytes();x,y=n['source_byte_interval'];assert raw[x:y]==b and sha(raw)==n['original_raw_SHA256'] and sha(b)==n['reference']['SHA256']
 assert n['admitted_main_document'] is False and n['tokens_added_to_main_supply']==0
 aa=copy.deepcopy(a);dd=copy.deepcopy(n);aa['reference']['path']=dd['reference']['path'];dd.pop('admitted_main_document');dd.pop('tokens_added_to_main_supply');assert aa==dd
 notechecks.append({'key':n['document_key'],'SHA256':sha(b),'bytes':len(b),'existing_tokens_not_added':n['existing_M1_content_tokens']})
assert len(notes)==4 and sum(n['existing_M1_content_tokens'] for n in notes)==1181
families=j(P/'family-train-overlay.json');prior=j(Q/'family-train-reservations.proposed.json');con=sqlite3.connect('file:'+str(R/'m2-intake/gutenberg-complete-English-metadata-frame-v2/frame.sqlite3')+'?mode=ro',uri=True)
for f,a in zip(families,prior):
 assert f['assignment']=='train' and f['held_siblings_not_promoted'] and f['no_mutation_of_M0_original_or_existing_admitted_manifests']
 actual=con.execute('select ebook_ID,component_ID,roles from families where component_ID=? order by ebook_ID',(f['family_component_ID'],)).fetchall();expected=[(v['ebook_ID'],v['component_ID'],json.dumps(v['roles'],sort_keys=True)) for v in f['all_current_metadata_members']];assert [(x,y,json.dumps(json.loads(z),sort_keys=True)) for x,y,z in actual]==expected
 dd=copy.deepcopy(f);dd.pop('assignment');dd.pop('scope');assert dd==a
assert len(families)==14 and sum(f['members_count'] for f in families)==15
potential=j(P/'potential-3172-raw-ancestry-train-overlay.json');prior=j(Q/'potential-3172-raw-ancestry-reservations.proposed.json');assert len(potential['exact_targets'])==2 and 'protected' in potential['protected_priority'].lower()
for t,a in zip(potential['exact_targets'],prior['exact_targets']):
 dd=copy.deepcopy(t);dd.pop('custody');assert dd==a and not t['body_admitted'] and not t['extra_document_or_tokens_counted'] and not t['confirmed_same_work'] and not t['registry_hits']
for k in ['mapping_evidence','all1147_hint_review']:assert h(potential[k]['path'])==potential[k]['SHA256']
dec=j(P/'admission-decision.json');evidence=[]
for n,digest in dec['evidence_SHA256'].items():assert h(R/n)==digest;evidence.append({'path':n,'SHA256':digest})
assert dec['future_known_parent_collection_context_constraints'][0]['ebook_ID']==3380 and 'Literature and Life'==dec['future_known_parent_collection_context_constraints'][0]['known_parent_collection']
old=j(R/'m2-intake/gutenberg-individual-admissions-independent-verification-v1/verification.json');legacy=old['legacy_current_hashes_match_recorded_prepublication']
for p,digest in legacy.items():assert h(p)==digest
oldpg=pool(R/'m2-intake/gutenberg-individual-admissions-v1','4abc4f880f6f51fa33fcd5012d9e03f2c816ae7468293b50670492f520edd77d');wb=pool(R/'m2-intake/wikibooks-individual-admissions-v1')
counts=j(P/'counts.json');assert counts['admitted_documents']==14 and counts['M1_content_tokens']==144780 and counts['EOS_separate']==14 and counts['UTF8_bytes']==443370
out={'status':'PASS_ACTUAL_PARENT_PUBLISHED_INDIVIDUAL_ADMISSION_VERIFIED','pool':str(P),'publication':verified,'main_units':checks,'notes':notechecks,'actual_admitted_documents':14,'M1_content_tokens':144780,'EOS_separate':14,'UTF8_bytes':443370,'notes_not_added_to_main_tokens':1181,'whole_metadata_train_families':14,'catalog_members_reserved':15,'potential_raw_3172_reservations':2,'protected_priority_preserved':True,'source_attribution_components_equal_reviewed_v3':True,'known_Howells_Literature_and_Life_future_train_constraint_preserved':True,'decision_evidence':evidence,'original_M0_train_manifest_FineWeb_hashes_unchanged':legacy,'old_four_PG_pool':oldpg,'old_one_WB_pool':wb,'model_tokenizer_matcher_network_invocations':0,'publication_or_count_state_edits':False,'scope':'Exact14main individualsourcepool only. Four notes separate/unadmitted. No finalM2mixture/cohortacceptance or training approval.'}
(O/'verification.json').write_text(json.dumps(out,indent=2)+'\n');(O/'manifest.json').write_text(json.dumps({'status':'PASS','files':{n:{'SHA256':h(O/n),'bytes':(O/n).stat().st_size} for n in ['verify.py','verification.json']}},indent=2)+'\n');print(json.dumps({'status':'PASS','verification_SHA256':h(O/'verification.json'),'manifest_SHA256':h(O/'manifest.json'),'old_WB_manifest_SHA256':wb['manifest_SHA256']}))
