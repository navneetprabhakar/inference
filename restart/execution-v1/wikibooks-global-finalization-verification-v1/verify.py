"""Independent terminal verification, immutable source match and Python ownership replay."""
import pathlib,sqlite3,json,hashlib,time,resource,sys
BASE=pathlib.Path(__file__).resolve().parents[1]
ROOT=BASE/'m2-intake/wikibooks-global-finalization-v3'
OUT=BASE/'m2-intake/wikibooks-global-finalization-v3-verification-v1'
RECIPE=BASE/'wikibooks-global-finalizer-parent-dispatch-v1/recipe.json'
RECIPE_SHA='a7ffbc92b0a8d41e4aa7ce57ff105045325cbd2f3b8119b3eedd1341cf7db2ee'

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ro(p):return sqlite3.connect('file:'+str(p.resolve())+'?mode=ro',uri=True)
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def main():
 started=clk()
 if not (ROOT/'supervisor-result.json').exists():raise RuntimeError('supervisor_not_terminal')
 supervisor=json.loads((ROOT/'supervisor-result.json').read_text());worker=json.loads((ROOT/'result.json').read_text())
 if supervisor['status']!='COMPLETE_GLOBAL_FINALIZER_NO_ADMISSION' or worker['status']!='COMPLETE_GLOBAL_STRUCTURAL_RECONCILIATION_PROVISIONAL_NO_ADMISSION':raise RuntimeError('partial_finalizer_requires_separate_recovery_review')
 if sha(RECIPE)!=RECIPE_SHA or worker['recipe_sha256']!=RECIPE_SHA:raise RuntimeError('parent_recipe_pin_changed')
 if sha(ROOT/'result.json')!=supervisor['worker_receipt_sha256']:raise RuntimeError('worker_receipt_binding')
 sourcehash=sha(ROOT/'finalized.sqlite3')
 if sourcehash!=worker['output_sha256']:raise RuntimeError('final_DB_hash_mismatch')
 recipe=json.loads(RECIPE.read_text());d=ro(ROOT/'finalized.sqlite3');c=ro(pathlib.Path(recipe['canonical']['path']));OUT.mkdir(exist_ok=False)
 def guard():
  if clk()-started>=900:raise RuntimeError('verification900sec_cap')
  rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
  if rss>=1_000_000_000:raise RuntimeError('verification1GB_RSS_cap')
  if sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())>1_000_000_000:raise RuntimeError('verification1GB_output_cap')
 if d.execute('pragma integrity_check').fetchone()[0]!='ok':raise RuntimeError('SQLite_integrity')
 seen=set();all_prior_holds=0;all_blocks=0;longblocks=0;textchars=0;UTF8bytes=0
 for item in recipe['shards']:
  path=pathlib.Path(item['path'])
  if sha(path)!=item['sha256']:raise RuntimeError('source_pin_changed')
  s=ro(path)
  for ordinal,page,rev,family,payload in s.execute('select source_ordinal,page_id,revision_id,family,data from rendered order by source_ordinal'):
   guard()
   if ordinal in seen:raise RuntimeError('duplicate_input_source_ordinal')
   seen.add(ordinal);r=json.loads(payload);canonical=json.loads(c.execute('select data from candidates where source_ordinal=?',(ordinal,)).fetchone()[0]);out=d.execute('select page_id,revision_id,family,title,depth,text_sha256,characters,utf8_bytes,holds,active from pages where source_ordinal=?',(ordinal,)).fetchone()
   prior=set(r['structural_holds'])|set(r['prior_v3_holds']);all_prior_holds+=len(prior)
   expected=(page,rev,canonical['family_id'],r['title'],r['title'].count('/'),r['extracted_text_sha256'],r['text_unicode_characters'],r['text_UTF8_bytes'],sorted(prior),1)
   actual=out[:8]+(sorted(json.loads(out[8])),out[9])
   if actual!=expected or page!=r['page_id'] or rev!=r['revision_id']:raise RuntimeError('final_page_identity_metadata_or_prior_holds_changed')
   if not prior<=set(json.loads(d.execute('select holds from final_pages where source_ordinal=?',(ordinal,)).fetchone()[0])):raise RuntimeError('prior_hold_removed')
   textchars+=r['text_unicode_characters'];UTF8bytes+=r['text_UTF8_bytes'];expected_long=[]
   for i,h,n in s.execute('select ordinal,hash,characters from blocks where source_ordinal=? order by ordinal',(ordinal,)):
    all_blocks+=1
    if n>=80:expected_long.append((i,bytes.fromhex(h),n));longblocks+=1
   actual_long=list(d.execute('select ordinal,hash,characters from blocks where source_ordinal=? order by ordinal',(ordinal,)))
   if actual_long!=expected_long:raise RuntimeError('substantive_block_representation_or_ordinals_changed')
   if d.execute('select count(*) from blocks where source_ordinal=? and family is not null',(ordinal,)).fetchone()[0]:raise RuntimeError('unexpected_repeated_family_payload')
  s.close()
 if len(seen)!=89758 or d.execute('select count(*) from pages').fetchone()[0]!=89758 or d.execute('select count(*) from final_pages').fetchone()[0]!=89758:raise RuntimeError('incomplete_page_union')
 if all_blocks!=4008512 or longblocks!=1607248 or d.execute('select count(*) from blocks').fetchone()[0]!=longblocks:raise RuntimeError('block_count_drift')
 # Independent Python maps replay greedy canonical ownership; no output writes.
 ownership={};exact={};holds_hist={};final_free=0;replayed=0;overlap_rows=0;exact_held=0;block_held=0;candidate_chars=0;candidate_UTF8bytes=0
 for ordinal,page,family,title,depth,tsha,chars,bytes_,rawholds in d.execute('select source_ordinal,page_id,family,title,depth,text_sha256,characters,utf8_bytes,holds from pages order by depth desc,title collate binary,page_id,source_ordinal'):
  guard();prior=set(json.loads(rawholds));want=set(prior);want_overlaps=[];want_exact=None;blocks=list(d.execute('select ordinal,hash from blocks where source_ordinal=? order by ordinal',(ordinal,)))
  if not prior:
   if tsha in exact:want_exact=exact[tsha];want.add('exact_text_duplicate_global');exact_held+=1
   else:
    want_overlaps=[(i,h,ownership[(family,h)]) for i,h in blocks if (family,h) in ownership]
    if want_overlaps:want.add('substantive_block_duplicates_canonical_chapter');block_held+=1
    else:
     exact[tsha]=ordinal
     for i,h in blocks:ownership.setdefault((family,h),ordinal)
  actual=d.execute('select holds,exact_owner from final_pages where source_ordinal=?',(ordinal,)).fetchone();actual_overlaps=list(d.execute('select block_ordinal,hash,owner_source_ordinal from overlaps where source_ordinal=? order by block_ordinal',(ordinal,)))
  if set(json.loads(actual[0]))!=want or actual[1]!=want_exact or actual_overlaps!=want_overlaps:raise RuntimeError('independent_greedy_replay_mismatch')
  if not want:final_free+=1;candidate_chars+=chars;candidate_UTF8bytes+=bytes_
  for h in want:holds_hist[h]=holds_hist.get(h,0)+1
  replayed+=1;overlap_rows+=len(want_overlaps)
 if {(family,h):o for family,h,o in d.execute('select family,hash,source_ordinal from owners')}!=ownership:raise RuntimeError('global_owner_mapping_mismatch')
 if {h:o for h,o in d.execute('select hash,source_ordinal from exact_owners')}!=exact:raise RuntimeError('global_exact_owner_mapping_mismatch')
 # Independent aggregate recomputation, checked bidirectionally with EXCEPT.
 exact_sql='select text_sha256,count(*),count(distinct family) from pages group by text_sha256 having count(*)>1'
 cross_sql='select b.hash,count(*),count(distinct p.family) from blocks b join pages p on p.source_ordinal=b.source_ordinal group by b.hash having count(distinct p.family)>1'
 for table,query in [('exact_duplicate_groups',exact_sql),('cross_family_block_groups',cross_sql)]:
  guard()
  if d.execute('select count(*) from (select * from '+table+' except '+query+')').fetchone()[0] or d.execute('select count(*) from ('+query+' except select * from '+table+')').fetchone()[0]:raise RuntimeError('group_aggregate_mismatch:'+table)
 groupcounts={table:d.execute('select count(*) from '+table).fetchone()[0] for table in ['owners','exact_owners','overlaps','exact_duplicate_groups','cross_family_block_groups']}
 d.close();c.close()
 if sha(ROOT/'finalized.sqlite3')!=sourcehash:raise RuntimeError('final_output_mutated_during_readonly_verification')
 for item in recipe['shards']+[recipe['canonical'],recipe['identity_reconciliation_receipt']]:
  guard()
  if sha(pathlib.Path(item['path']))!=item['sha256']:raise RuntimeError('original_input_mutated')
 result={'status':'INDEPENDENTLY_VERIFIED_COMPLETE_GLOBAL_STRUCTURAL_RECONCILIATION_NO_ADMISSION','parent_recipe_sha256':RECIPE_SHA,'final_database_sha256':sourcehash,'worker_receipt_sha256':sha(ROOT/'result.json'),'supervisor_receipt_sha256':sha(ROOT/'supervisor-result.json'),'pages':len(seen),'all_immutable_source_blocks':all_blocks,'substantive_global_blocks':longblocks,'all_prior_hold_assignments_preserved':all_prior_holds,'canonical_greedy_pages_replayed':replayed,'global_owner_and_exact_owner_maps_match':True,'overlap_rows_replayed':overlap_rows,'new_exact_duplicate_held_pages':exact_held,'new_substantive_overlap_held_pages':block_held,'group_counts':groupcounts,'post_structural_duplicate_candidate_documents':final_free,'post_structural_duplicate_candidate_rendered_characters':candidate_chars,'post_structural_duplicate_candidate_UTF8_bytes':candidate_UTF8bytes,'full_frame_rendered_characters':textchars,'full_frame_UTF8_bytes':UTF8bytes,'hold_incidence':holds_hist,'not_usable_or_admitted_counts':True,'remaining_gates':['language','source/captured-text rights and third-party exceptions','semantic/factual/readability filter repair and fresh representative review','cross-source deduplication and leakage','family split freeze'],'new_admitted_documents':0,'new_admitted_tokens':0,'all_input_shards_unchanged':True,'elapsed_seconds':clk()-started}
 (OUT/'verification.json').write_text(json.dumps(result,sort_keys=True,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
