"""Closed metadata selection only: no original text/gzip reads or classifier calls."""
import hashlib,json,os,sqlite3
from pathlib import Path
import adapter,select_core,source_guard

def require(v,s):
 if not v:raise ValueError(s)
def ro(item):
 p=Path(item['path']);require(not p.is_symlink() and source_guard.ident(p.stat())==item['stat'],'metadata_custody')
 d=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)
 for x in ['query_only=ON','cache_size=-4096','mmap_size=0']:d.execute('PRAGMA '+x)
 return d

def run(profile,out,check):
 items=[profile['candidate_frame'],profile['family_frame']]+[s['frame'] for s in profile['sources']]
 opened=[]
 try:
  for item in items:
   d=ro(item);d.set_progress_handler(lambda:(check() or 0),10000);opened.append(d)
  db,family=opened[:2];frames={s['source_id']:d for s,d in zip(profile['sources'],opened[2:])}
  expected=profile['expected_fresh'];actual=list(db.execute('SELECT count(*),sum(M1_content_tokens),sum(UTF8_bytes) FROM texts WHERE fresh_population=1').fetchone());require(actual==expected,'exact_verified_fresh_population')
  require(db.execute('SELECT count(*) FROM texts WHERE fresh_population=1 AND (candidate!=1 OR language_pass!=1 OR explicit_known_hold!=0 OR generic_mask!=0 OR queue_mask!=0 OR prior_reviewed_or_held!=0 OR M1_content_tokens<=0)').fetchone()==(0,),'strict_fresh_frame_flags')
  def context(s,o):
   r=family.execute('SELECT r.lead_status,r.existing_flags,r.identity_holds,a.value,b.value,c.value,d.value FROM rows r LEFT JOIN strings a ON a.string_id=r.id_id LEFT JOIN strings b ON b.string_id=r.url_id LEFT JOIN strings c ON c.string_id=r.book_url_id LEFT JOIN strings d ON d.string_id=r.lead_root_id WHERE r.source_id=? AND r.ordinal=?',(s,o)).fetchone();require(r is not None,'context_identity')
   h=db.execute('SELECT text_SHA256,source_flags,family_uncertainty,occurrences FROM texts WHERE first_source=? AND first_ordinal=?',(s,o)).fetchone();require(h is not None,'canonical_capture_metadata')
   aliases=[]
   for a in db.execute('SELECT source_id,ordinal,identity_holds,lead_status,lead_root_id FROM occurrences WHERE text_SHA256=? ORDER BY source_id,ordinal',(h[0],)):
    check();aliases.append({'source_id':a[0],'ordinal':a[1],'identity_holds':a[2],'lead_status':a[3],'lead_root_id':a[4]})
   require(len(aliases)==h[3],'all_raw_aliases_context')
   return {**dict(zip(['lead_status','source_flags','prior_identity_hold_bits','source_id_URL','source_url','book_url','derived_book_root_LEAD_NOT_verified_family'],r)),'all_copy_source_flags':h[1],'family_uncertainty':h[2],'raw_occurrences':aliases,'verified_work_family':False}
  selection=select_core.select(db,profile['sampling_seed'],200,check,context)
  def lookup(s,o):
   t=db.execute('SELECT t.text_SHA256,t.UTF8_bytes,t.M1_content_tokens,t.candidate,t.fresh_population,t.first_source,t.first_ordinal,o.line_offset,o.line_bytes,o.line_SHA256,o.source_flags,o.identity_holds,o.lead_status FROM texts t JOIN occurrences o ON o.text_SHA256=t.text_SHA256 AND o.source_id=t.first_source AND o.ordinal=t.first_ordinal WHERE t.first_source=? AND t.first_ordinal=?',(s,o)).fetchall();require(len(t)==1 and t[0][3:7]==(1,1,s,o),'selected_fresh_canonical');t=t[0]
   r=frames[s].execute('SELECT ordinal,line_offset,line_bytes,ends_LF,line_SHA256,flags,text_SHA256,text_UTF8_bytes FROM records WHERE ordinal=?',(o,)).fetchone();require(r is not None and (r[1],r[2],r[4],r[5],r[6],r[7])==(t[7],t[8],t[9],t[10],t[0],t[1]),'original_frame_locator_hash')
   return {'source_id':s,'ordinal':o,'line_offset':r[1],'line_bytes':r[2],'ends_LF':r[3],'line_SHA256':r[4].hex(),'text_SHA256':r[6].hex(),'text_UTF8_bytes':r[7],'existing_flags':r[5],'identity_holds':t[11],'lead_status':t[12]}
  derived=adapter.adapt(selection,lookup)
  stats=derived['stats'];capture_cost=stats['text_UTF8_bytes']+stats['original_JSON_bytes']+16000000
  report={'status':'COMPLETE_REPAIRED_FRESH400_SELECTION_METADATA_ONLY_NO_ADMISSION','fresh_population':actual,'ordered_frame_SHA256':selection['ordered_fresh_frame_SHA256'],'seed':profile['sampling_seed'],'draw_roles':400,'stats':stats,'capture_proposed_output_bytes':128000000,'capture_minimum_reserved_cost_bytes':capture_cost,'capture_resource_disposition':'WITHIN_PROPOSED_BOUND_PENDING_PARENT_PROFILE_REVIEW' if capture_cost<=128000000 else 'HOLD_CAPTURE_RESOURCE_NO_REROLL','policy_changed':False,'source_body_reads':0,'new_admitted_documents':0,'new_admitted_tokens':0,'quality_acceptance_not_final_M2_rights_release':True}
  for name,obj in [('fresh-review-selection.json',selection),('capture-selection.json',derived),('capture-sizing.json',report)]:
   data=(json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode();require(len(data)<=4000000,'per_metadata_file_cap');check(len(data))
   with (Path(out)/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  for item in items:require(source_guard.ident(Path(item['path']).stat())==item['stat'],'metadata_unchanged_postflight')
  return report
 finally:
  for d in opened:d.close()
