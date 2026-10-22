"""Audited whole-source reader plus fixed fresh400 all-original capture adapter."""
import hashlib,json,os
from pathlib import Path
import retained_capture,source_guard,adapter

def run(profile,out,check):
 selection=json.loads(Path(profile['selection']).read_text());adapter.verify_derived(selection);results=[]
 for source in profile['sources']:
  sid=source['source_id'];chosen={r['ordinal']:r for r in selection['selected_capture_occurrences'] if r['source_id']==sid}
  if len(chosen)!=sum(r['source_id']==sid for r in selection['selected_capture_occurrences']):raise ValueError('duplicate_selected_occurrence')
  with source_guard.opened(source['raw'],check) as read:
   results.append(retained_capture.one({**source['raw'],'source_id':sid},source['frame'],chosen,out,read,check,source['known_holds']));read.assert_custody()
  if source_guard.ident(Path(source['frame']['path']).stat())!=source['frame']['stat']:raise ValueError('frame_postflight_stat')
 captures=[r for s in results for r in s['captures']];expected=selection['selected_capture_occurrences']
 if len(captures)!=len(expected) or {r['text_SHA256'] for r in captures}!={r['text_SHA256'] for r in expected}:raise ValueError('all_unique_capture_hash_outcomes')
 # Independently reconstruct captured text directly from preserved originalJSON; no rewriting.
 byhash={r['text_SHA256']:r for r in captures}
 for item in expected:
  got=byhash[item['text_SHA256']];raw=(Path(out)/got['raw_line_file']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=item['line_SHA256']:raise ValueError('saved_full_original_JSON_SHA')
  obj=json.loads(raw.decode('utf8'));text=obj['text'].encode('utf8');saved=(Path(out)/got['text_file']).read_bytes()
  if text!=saved or hashlib.sha256(saved).hexdigest()!=item['text_SHA256'] or len(saved)!=item['text_UTF8_bytes']:raise ValueError('saved_original_JSON_text_exact_inverse')
  got['draw_roles']=item['draw_roles'];got['existing_M1_content_tokens']=item['M1_content_tokens']
 stats=selection['stats']
 if sum(r['text_UTF8_bytes'] for r in captures)!=stats['text_UTF8_bytes'] or sum(r['raw_line_bytes'] for r in captures)!=stats['original_JSON_bytes']:raise ValueError('all_capture_costs_exact')
 report={'status':'COMPLETE_FRESH400_DRAW_WHOLE_ORIGINAL_PRESSBOOKS_CAPTURE_NO_ADMISSION','sources':results,'draws':selection['draws'],'draw_count':400,'unique_captured_raw_SHA':len(captures),'captured_text_UTF8_bytes':stats['text_UTF8_bytes'],'captured_original_JSON_bytes':stats['original_JSON_bytes'],'all_original_metadata_retained':True,'raw_JSON_to_text_inverse_exact':True,'draw_multiplicity_preserved':True,'capture_not_edition_or_corpus_version_choice':True,'source_pipeline_candidate_quality_audit_not_M2_final_acceptance':True,'rights_family_near_protected_uncleared':True,'new_admitted_documents':0,'new_admitted_tokens':0}
 data=(json.dumps(report,ensure_ascii=False,indent=2)+'\n').encode()
 if len(data)>16000000:raise ValueError('full_draw_capture_receipt_cap_before_write')
 retained_capture.write(out,'records.json',data,check)
 # Full role/source metadata is artifact-bound; avoid duplicating it into padded terminal slots.
 return {'status':report['status'],'sources':[{'source_id':s['source_id'],'rows':s['rows'],'counts':s['counts'],'ordered_line_locator_SHA256':s['ordered_line_locator_SHA256'],'unique_captures':len(s['captures'])} for s in results],'draw_count':400,'unique_captured_raw_SHA':len(captures),'captured_text_UTF8_bytes':stats['text_UTF8_bytes'],'captured_original_JSON_bytes':stats['original_JSON_bytes'],'raw_JSON_to_text_inverse_exact':True,'records_file':'records.json','records_SHA256':hashlib.sha256(data).hexdigest(),'records_bytes':len(data),'all_draw_multiplicity_preserved_in_records':True,'candidate_quality_audit_not_M2_final_acceptance':True,'rights_family_near_protected_uncleared':True,'new_admitted_documents':0,'new_admitted_tokens':0}
