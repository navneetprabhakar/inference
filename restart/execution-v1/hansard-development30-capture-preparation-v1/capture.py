"""Full two-gzip fidelity capture of frozen development draws only."""
import sqlite3,json,hashlib,os
from pathlib import Path
import inventory,source_guard

def write(out,name,data,check):
 check(len(data))
 with (Path(out)/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def one(binding,frame,selected,out,read,check,known):
 conn=sqlite3.connect(Path(frame['path']).as_uri()+'?mode=ro&immutable=1',uri=True);conn.execute('PRAGMA query_only=ON');conn.execute('PRAGMA cache_size=-4096');conn.execute('PRAGMA mmap_size=0');conn.set_progress_handler(lambda:(check() or 0),10000)
 current=iter(conn.execute('SELECT * FROM records WHERE source_id=? ORDER BY ordinal',(binding['source_id'],)));captured=[];linehash=hashlib.sha256()
 def accept(ordinal,offset,n,ends,digest,raw):
  check();expected=next(current,None)
  if expected is None:raise ValueError('extra_source_row')
  record,reasons=inventory.row(binding['source_id'],ordinal,offset,n,ends,digest,raw)
  if tuple(expected)!=tuple(record):raise ValueError('full_original_frame_row_binding')
  linehash.update(json.dumps([binding['source_id'],ordinal,offset,n,int(ends),digest.hex()],separators=(',',':')).encode()+b'\n')
  item=selected.get(ordinal)
  if item is None:return
  if raw is None or digest.hex()!=item['line_SHA256'] or offset!=item['line_offset'] or n!=item['line_bytes'] or int(ends)!=item['ends_LF']:raise ValueError('selected_raw_line_identity')
  obj=json.loads(raw.decode('utf8'),object_pairs_hook=inventory.unique,parse_constant=inventory.nofloat)
  text=obj['text'].encode('utf8');sha=hashlib.sha256(text).hexdigest()
  if len(text)>976482 or len(text)!=item['text_UTF8_bytes'] or sha!=item['text_SHA256']:raise ValueError('selected_complete_text_identity_cap')
  stem=f"source-{binding['source_id']}-row-{ordinal:06d}";write(out,stem+'.source.json',raw,check);write(out,stem+'.text.utf8',text,check)
  captured.append({'source_id':binding['source_id'],'ordinal':ordinal,'raw_line_file':stem+'.source.json','raw_line_SHA256':digest.hex(),'raw_line_bytes':n,'line_offset':offset,'ends_LF':bool(ends),'text_file':stem+'.text.utf8','text_SHA256':sha,'text_UTF8_bytes':len(text),'existing_flags':expected[6],'native_subsource':expected[8],'all_rights_status':'UNCLEARED','original_metadata_all_retained':True,'original_source_id':obj['id'],'source_record_is_not_preferred_corpus_version':True,'all_rights_family_quality_language_leakage_holds_retained':True})
 lines=inventory.Lines(981231,100000,accept)
 try:
  counts=inventory.gzip_stream(read,lines.add,{'compressed_bytes':binding['bytes'],'decoded_bytes':2000000000},check);lines.finish()
  if next(current,None) is not None or lines.ordinal!=frame['rows'] or lines.total!=counts['decoded_bytes']:raise ValueError('full_frame_count_decoded_coverage')
  if counts['compressed_bytes']!=binding['bytes'] or counts['compressed_SHA256']!=binding['SHA256']:raise ValueError('full_gzip_original_SHA256')
  if linehash.hexdigest()!=frame['ordered_line_locator_SHA256']:raise ValueError('full_frame_ordered_line_digest')
  if len(captured)!=len(selected):raise ValueError('all_fixed_selected_outcomes_no_replacement')
  return {'source_id':binding['source_id'],'counts':counts,'rows':lines.ordinal,'ordered_line_locator_SHA256':linehash.hexdigest(),'captures':captured}
 finally:conn.close()

def run(profile,out,check):
 selection=json.loads(Path(profile['selection']).read_text());results=[]
 for source in profile['sources']:
  sid=source['source_id'];chosen={r['ordinal']:r for r in selection['selected_capture_occurrences'] if r['source_id']==sid};binding=source['raw'];binding={**binding,'source_id':sid}
  with source_guard.opened(binding,check) as read:
   results.append(one(binding,source['frame'],chosen,out,read,check,source['known_holds']));read.assert_custody()
  if source_guard.ident(Path(source['frame']['path']).stat())!=source['frame']['stat']:raise ValueError('frame_postflight_stat')
 captures=[r for s in results for r in s['captures']]
 if len(captures)!=selection['capture_distinct_textSHA'] or {r['text_SHA256'] for r in captures}!={r['text_SHA256'] for r in selection['draws']}:raise ValueError('draw_capture_coverage')
 if sum(r['text_UTF8_bytes']for r in captures)>30000000:raise ValueError('selected_text30MBcap')
 report={'status':'COMPLETE_FIXED30_DRAW_WHOLE_HANSARD_DEVELOPMENT_CAPTURE_NO_ADMISSION','sources':results,'draws':selection['draws'],'draws_count':30,'unique_captured_texts':len(captures),'captured_text_UTF8_bytes':sum(r['text_UTF8_bytes'] for r in captures),'capture_not_version_selection':True,'sampling_scope':'DEVELOPMENT_ONLY_NOT_FRESH_ACCEPTANCE_NO_SOURCE_QUALITY_EXTRAPOLATION','token_weighted':False,'new_admitted_documents':0,'new_admitted_tokens':0}
 write(out,'records.json',(json.dumps(report,indent=2,ensure_ascii=False)+'\n').encode(),check)
 return report
