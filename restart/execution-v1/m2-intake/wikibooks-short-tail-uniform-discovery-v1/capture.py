"""One bounded original-context capture after frozen metadata-only selection."""
import pathlib,sqlite3,json,hashlib,time,os
BASE=pathlib.Path(__file__).resolve().parents[2]
OUT=pathlib.Path(__file__).resolve().parent
SELECT_SHA='4b8035e532e5cc23c42ea1ff258ae38405597e7b9989cef3ea3005fbf04662d3'
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ro(p):return sqlite3.connect('file:'+str(pathlib.Path(p).resolve())+'?mode=ro',uri=True)
def run():
 start=time.clock_gettime(time.CLOCK_MONOTONIC);selection=OUT/'selection.json'
 if sha(selection)!=SELECT_SHA:raise RuntimeError('frozen_selection_changed')
 s=json.loads(selection.read_text());used_native=s['selection_elapsed_seconds'];cap=1_000_000
 def guard(extra=0):
  if time.clock_gettime(time.CLOCK_MONOTONIC)-start+used_native>=30:raise RuntimeError('30second_total_native_work_cap')
  if sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())+extra>cap-16384:raise RuntimeError('1MB_output_cap_terminal_reserve')
 def save(path,payload):
  guard(len(payload))
  with path.open('xb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
 dbpath=pathlib.Path(s['screening_database_path'])
 if sha(dbpath)!=s['screening_database_sha256']:raise RuntimeError('screening_input_changed')
 profile_path=BASE/'wikibooks-language-token-preparation-v1/profile.json'
 if sha(profile_path)!='8f0c7233d2f0af5920e48f0874c1ed94a2e9169191ff26c7f8ecd1499d2b835e':raise RuntimeError('language_profile_changed')
 p=json.loads(profile_path.read_text());sourcepins=p['shards'];final=pathlib.Path(p['finalizer']['path'])
 if sha(final)!=p['finalizer']['sha256']:raise RuntimeError('finalizer_pin_changed')
 capture_profile={'status':'BOUNDED_ORIGINAL_TAIL_CONTEXT_CAPTURE_NO_ACCEPTANCE','selection_sha256':SELECT_SHA,'screening_database':{'path':str(dbpath),'sha256':sha(dbpath)},'finalizer':p['finalizer'],'language_profile_sha256':sha(profile_path),'shards':sourcepins,'capture_rule':'Original contiguous text[max(0,n-2048):n], Unicode character offsets, exact UTF8 bytes. Full short documents allowed when n<=2048; no clipping first character, no replacements.','parent_clarification':'not full doc means no full export of longdocuments; entire shortdocs required for honestreview.','maximum_total_native_seconds_including_selection':30,'aggregate_output_bytes_cap':1000000,'no_classifier_rerun':True,'no_policy_change':True,'no_acceptance_inference':True,'new_admitted_documents':0,'new_admitted_tokens':0}
 save(OUT/'profile.json',(json.dumps(capture_profile,indent=2,sort_keys=True)+'\n').encode())
 d=ro(dbpath);f=ro(final);selected={r['source_ordinal']:r for r in s['selected']};found={};ids=sorted(selected)
 for item in sourcepins:
  guard();path=pathlib.Path(item['path'])
  if sha(path)!=item['sha256']:raise RuntimeError('source_shard_pin_changed')
  source=ro(path);query='select source_ordinal,page_id,revision_id,data from rendered where source_ordinal in ('+','.join('?' for _ in ids)+') order by source_ordinal'
  for ordinal,page,rev,payload in source.execute(query,ids):
   if ordinal in found:raise RuntimeError('duplicate_selected_source')
   r=json.loads(payload);text=r['text'];sample=selected[ordinal];tail=sample['failed_tail'];n=len(text)
   if (page,rev,hashlib.sha256(text.encode()).hexdigest(),n)!=(sample['page_id'],sample['revision_id'],sample['text_sha256'],sample['characters']):raise RuntimeError('selected_text_identity_changed')
   raw_tail=text[tail['start_character']:tail['end_character']]
   if hashlib.sha256(raw_tail.encode()).hexdigest()!=tail['raw_sha256'] or not (tail['end_character']==n and len(raw_tail)<1024 and sum(c.isalpha() for c in raw_tail)>=40):raise RuntimeError('failed_raw_tail_changed')
   a=max(0,n-2048);context=text[a:n];contextbytes=context.encode();file=OUT/(str(ordinal)+'.txt');save(file,contextbytes)
   columns=[r[1] for r in d.execute('pragma table_info(windows)')];windows=[]
   for window in d.execute('select * from windows where source_ordinal=? order by ordinal',(ordinal,)):
    w={k:(v.hex() if isinstance(v,bytes) else v) for k,v in zip(columns,window)};windows.append(w)
   whole=[w for w in windows if w['kind']=='whole'];failed=[w for w in windows if w['ordinal']==tail['window_ordinal']]
   if len(whole)!=1 or len(failed)!=1 or whole[0]['raw_sha256']!=sample['text_sha256'] or failed[0]['raw_sha256']!=tail['raw_sha256'] or failed[0]['policy_pass']!=0:raise RuntimeError('whole_or_failed_window_binding')
   original_holds=f.execute('select holds from final_pages where source_ordinal=?',(ordinal,)).fetchone()[0]
   found[ordinal]={'source_ordinal':ordinal,'page_id':page,'revision_id':rev,'title':sample['title'],'family':sample['family'],'url':r['url'],'source_record_sha256':r['record_sha256'],'original_HTML_sha256':r['html_sha256'],'full_original_text_sha256':sample['text_sha256'],'full_original_characters':n,'context_file':file.name,'context_start_character':a,'context_end_character':n,'context_characters':len(context),'context_UTF8_bytes':len(contextbytes),'context_sha256':sha(file),'context_is_entire_short_document':a==0,'failed_tail_start_character':tail['start_character'],'failed_tail_end_character':tail['end_character'],'failed_tail_relative_context_start':tail['start_character']-a,'failed_tail_relative_context_end':tail['end_character']-a,'failed_tail_raw_sha256':tail['raw_sha256'],'failed_tail_entire_original_document':tail['start_character']==0,'whole_prediction':whole[0],'all_original_window_predictions_and_skips':windows,'original_post_finalizer_holds':json.loads(original_holds),'existing_screening_holds':sample['existing_screening_holds'],'known_discovery_hold':sample['known_discovery_hold'],'language_failure_is_not_semantic_nonEnglish':True,'training_admitted':False}
  source.close()
 if set(found)!=set(selected):raise RuntimeError('missing_selected_document_no_replacement')
 save(OUT/'contexts.json',(json.dumps({'status':'UNIFORM20_SHORT_TAIL_DEVELOPMENT_CONTEXTS_NOT_ACCEPTANCE','records':[found[r['source_ordinal']] for r in s['selected']],'new_admitted_documents':0,'new_admitted_tokens':0},indent=2,sort_keys=True)+'\n').encode())
 d.close();f.close()
 if sha(selection)!=SELECT_SHA or sha(dbpath)!=s['screening_database_sha256']:raise RuntimeError('immutable_selection_or_predictions_changed')
 for item in sourcepins:
  guard()
  if sha(pathlib.Path(item['path']))!=item['sha256']:raise RuntimeError('immutable_source_changed')
 files={x.name:sha(x) for x in OUT.iterdir() if x.is_file()};result={'status':'COMPLETE_BOUNDED_UNIFORM20_SHORT_TAIL_CONTEXT_CAPTURE_NO_ACCEPTANCE','frame_documents':7406,'frame_failed_tail_windows':7406,'sample_documents':20,'full_short_document_contexts':sum(r['context_is_entire_short_document'] for r in found.values()),'failed_tails_that_are_entire_documents':sum(r['failed_tail_entire_original_document'] for r in found.values()),'original_whole_prediction_pass_documents':sum(r['whole_prediction']['policy_pass']==1 for r in found.values()),'source_and_prediction_pins_unchanged':True,'source_text_never_rewritten':True,'selection_sha256':SELECT_SHA,'files_sha256':files,'native_work_seconds_including_selection':time.clock_gettime(time.CLOCK_MONOTONIC)-start+used_native,'output_bytes_before_manifest':sum(x.stat().st_size for x in OUT.iterdir() if x.is_file()),'limits':capture_profile,'no_classifier_rerun_or_policy_override':True,'new_admitted_documents':0,'new_admitted_tokens':0};save(OUT/'manifest.json',(json.dumps(result,indent=2,sort_keys=True)+'\n').encode());print(json.dumps({k:v for k,v in result.items() if k not in ['files_sha256','limits']}))
if __name__=='__main__':run()
