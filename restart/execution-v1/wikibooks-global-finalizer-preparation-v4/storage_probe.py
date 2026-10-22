"""Metadata-only capacity probe, NOT a finalizer/quality sample.

Requires the independently verified terminal full render frame. Indexes a bounded
20,000 substantive-block storage fixture; never runs resolve() on real data.
"""
import argparse,pathlib,json,sqlite3,tempfile,shutil,time
import finalize as f
HERE=pathlib.Path(__file__).resolve().parent

def run(verification,output):
 started=f.clk();v=json.loads(verification.read_text())
 if v['status']!='COMPLETE_VERIFIED_CANONICAL_RENDER_UNION_PROVISIONAL_NO_ADMISSION' or v['combined_rows']!=89758:raise RuntimeError('complete_verified_frame_required')
 if output.exists():raise RuntimeError('existing_probe_output')
 output.mkdir();db=sqlite3.connect(output/'capacity-fixture.sqlite3');f.schema(db);counts=[];sample=0;families=set()
 for i,item in enumerate(v['verified_input_databases']):
  path=pathlib.Path(item['path'])
  if f.sha(path)!=item['sha256']:raise RuntimeError('frozen_input_pin_changed')
  source=f.ro(path);pages=source.execute('select count(*) from rendered').fetchone()[0];allblocks=source.execute('select count(*) from blocks').fetchone()[0];longblocks=source.execute('select count(*) from blocks where characters>=80').fetchone()[0];counts.append({'path':str(path),'sha256':item['sha256'],'pages':pages,'all_blocks':allblocks,'substantive_blocks':longblocks})
  if i<4:
   for ordinal,index,h,chars in source.execute('select source_ordinal,ordinal,hash,characters from blocks where characters>=80 order by source_ordinal,ordinal limit 5000'):
    if f.clk()-started>180:raise RuntimeError('probe180second_bound')
    if not db.execute('select 1 from pages where source_ordinal=?',(ordinal,)).fetchone():
     page,rev,family,payload=source.execute('select page_id,revision_id,family,data from rendered where source_ordinal=?',(ordinal,)).fetchone();r=json.loads(payload);fid=f.intern_family(db,family);families.add(family);db.execute('insert into pages values (?,?,?,?,?,?,?,?,?,?,?)',(ordinal,page,rev,fid,r['title'],r['title'].count('/'),bytes.fromhex(r['extracted_text_sha256']),r['text_unicode_characters'],r['text_UTF8_bytes'],json.dumps(r['structural_holds']),1));db.execute('insert into final_pages values (?,?,?)',(ordinal,json.dumps(r['structural_holds']),None));db.execute('insert or ignore into exact_owners values (?,?)',(bytes.fromhex(r['extracted_text_sha256']),ordinal));db.execute('insert or ignore into exact_duplicate_groups values (?,?,?)',(bytes.fromhex(r['extracted_text_sha256']),2,2))
    family=db.execute('select family from pages where source_ordinal=?',(ordinal,)).fetchone()[0];bh=bytes.fromhex(h);assert bh.hex()==h;db.execute('insert into blocks values (?,?,?,?)',(ordinal,index,bh,chars));db.execute('insert or ignore into owners values (?,?,?)',(family,bh,ordinal))
    # Conservative artificial maximum: simultaneously allocate ownership,
    # overlap and group metadata. These are capacity fixtures, not true labels.
    db.execute('insert into overlaps values (?,?,?,?)',(ordinal,index,bh,ordinal));db.execute('insert or ignore into cross_family_block_groups values (?,?,?)',(bh,2,2));sample+=1
  source.close()
 db.commit();db.execute('pragma optimize');db.close();bytes_=f.size(output);total_long=sum(r['substantive_blocks'] for r in counts);total_all=sum(r['all_blocks'] for r in counts);total_pages=sum(r['pages'] for r in counts)
 if total_pages!=89758 or sample!=20000 or bytes_>32_000_000:raise RuntimeError('probe_frame_or_output_bound')
 per=bytes_/sample;projection=per*total_long;receipt={'status':'BOUNDED_ACTUAL_STORAGE_PROBE_NOT_FINALIZATION_OR_QUALITY_SAMPLE','input_verification_sha256':f.sha(verification),'sample':'First5000substantiveblocks from each of the four immutable prior verified shards. No content acceptance or representative-quality inference.','input_counts':counts,'actual_complete_frame_pages':total_pages,'actual_complete_frame_all_blocks':total_all,'actual_complete_frame_substantive_blocks':total_long,'fixture_substantive_blocks':sample,'actual_SQLite_bytes':bytes_,'bytes_per_sample_substantive_block_including_tables':per,'linear_conservative_fixture_projection_bytes':projection,'main_database_hard_cap_bytes':409600000,'headroom_bytes':409600000-projection,'capacity_fixture_artificial_allocations':'Every sampled block simultaneously gets ownership+overlap+cross-family group records, and every sampled page gets exact-owner+exact-group+final-hold records. These intentionally overstate mutually exclusive metadata; they are not real dispositions.','projection_limitations':'Capacity planning only. Family/title/hold lengths and B-tree occupancy may vary. The exact409.6MBhard cap still stops the real job; no silent cap increase or completion guarantee.','all_input_text_and_HTML_unchanged':True,'no_real_resolve_called':True,'elapsed_seconds':f.clk()-started,'new_admitted_documents':0,'new_admitted_tokens':0}
 (output/'projection.json').write_text(json.dumps(receipt,sort_keys=True,indent=2)+'\n');print(json.dumps({k:r for k,r in receipt.items() if k!='input_counts'}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--verification',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();run(a.verification,a.output)
