import collections,hashlib,json,pathlib,re
from lxml import etree
P=pathlib.Path(__file__).resolve().parent;E=P.parent;D=E/'m2-intake/openstax-structured-development-v2';h=lambda p:hashlib.file_digest(p.open('rb'),'sha256').hexdigest();sample=json.loads((P/'development-sample.json').read_text());receipt=json.loads((D/'receipt.json').read_text());supervisor=json.loads((D/'supervisor.json').read_text());assert supervisor['worker_exit_code']==0 and supervisor['reason'] is None and supervisor['elapsed_seconds']<300 and supervisor['peak_observed_owned_tree_RSS_bytes']<1000000000;holds=collections.Counter();kinds=collections.Counter();misses=[];checked=0;paragraphs=0;emptyrefs=0;questions=0;glossary=0
for x in sample['selected_modules']:
 mid=x['module_ID'];source=E/'m2-intake/openstax-world-history-native-source-v1'/(mid+'.cnxml');raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==x['source_sha256'];r=json.loads((D/(mid+'.json')).read_text());text=(D/(mid+'.txt')).read_text();ast=json.loads((D/(mid+'.AST.json')).read_text());assert not r['training_admitted'] and r['source_sha256']==x['source_sha256'];root=etree.fromstring(raw);content=root.find('{http://cnx.rice.edu/cnxml}content')
 def ast_text(n):
  if 'kind' in n:return n.get('tail') or ''
  return (n['text'] or '')+''.join(ast_text(c) for c in n['children'])+(n['tail'] or '')
 assert ast_text(ast)==''.join(root.itertext())
 for b in r['blocks']:assert hashlib.sha256(raw[b['source_start_byte']:b['source_end_byte']]).hexdigest()==b['source_exact_subtree_sha256'];kinds[b['kind']]+=1
 for n in content.iter():
  for v in [n.text,n.tail]:
   if v and v.strip():
    checked+=1
    if v.strip() not in text:misses.append({'module':mid,'node':str(n.tag),'literal':v.strip()})
  if n.tag.endswith('}para'):paragraphs+=1
 for d in r['dependencies']:
  if d['kind']=='unresolved_embedded_question':questions+=1
  if d['kind']=='literal_reference_unresolved_visible_label':emptyrefs+=1
 glossary+=sum(b['kind']=='glossary_definition' for b in r['blocks']);holds.update(r['holds'])
assert not misses,misses;assert questions>0 and emptyrefs>0 and glossary>0
# Concrete actual development defect regression.
t=(D/'m00042.txt').read_text();assert 'role of the slave trade in city-states' in ' '.join(t.split());assert '\nslave trade\n' not in t
summary={'status':'PASS_ACTUAL20_DEVELOPMENT_SOURCE_BOUND_PREVIEWS_NO_ACCEPTANCE','source_modules_pinned':162,'uniform_development_modules':20,'all_native_AST_text_and_tails_exactly_conserved':True,'all_block_exact_source_byte_spans_hashes_verified':True,'actual_nonblank_content_text_tail_pieces_checked_for_presence':checked,'missing_content_pieces':misses,'paragraphs_in_sample':paragraphs,'explicit_missing_questions':questions,'empty_visible_reference_markers':emptyrefs,'glossary_definition_boundaries':glossary,'block_kind_counts':dict(kinds),'module_hold_counts':dict(holds),'actual_list_term_boundary_regression_passed':True,'role':'All20development; never acceptance','token_counts':'PENDING: preview diagnostics are not eligible training prose','new_admitted_documents':0,'new_admitted_tokens':0}
(D/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n');index=['# OpenStax development previews','', 'All 20 modules are DEVELOPMENT only. Bracketed references and media are editorial review diagnostics. Original XML/AST is authoritative. No admission or acceptance.','']
for x in receipt['selected_module_results']:
 mid=x['module_ID'];index+=['- ['+mid+' — '+x['title']+']('+str(D/(mid+'.html'))+') | [text]('+str(D/(mid+'.txt'))+') | [source provenance, node paths and holds]('+str(D/(mid+'.json'))+')']
(D/'REVIEW_INDEX.md').write_text('\n'.join(index)+'\n');manifest={'preparation_SHA256':{p.name:h(p) for p in P.iterdir() if p.is_file()},'outputs_SHA256':{p.name:h(p) for p in D.iterdir() if p.is_file()}};(D/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');assert sum(p.stat().st_size for p in D.rglob('*') if p.is_file())<100000000;print(json.dumps({'summary':summary,'manifest_SHA256':h(D/'manifest.json'),'frozen_profile_SHA256':h(P/'frozen-profile.json'),'output_bytes':sum(p.stat().st_size for p in D.rglob('*') if p.is_file())}))
