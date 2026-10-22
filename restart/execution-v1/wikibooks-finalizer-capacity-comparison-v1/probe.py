"""Bounded v3 production-representation capacity fixture; no resolve/admission."""
import pathlib,json,sqlite3,importlib.util,argparse,time
BASE=pathlib.Path(__file__).resolve().parents[1]
p=BASE/'wikibooks-global-finalizer-preparation-v3/finalize.py';spec=importlib.util.spec_from_file_location('audited_v3',p);f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
def run(frame,out):
 start=f.clk();v=json.loads(frame.read_text())
 if v['status']!='COMPLETE_VERIFIED_CANONICAL_RENDER_UNION_PROVISIONAL_NO_ADMISSION' or v['combined_rows']!=89758:raise RuntimeError('full_verified_frame_required')
 if out.exists():raise RuntimeError('no_probe_retry')
 if f.shutil.disk_usage(out.parent).free<f.CAPS['free_floor_bytes']+f.CAPS['weights_bytes']+32_000_000:raise RuntimeError('probe_disk_weights_reservation')
 out.mkdir();d=sqlite3.connect(out/'capacity-fixture.sqlite3');f.schema(d);totals={'pages':0,'all_blocks':0,'substantive_blocks':0,'structurally_unheld_pages':0,'structurally_unheld_substantive_occurrences':0};sample=0;inputs=[]
 for source_index,item in enumerate(v['verified_input_databases']):
  path=pathlib.Path(item['path'])
  if f.sha(path)!=item['sha256']:raise RuntimeError('input_hash_changed')
  source=f.ro(path);allblocks=source.execute('select count(*) from blocks').fetchone()[0];longblocks=source.execute('select count(*) from blocks where characters>=80').fetchone()[0];totals['all_blocks']+=allblocks;totals['substantive_blocks']+=longblocks;pages=0
  for ordinal,payload in source.execute('select source_ordinal,data from rendered'):
   if f.clk()-start>180:raise RuntimeError('probe180second_cap')
   r=json.loads(payload);pages+=1
   if not (set(r['structural_holds'])|set(r['prior_v3_holds'])):
    totals['structurally_unheld_pages']+=1;totals['structurally_unheld_substantive_occurrences']+=source.execute('select count(*) from blocks where source_ordinal=? and characters>=80',(ordinal,)).fetchone()[0]
  totals['pages']+=pages;inputs.append({'path':str(path),'sha256':item['sha256'],'pages':pages,'all_blocks':allblocks,'substantive_blocks':longblocks})
  if source_index<4:
   for ordinal,index,h,chars in source.execute('select source_ordinal,ordinal,hash,characters from blocks where characters>=80 order by source_ordinal,ordinal limit 5000'):
    if not d.execute('select 1 from pages where source_ordinal=?',(ordinal,)).fetchone():
     page,rev,family,payload=source.execute('select page_id,revision_id,family,data from rendered where source_ordinal=?',(ordinal,)).fetchone();r=json.loads(payload);d.execute('insert into pages values (?,?,?,?,?,?,?,?,?,?,?)',(ordinal,page,rev,family,r['title'],r['title'].count('/'),r['extracted_text_sha256'],r['text_unicode_characters'],r['text_UTF8_bytes'],json.dumps(r['structural_holds']),1));d.execute('insert into final_pages values (?,?,?)',(ordinal,json.dumps(r['structural_holds']),None));d.execute('insert or ignore into exact_owners values (?,?)',(r['extracted_text_sha256'],ordinal));d.execute('insert or ignore into exact_duplicate_groups values (?,?,?)',(r['extracted_text_sha256'],2,2))
    family=d.execute('select family from pages where source_ordinal=?',(ordinal,)).fetchone()[0];bh=bytes.fromhex(h);assert bh.hex()==h;d.execute('insert into blocks values (?,?,?,?,?)',(ordinal,index,None,bh,chars));d.execute('insert or ignore into owners values (?,?,?)',(family,bh,ordinal));d.execute('insert into overlaps values (?,?,?,?)',(ordinal,index,bh,ordinal));d.execute('insert or ignore into cross_family_block_groups values (?,?,?)',(bh,2,2));sample+=1
  source.close()
 d.commit();stats={n:b for n,b in d.execute('select name,sum(pgsize) from dbstat group by name')};rowcounts={t:d.execute('select count(*) from '+t).fetchone()[0] for t in ['pages','blocks','owners','overlaps','final_pages','exact_owners','exact_duplicate_groups','cross_family_block_groups']};d.close()
 if sample!=20000 or totals['pages']!=89758 or f.size(out)>32_000_000:raise RuntimeError('probe_expected_size_bound')
 # Sum table and automatic-index bytes for each logical component. Explicit
 # page_order/block_hash indexes belong to pages/blocks respectively.
 def component(table):return sum(b for name,b in stats.items() if name==table or name.startswith('sqlite_autoindex_'+table+'_') or (table=='pages' and name=='page_order') or (table=='blocks' and name=='block_hash'))
 per={t:component(t)/max(1,rowcounts[t]) for t in rowcounts};P=totals['pages'];E=totals['structurally_unheld_pages'];M=totals['substantive_blocks'];Q=totals['structurally_unheld_substantive_occurrences']
 projection={'pages_and_order_index':per['pages']*P,'substantive_blocks_and_hash_index':per['blocks']*M,'owners_or_overlaps_max_per_eligible_occurrence':max(per['owners'],per['overlaps'])*Q,'final_pages_plus128extra_bytes_each':(per['final_pages']+128)*P,'exact_owners_upper_bound':per['exact_owners']*E,'exact_duplicate_groups_upper_bound':per['exact_duplicate_groups']*(P//2),'cross_family_groups_upper_bound':per['cross_family_block_groups']*(M//2),'fixed_page_reserve':1_048_576};projected=sum(projection.values())
 r={'status':'ACTUAL_V3_PRODUCTION_REPRESENTATION_CAPACITY_FIXTURE_NOT_FINALIZER','schema_sha256':f.sha(p),'frame_verification_sha256':f.sha(frame),'full_frame_counts':totals,'bounded_fixture_substantive_blocks':sample,'fixture_SQLite_bytes':f.size(out),'dbstat_bytes':stats,'fixture_row_counts':rowcounts,'component_bytes_per_fixture_row':per,'capacity_projection_components':projection,'capacity_projection_bytes':projected,'main_database_hard_cap_bytes':409600000,'projected_headroom_bytes':409600000-projected,'method':'Exactly v3 ingestion: only>=80character blocks, NULL block family,32byteBLOB block hashes; v3 family strings retained for pages/owners. Artificial ownership/overlap/group rows estimate component storage only; resolve() is never called. Global eligible counts come only from preserved structural/prior holds. Owners+overlaps rows cannot exceed eligible substantive occurrences, so use maximum per-row cost rather than summing both. Cross-family groups<=M/2 and exactduplicate groups<=P/2.128extra bytes per final page and1MiB fixed overhead reserved.','limitations':'Empirical SQLite capacity planning, not a byte-exact worst-case proof or actual dispositions. B-tree occupancy and strings may differ.409.6MBmain/1GBoutput/900s/RSS caps remain hard stops; no increase, dispatch, admission or quality inference.','input_shards_unchanged':all(f.sha(pathlib.Path(i['path']))==i['sha256'] for i in inputs),'input_pins':inputs,'elapsed_seconds':f.clk()-start,'new_admitted_documents':0,'new_admitted_tokens':0};(out/'projection.json').write_text(json.dumps(r,sort_keys=True,indent=2)+'\n');print(json.dumps({k:x for k,x in r.items() if k not in ['input_pins','dbstat_bytes']}))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--frame',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True);r=a.parse_args();run(r.frame,r.output)
