import hashlib,json,pathlib,sys,collections
from lxml import etree
D=pathlib.Path(__file__).resolve().parent;E=D.parent;P=E/'openstax-cnxml-structured-preparation-v2';sys.path.insert(0,str(P));import render as r
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();CN='{'+r.CN+'}';REVIEW=E/'m2-intake/openstax-uniform-development-manual-review-v1';reviews={};pins={}
for i in range(1,21):
 f=REVIEW/f'review-{i:03d}.json';v=json.loads(f.read_text());assert v['whole_preview_text_read_by_parent'];reviews[v['selected_module']]=(f,v);pins[str(f.resolve())]=h(f)
assert len(reviews)==20
sample={x['module_ID']:x for x in json.loads((P/'development-sample.json').read_text())['selected_modules']};assert set(reviews)==set(sample)
complete=REVIEW/'complete-review-v1.json';pins[str(complete.resolve())]=h(complete)
rows=json.loads((E/'openstax-factual-span-overlay-v2/source-node-holds.json').read_text());roots={};maps={};raws={}
for mid in sample:
 raw=(r.SOURCE/(mid+'.cnxml')).read_bytes();assert hashlib.sha256(raw).hexdigest()==sample[mid]['source_sha256'];root=r.generic.validate_input(raw,sample[mid]);roots[mid]=root;maps[mid]=r.spans(raw,root);raws[mid]=raw
known_error_keys={'Gaugamela','Pyrrhus','Aleutian','UNFCCC'};internal_keys={'Northern','NorthAfrica','king_versus','no_external','263','caption'}
for row in rows:
 key=row['finding_key'];row['disposition_category']='PARENT_EXTERNALLY_SUPPORTED_ERROR_HOLD' if any(s in key for s in known_error_keys) else ('SOURCE_INTERNAL_CONTRADICTION_OR_TENSION_HOLD' if any(s in key for s in internal_keys) else ('CONTEXT_OR_COMPONENT_RIGHTS_REVIEW_HOLD' if any(s in key for s in ['context','quoted','inset']) else ('SOURCE_WORDING_ERROR_HOLD' if 'grammar' in key else 'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD')))
 row['source_start_character']=len(raws[row['module_ID']][:row['source_start_byte']].decode());row['source_end_character']=len(raws[row['module_ID']][:row['source_end_byte']].decode())
# IDs below refer only to observed parent-flagged assertions, complete paragraphs retained as holds.
rules={
'm00118':{'SOURCE_INTERNAL_CONTRADICTION_OR_TENSION_HOLD':[8],'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD':[2,24,25,38],'SOURCE_WORDING_ERROR_HOLD':[27,32,35,49]},
'm00125':{'SOURCE_INTERNAL_CONTRADICTION_OR_TENSION_HOLD':[25],'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD':[3,4,5,6,19,23],'DATED_CONTEXT_HOLD':[20]},
'm00070':{'SOURCE_INTERNAL_CONTRADICTION_OR_TENSION_HOLD':[8,55],'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD':[6,9,19,28,29,31,45],'SOURCE_WORDING_ERROR_HOLD':[26]},
'm00159':{'SOURCE_INTERNAL_CONTRADICTION_OR_TENSION_HOLD':[20],'UNVERIFIED_MEDICAL_OR_HISTORICAL_CLAIM_HOLD':[3,4,6,21,22,35]},
'm00076':{'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD':[21,27,33,42,43,48]},
'm00032':{'SOURCE_INTERNAL_CONTRADICTION_OR_TENSION_HOLD':[22,25,38],'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD':[4,5,9]},
'm00107':{'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD':[4,10,17,19,27]},
'm00090':{'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD':[5,13,17,18,20,22,24,28,31,36]},
'm00022':{'PARENT_EXTERNALLY_SUPPORTED_ERROR_HOLD':[37,43],'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD':[4,8,12,16],'SOURCE_WORDING_OR_ENCODING_ERROR_HOLD':[16]},
'm00144':{'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD':[2,6,7,8,11,12,19,21,25,26,33,40,42,47]},
'm00096':{'SOURCE_INTERNAL_CONTRADICTION_OR_TENSION_HOLD':[39],'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD':[9,18,24,35,40]},
'm00026':{'SOURCE_INTERNAL_CONTRADICTION_OR_TENSION_HOLD':[226],'UNVERIFIED_FACTUAL_OR_EDITORIAL_CLAIM_HOLD':[202,205,208,212,217,219,220,223,235,236,240,243]}}

def add(mid,n,category,key):
 m=maps[mid][n];raw=raws[mid];a,b=m['source_start_byte'],m['source_end_byte'];chunk=raw[a:b];assert hashlib.sha256(chunk).hexdigest()==m['source_exact_subtree_sha256'];assert raw[:a]+chunk+raw[b:]==raw
 sec=n
 while sec is not None and sec.tag!=CN+'section':sec=sec.getparent()
 reviewfile,review=reviews[mid]
 row={'module_ID':mid,'source_module_SHA256':sample[mid]['source_sha256'],'native_node_id':n.get('id'),'qualified_name':n.tag,**m,'source_start_character':len(raw[:a].decode()),'source_end_character':len(raw[:b].decode()),'exact_source_XML':chunk.decode(),'exact_source_text_itertext':''.join(n.itertext()),'disposition_category':category,'factual_disposition':'PARENT_FLAGGED_HOLD_NO_AUTOMATIC_CORRECTION_OR_FACTUAL_CERTIFICATION','finding_key':key,'parent_review_file':str(reviewfile.resolve()),'parent_review_SHA256':h(reviewfile),'parent_review_issue_records':review.get('issues',review.get('factual_risk',[])),'containing_section_node_path':maps[mid][sec]['node_path'] if sec is not None else None,'containing_section_title':''.join(sec.find(CN+'title').itertext()) if sec is not None and sec.find(CN+'title') is not None else None,'structural_status':'SEPARATE_FROM_FACTUAL_DISPOSITION','proposed_unit_policy':'Hold whole exact paragraph/caption/media/inset or containing section. No sentence rewriting/omission. Independent sections retain distinct pending review.','family_id':'openstax:world-history-2024-both-volumes','source_text_modified':False,'training_admitted':False};rows.append(row)
for mid,categories in rules.items():
 for category,ids in categories.items():
  for ident in ids:
   ident=f'para-{ident:05d}';nodes=roots[mid].xpath('//*[@id=$ident]',ident=ident);assert len(nodes)==1,(mid,ident);add(mid,nodes[0],category,'full20_parent_review:'+ident)
# Distinct media/definition errors, exact observed source nodes; retain whole figure when media/caption pairs apply.
for mid,tag,attribute,needle,category in [
 ('m00107','caption',None,'built circa 2500 BCE','PARENT_EXTERNALLY_SUPPORTED_ERROR_HOLD'),
 ('m00107','media','alt','alt text placeholder','MISSING_SOURCE_MEDIA_CONTENT_HOLD'),
 ('m00076','media','alt','Jamestown (1608)','SOURCE_INTERNAL_MEDIA_DATE_MISMATCH_HOLD'),
 ('m00022','caption',None,'Germany children','SOURCE_WORDING_ERROR_HOLD'),
 ('m00096','media','alt','Lower Nubia','PARENT_REPORTED_MEDIA_LABEL_ERROR_HOLD'),
 ('m00090','definition',None,'final phase of the Paleolithic Age','PARENT_REPORTED_DEFINITION_ERROR_HOLD')]:
 ns=[n for n in roots[mid].iter(CN+tag) if needle in (n.get(attribute,'') if attribute else ''.join(n.itertext()))];assert ns,(mid,needle)
 if mid=='m00096':
  # Exact duplicated Upper/Lower label issue in one source map alt, not every Nubia map.
  ns=[n for n in ns if n.get('alt','').count('Lower Nubia')>=2];assert len(ns)==1
 for n in ns:
  ancestor=n
  while ancestor is not None and ancestor.tag!=CN+'figure':ancestor=ancestor.getparent()
  add(mid,ancestor if ancestor is not None else n,category,'full20_parent_review:'+needle)
# Every quotation is an attribution-bearing component, not automatically licensed textbook narration.
# Hold the entire immediate containing note/inset, including attribution and critical context.
quoteunits=set()
for mid,root in roots.items():
 for q in root.iter(CN+'quote'):
  node=q;ancestor=q.getparent()
  while ancestor is not None and ancestor.tag not in {CN+'note',CN+'section',CN+'content'}:ancestor=ancestor.getparent()
  if ancestor is not None and ancestor.tag==CN+'note':node=ancestor
  key=(mid,maps[mid][node]['node_path'])
  if key not in quoteunits:add(mid,node,'CONTEXT_OR_COMPONENT_RIGHTS_REVIEW_HOLD','complete_attributed_quotation_component_pending_rights_and_context');quoteunits.add(key)
# Each hold is source-bound. Multiple issues may share one node but are never counted as separate prose documents.
for row in rows:
 raw=raws[row['module_ID']];a,b=row['source_start_byte'],row['source_end_byte'];chunk=raw[a:b];assert chunk.decode()==row['exact_source_XML'];assert hashlib.sha256(chunk).hexdigest()==row['source_exact_subtree_sha256'];assert raw[:a]+chunk+raw[b:]==raw
proposals=json.loads((E/'openstax-prose-cohort-specification-v1/development-section-proposals.json').read_text());overlay=[]
for p in proposals:
 affected=[x for x in rows if x['module_ID']==p['module_ID'] and (x['node_path']==p['node_path'] or x['node_path'].startswith(p['node_path']+'/') or p['node_path'].startswith(x['node_path']+'/'))]
 if affected:overlay.append({'module_ID':p['module_ID'],'section_node_path':p['node_path'],'section_title':p['section_title_literal'],'structural_disposition':p['proposed_disposition'],'factual_context_or_rights_disposition':'HOLD_COMPLETE_SECTION_PARENT_FLAGGED_NODES','known_flagged_source_node_paths':sorted(set(x['node_path'] for x in affected)),'categories':sorted(set(x['disposition_category'] for x in affected)),'was_structural_review_candidate':p['proposed_disposition']=='COMPLETE_SECTION_REVIEW_CANDIDATE_NOT_ADMITTED'})
affected={(x['module_ID'],x['section_node_path']) for x in overlay};candidates=[p for p in proposals if p['proposed_disposition']=='COMPLETE_SECTION_REVIEW_CANDIDATE_NOT_ADMITTED'];remaining=[p for p in candidates if (p['module_ID'],p['node_path']) not in affected];held=[p for p in candidates if (p['module_ID'],p['node_path']) in affected]
coverage=[]
for mid,(f,review) in reviews.items():
 coverage.append({'module_ID':mid,'parent_review_file':str(f.resolve()),'parent_review_SHA256':h(f),'whole_preview_read':True,'all_parent_issue_records_retained':review.get('issues',review.get('factual_risk',[])),'scoped_node_hold_records':sum(x['module_ID']==mid for x in rows),'structurally_held_section_paths':[p['node_path'] for p in proposals if p['module_ID']==mid and p['proposed_disposition']!='COMPLETE_SECTION_REVIEW_CANDIDATE_NOT_ADMITTED'],'remaining_disposition':'Remaining independent candidate sections have not been fact/rights/acceptance certified; all source-level rights and cross-source checks remain pending.'})
summary={'status':'ALL20_PARENT_FULL_PREVIEW_REVIEWS_BOUND_TO_EXACT_SOURCE_NODE_HOLDS_NO_REWRITING','reviewed_development_modules':20,'development_sample_size_unchanged':20,'parent_review_SHA256':pins,'source_node_hold_records':len(rows),'distinct_source_nodes_held':len({(x['module_ID'],x['node_path']) for x in rows}),'category_counts_nonexclusive':dict(collections.Counter(x['disposition_category'] for x in rows)),'complete_attributed_quotation_units':len(quoteunits),'affected_complete_sections':len(overlay),'structural_review_candidates_total':len(candidates),'structural_candidates_with_known_parent_flags':len(held),'other_structural_candidates_pending_all_remaining_gates':len(remaining),'before_candidate_direct_paragraphs':sum(x['complete_direct_paragraphs'] for x in candidates),'after_known_holds_pending_candidate_direct_paragraphs':sum(x['complete_direct_paragraphs'] for x in remaining),'before_candidate_native_paragraph_characters':sum(x['native_direct_paragraph_characters'] for x in candidates),'after_known_holds_pending_candidate_native_paragraph_characters':sum(x['native_direct_paragraph_characters'] for x in remaining),'separate_module_context_holds':['m00001','m00122'],'all_source_byte_span_reconstructions_PASS':True,'source_modules_all_unchanged':True,'no_factual_or_rights_clearance':True,'no_extrapolation_to162':True,'sentence_edits':0,'new_admitted_documents':0,'new_admitted_tokens':0}
for name,obj in [('source-node-holds.json',rows),('section-overlay.json',overlay),('review-coverage.json',coverage),('remaining-development-candidates.json',remaining),('summary.json',summary)]: (D/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
for mid in sample:assert h(r.SOURCE/(mid+'.cnxml'))==sample[mid]['source_sha256']
(D/'manifest.json').write_text(json.dumps({p.name:h(p) for p in D.iterdir() if p.is_file() and p.name!='manifest.json'},indent=2)+'\n');print(json.dumps(summary,indent=2))
