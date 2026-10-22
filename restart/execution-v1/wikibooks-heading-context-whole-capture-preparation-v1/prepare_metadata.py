"""Metadata-only outer identity and size binding, no rendered.data/text/HTML reads."""
import pathlib,json,hashlib,sqlite3
R=pathlib.Path('/Users/navneetprabhakar/Documents/git/image/inference/restart/execution-v1');P=pathlib.Path(__file__).resolve().parent;I=R/'m2-intake';S=I/'wikibooks-heading-context-development-selection-v1/selection.json';H='6ddf08ae24cd3f4fb39e8ccaf7acf66da20003c5f4efd8cbbc7568cb9533987b'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def j(p):return json.loads(p.read_text())
def ro(p):
 c=sqlite3.connect(p.resolve().as_uri()+'?mode=ro&immutable=1',uri=True);c.row_factory=sqlite3.Row;return c
assert h(S)==H
selection=j(S);triageprep=R/'wikibooks-rendered-heading-triage-executor-preparation-v1';tp=j(triageprep/'profile.json');tpins=j(triageprep/'code-pins.json')['SHA256'];resultpath=I/'wikibooks-current-candidate-heading-metadata-v1/result.json';result=j(resultpath)
assert result['status']=='COMPLETE_METADATA_FEATURE_INVENTORY_NOT_FILTER_OR_ADMISSION' and result['feature_file_SHA256']==selection['source_feature_SHA256'] and result['all_input_pins_rechecked_unchanged']
selected=[];by={r['source_ordinal']:r for r in selection['selected']};assert len(by)==20
with ro(pathlib.Path(tp['screening'])) as c:
 for ordinal,r in by.items():
  screen=dict(c.execute('select source_ordinal,page_id,revision_id,family,title,text_sha256,characters,utf8_bytes,content_tokens,tokens_plus_one_EOS,scored_lines,skipped_chunks,language_pass,minimum_english_probability,known_discovery_hold,holds from docs where source_ordinal=?',(ordinal,)).fetchone())
  assert (screen['page_id'],screen['revision_id'],screen['family'],screen['text_sha256'],screen['content_tokens'])==(r['page_id'],r['revision_id'],r['family'],r['text_sha256'],r['M1_tokens_stored']) and screen['language_pass']==1
  selected.append({**screen,'frozen_development_selection':r})
with ro(pathlib.Path(tp['finalizer'])) as c:
 for r in selected:
  ordinal=r['source_ordinal'];page=dict(c.execute('select source_ordinal,page_id,revision_id,family,title,depth,text_sha256,characters,utf8_bytes,holds,active from pages where source_ordinal=?',(ordinal,)).fetchone());role=dict(c.execute('select source_ordinal,holds,exact_owner from final_pages where source_ordinal=?',(ordinal,)).fetchone())
  assert all(page[k]==r[k] for k in ['page_id','revision_id','family','title','text_sha256','characters','utf8_bytes']) and page['active']==1 and json.loads(page['holds'])==[] and json.loads(role['holds'])==[]
  r['expected_finalizer_page']=page;r['expected_finalizer_role']=role
owners={};ordinals=list(by)
for store in tp['stores']:
 with ro(pathlib.Path(store['path'])) as c:
  rows=c.execute('select source_ordinal,page_id,revision_id,family from rendered where source_ordinal in ('+','.join('?'*20)+')',ordinals)
  for row in rows:
   x=dict(row);ordinal=x['source_ordinal'];assert ordinal not in owners
   expected=by[ordinal];assert all(x[k]==expected[k] for k in ['page_id','revision_id','family'])
   owners[ordinal]={'path':store['path'],'SHA256':store['SHA256'],'outer_identity':x}
assert set(owners)==set(by)
for r in selected:r['source_shard']=owners[r['source_ordinal']]
source_pins={p:tpins[p] for p in [tp['screening'],tp['finalizer']]+[s['path'] for s in tp['stores']]}
assert all(source_pins[s['path']]==s['SHA256'] for s in tp['stores'])
proposal={'status':'PREPARED_EXACT20_METADATA_ONLY_NO_BODY_READ_NOT_ACCEPTANCE','original_selection':{'path':str(S),'SHA256':H},'selected':selected,'strata':selection['selection_counts'],'exact_documents':20,'exact_UTF8_bytes':sum(r['utf8_bytes'] for r in selected),'max_document_UTF8_bytes':max(r['utf8_bytes'] for r in selected),'stored_M1_content_tokens':sum(r['content_tokens'] for r in selected),'all12canonical_owner_paths_bound':tp['stores'],'source_DB_SHA256_inherited_completed_triage_not_rehashed_in_preparation':source_pins,'source_query_scope':['SELECT explicit docs metadata columns by source_ordinal','SELECT explicit pages/final_pages metadata columns by source_ordinal','SELECT source_ordinal,page_id,revision_id,family from rendered by20ordinalIN'], 'rendered_data_text_HTML_block_body_queries':0,'source_text_reads':0,'no_rendering_tokenizer_language_model_training_network':True,'counts_or_policy_or_admission_changes':0,'hold_not_truncate_above_2MB':True}
(P/'selected.metadata.json').write_text(json.dumps(proposal,indent=2)+'\n')
evidence={str(s):h(s) for s in [S,triageprep/'profile.json',triageprep/'code-pins.json',triageprep/'readiness.json',resultpath,I/'wikibooks-current-candidate-heading-metadata-v1/supervisor.json',R/'wikibooks-heading-terminal-independent-verification-v1/verification.json',R/'wikibooks-semantic-provenance-preparation-v1/canonical-stores.json']}
(P/'evidence-pins.json').write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps({k:proposal[k] for k in ['exact_documents','exact_UTF8_bytes','max_document_UTF8_bytes','stored_M1_content_tokens']}))
