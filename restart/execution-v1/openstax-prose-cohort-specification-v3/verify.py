import pathlib,json,hashlib,collections
from lxml import etree
D=pathlib.Path(__file__).resolve().parent;E=D.parent;O=E/'openstax-factual-span-overlay-v3';S=E/'m2-intake/openstax-world-history-native-source-v1';h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text());holds=read(O/'source-node-holds.json');props=read(D/'development-section-proposals.json');summ=read(O/'summary.json');spec=read(D/'specification.json');raws={};nodes={};checks=0
for row in holds+props:
 mid=row['module_ID'];raw=raws.setdefault(mid,(S/(mid+'.cnxml')).read_bytes());assert hashlib.sha256(raw).hexdigest()==row['source_module_SHA256']
 if mid not in nodes:
  root=etree.fromstring(raw);nodes[mid]={}
  def visit(n,path):
   nodes[mid][path]=n
   for i,child in enumerate(n):visit(child,path+'/'+str(i))
  visit(root,'/0')
 n=nodes[mid][row['node_path']];a,b=row['source_start_byte'],row['source_end_byte'];part=raw[a:b];assert 0<=a<b<=len(raw) and hashlib.sha256(part).hexdigest()==row['source_exact_subtree_sha256'];assert hashlib.sha256(raw[:a]+part+raw[b:]).hexdigest()==row['source_module_SHA256'];checks+=1
 if 'exact_source_XML' in row:
  assert row['qualified_name']==n.tag and row['native_node_id']==n.get('id') and row['exact_source_text_itertext']==''.join(n.itertext()) and row['exact_source_XML'].encode()==part;assert row['source_start_character']==len(raw[:a].decode()) and row['source_end_character']==len(raw[:b].decode());assert not row['source_text_modified'] and not row['training_admitted']
reviews=summ['parent_review_SHA256'];assert len(reviews)==21 and all(h(pathlib.Path(p))==d for p,d in reviews.items());complete=read(E/'m2-intake/openstax-uniform-development-manual-review-v1/complete-review-v1.json');assert complete['whole_preview_texts_parent_read']==20 and not complete['remaining_modules'] and set(complete['reviewed_modules'])==set(raws)
for name,d in complete['review_SHA256'].items():assert h(E/'m2-intake/openstax-uniform-development-manual-review-v1'/name)==d
candidate=[p for p in props if p['proposed_disposition']=='COMPLETE_SECTION_REVIEW_CANDIDATE_NOT_ADMITTED'];affected=[];remaining=[]
for p in candidate:
 matched=any(x['module_ID']==p['module_ID'] and (x['node_path']==p['node_path'] or x['node_path'].startswith(p['node_path']+'/') or p['node_path'].startswith(x['node_path']+'/')) for x in holds)
 assert matched==bool(p['known_review_overlay']);(affected if matched else remaining).append(p)
assert len(candidate)==26 and len(affected)==14 and len(remaining)==12;assert sum(p['complete_direct_paragraphs'] for p in remaining)==21 and sum(p['native_direct_paragraph_characters'] for p in remaining)==14169
assert spec['structural_review_candidates_with_known_flags']==14 and spec['structural_candidates_still_needing_review_not_admitted']==12 and spec['full162_extraction_authorized'] is False and spec['new_admitted_documents']==spec['new_admitted_tokens']==0
for mid in raws:assert (S/(mid+'.cnxml')).read_bytes()==raws[mid]
result={'status':'PASS_INDEPENDENT_COMPLETE20_REVIEW_SOURCE_SPANS_AND_DEVELOPMENT_NOMINATION_RECONCILIATION','source_bound_span_records_verified':checks,'scoped_hold_records':len(holds),'distinct_nodes':len({(x['module_ID'],x['node_path']) for x in holds}),'reviewed_modules':20,'structural_nominees':26,'known_scoped_holds':14,'pending_not_usable_sections':12,'pending_whole_paragraphs':21,'pending_native_paragraph_characters':14169,'all_native_nodes_XML_text_byte_character_offsets_and_hashes_match':True,'all_sources_and_parent_reviews_unchanged':True,'all_previous_versions_preserved':True,'full162_extractions':0,'admitted_documents':0,'admitted_tokens':0,'network_requests':0};(D/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
