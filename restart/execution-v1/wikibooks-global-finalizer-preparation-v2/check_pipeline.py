"""Synthetic internal frames only; no corpus processing."""
import tempfile,pathlib,sqlite3,json
from unittest.mock import patch
import finalize as f
checks=[]
def pin(p):return {'path':str(p),'sha256':f.sha(p)}
with tempfile.TemporaryDirectory() as td:
 base=pathlib.Path(td);intake=base/'m2-intake';intake.mkdir();canonical=intake/'canonical.sqlite3';c=sqlite3.connect(canonical);c.execute('create table candidates(source_ordinal integer primary key,data text)');shards=[];texts=['a'*80+'\n\n'+'b'*80,'a'*80]
 for i,text in enumerate(texts,1):
  title='Book/Print' if i==1 else 'Book/Chapter/Section';r={'page_id':i,'revision_id':i+10,'record_sha256':'record-'+str(i),'html_sha256':'html-'+str(i),'wikitext_sha256':'wiki-'+str(i),'title':title,'url':'https://fixture.invalid/'+str(i),'license_original_metadata':[{'fixture':'notactuallicense'}],'archive_sha256':'syntheticarchive','line':i,'member_ordinal':1,'training_admitted':False,'text':text,'extracted_text_sha256':f.digest(text.encode()),'text_unicode_characters':len(text),'text_UTF8_bytes':len(text.encode()),'structural_holds':[],'prior_v3_holds':[],'family_id':'shared-historical-alias'};c.execute('insert into candidates values (?,?)',(i,json.dumps(r)))
  source=intake/('source-'+str(i)+'.sqlite3');d=sqlite3.connect(source);d.executescript('create table rendered(source_ordinal integer primary key,page_id integer,revision_id integer,family text,data text);create table blocks(source_ordinal integer,ordinal integer,kind text,hash text,characters integer,start integer,end integer);');d.execute('insert into rendered values (?,?,?,?,?)',(i,i,i+10,'old-unreconciled',json.dumps(r)));start=0
  for n,block in enumerate(text.split('\n\n')):d.execute('insert into blocks values (?,?,?,?,?,?,?)',(i,n,'p',f.digest(block.encode()),len(block),start,start+len(block)));start+=len(block)+2
  d.commit();d.close();shards.append(pin(source))
 c.commit();c.close();identity=intake/'identity.json';identity.write_text('{"synthetic_fixture":true}');recipe=intake/'recipe.json';recipe.write_text(json.dumps({'status':'PARENT_FROZEN_COMPLETE_RENDER_INPUTS_NO_ADMISSION','oversize_identity_reconciliation_complete':True,'source_frame_complete_and_hash_verified':True,'expected_candidate_count':2,'shards':shards,'canonical':pin(canonical),'identity_reconciliation_receipt':pin(identity)}));before=[f.sha(pathlib.Path(s['path'])) for s in shards]
 with patch.object(f,'BASE',base),patch.object(f,'EXPECTED_CANDIDATES',2),patch.object(f,'EXPECTED_CANONICAL_SHA',f.sha(canonical)):f.run(recipe,intake/'complete')
 result=json.loads((intake/'complete/result.json').read_text());assert result['status']=='COMPLETE_GLOBAL_STRUCTURAL_RECONCILIATION_PROVISIONAL_NO_ADMISSION' and result['stats']['rows']==2 and result['stats']['finalized_rows']==2;checks.append('synthetic_full_pipeline_complete_exact_union')
 d=sqlite3.connect(intake/'complete/finalized.sqlite3');assert json.loads(d.execute('select holds from final_pages where source_ordinal=1').fetchone()[0])==['substantive_block_duplicates_canonical_chapter'];checks.append('global_common_family_override_and_deepest_ownership');assert d.execute('select distinct family from pages').fetchall()==[('shared-historical-alias',)];checks.append('effective_alias_family_used');assert 'text' not in [r[1] for r in d.execute('pragma table_info(pages)')];checks.append('no_duplicate_fulltexts_or_HTML_output');d.close();assert [f.sha(pathlib.Path(s['path'])) for s in shards]==before;checks.append('all_original_input_bytes_unchanged')
 bad=json.loads(recipe.read_text());bad['shards']=shards[:1];bad_recipe=intake/'incomplete-recipe.json';bad_recipe.write_text(json.dumps(bad))
 with patch.object(f,'BASE',base),patch.object(f,'EXPECTED_CANDIDATES',2),patch.object(f,'EXPECTED_CANONICAL_SHA',f.sha(canonical)):
  try:f.run(bad_recipe,intake/'incomplete')
  except RuntimeError as e:assert str(e)=='incomplete_effective_canonical_union'
  else:raise AssertionError('incomplete union accepted')
 assert json.loads((intake/'incomplete/result.json').read_text())['status']=='PARTIAL_GLOBAL_RECONCILIATION_NO_ADMISSION';checks.append('incomplete_union_failclosed_with_receipt')

 # Approved recipe digest must bind the exact parsed buffer and remain fixed.
 with patch.object(f,'BASE',base),patch.object(f,'EXPECTED_CANDIDATES',2),patch.object(f,'EXPECTED_CANONICAL_SHA',f.sha(canonical)):
  try:f.run(recipe,intake/'wrong-digest',expected_recipe_sha='0'*64)
  except RuntimeError as e:assert str(e)=='parent_reviewed_recipe_digest_mismatch'
  else:raise AssertionError('wrong recipe digest')
 assert not (intake/'wrong-digest').exists();checks.append('wrong_recipe_digest_before_output')
 original_resolve=f.resolve
 def change_recipe(d,check):
  count=original_resolve(d,check);recipe.write_text(recipe.read_text()+' ');return count
 with patch.object(f,'BASE',base),patch.object(f,'EXPECTED_CANDIDATES',2),patch.object(f,'EXPECTED_CANONICAL_SHA',f.sha(canonical)),patch.object(f,'resolve',side_effect=change_recipe):
  try:f.run(recipe,intake/'changed-recipe',expected_recipe_sha=f.sha(recipe))
  except RuntimeError as e:assert str(e)=='parent_reviewed_recipe_changed_during_run'
  else:raise AssertionError('changed recipe accepted')
 assert json.loads((intake/'changed-recipe/result.json').read_text())['status']=='PARTIAL_GLOBAL_RECONCILIATION_NO_ADMISSION';checks.append('recipe_change_during_run_prevents_completion')
print(json.dumps({'passed':len(checks),'checks':checks},indent=2))
