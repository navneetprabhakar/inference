"""One complete two-shard source/metadata pass; no text replication or training."""
import hashlib,json,os,sqlite3,zlib,collections
from pathlib import Path
import inventory,source_guard,schema,bounded_policy,select_core

def require(ok,why):
 if not ok:raise ValueError(why)
def open_ro(p):
 d=sqlite3.connect(Path(p).as_uri()+'?mode=ro&immutable=1',uri=True)
 for v in ['query_only=ON','cache_size=-4096','mmap_size=0','temp_store=MEMORY']:d.execute('PRAGMA '+v)
 return d

def run(profile,out,check):
 out=Path(out);check(64000000);db=sqlite3.connect(out/'candidate.sqlite');db.execute('PRAGMA page_size=4096');require(db.execute('PRAGMA journal_mode=PERSIST').fetchone()==('persist',),'PERSIST');db.execute('PRAGMA journal_size_limit=64000000');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA cache_size=-8192');db.execute('PRAGMA temp_store=MEMORY');db.execute('PRAGMA mmap_size=0');db.execute('PRAGMA max_page_count='+str(profile['limits']['DB_bytes']//4096));db.executescript(schema.SCHEMA);db.commit()
 family=open_ro(profile['family_frame']['path']);tokens=open_ro(profile['token_frame']['path']);known={bytes.fromhex(h) for h in profile['known_hold_SHA256']};excluded={bytes.fromhex(h) for h in profile['fresh_exclusion_SHA256']};seenknown=set();seenexcluded=set();sources=[];rawcount=0;distinct=0;events=0;maxevents=0;maxupper=0;maxreceipt=0;pending=0;pending_bytes=0;reasoncounts=collections.Counter();progress_bytes=0;phase={'source_id':None,'last_ordinal':0}
 for c in [db,family,tokens]:c.set_progress_handler(lambda:(check() or 0),10000)
 def commit():
  nonlocal pending,pending_bytes,progress_bytes
  check();db.commit();pending=0;pending_bytes=0
  entry=(json.dumps({'phase':'COMMITTED_RAW_METADATA','raw_rows':rawcount,'distinct_raw_SHA':distinct,'events':events,**phase},separators=(',',':'))+'\n').encode()
  require(progress_bytes+len(entry)<=profile['limits'].get('progress_bytes',8000000),'progress_prewrite_cap');check(len(entry))
  with (out/'progress.metadata.jsonl').open('ab') as f:f.write(entry);f.flush();os.fsync(f.fileno())
  progress_bytes+=len(entry)
  journal=out/'candidate.sqlite-journal';require(journal.stat().st_size<=profile['limits']['journal_bytes'],'journal_cap');check()
 try:
  for source in profile['sources']:
   sid=source['source_id'];phase['source_id']=sid;phase['last_ordinal']=0;binding=source['raw'];frame=source['frame'];fdb=open_ro(frame['path']);fdb.set_progress_handler(lambda:(check() or 0),10000);current=iter(fdb.execute('SELECT * FROM records ORDER BY ordinal'));linehash=hashlib.sha256()
   db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',(sid,binding['path'],bytes.fromhex(binding['SHA256']),json.dumps(binding['stat']),frame['rows']))
   def accept(ordinal,offset,n,ends,digest,raw):
    nonlocal rawcount,distinct,events,maxevents,maxupper,maxreceipt,pending,pending_bytes
    check();expected=next(current,None);require(expected is not None,'extra_source_row')
    record,_=inventory.row(ordinal,offset,n,ends,digest,raw)
    if expected[5]&inventory.FLAGS['KNOWN_REVIEW_HOLD']:
     matches=[k for k in source['known_holds'] if k['source_ordinal']==ordinal and k['line_SHA256']==digest.hex() and k['text_SHA256']==record[17].hex() and k['id']==record[6]]
     require(len(matches)==1,'frozen_original_review_hold_binding');record=record[:5]+(record[5]|inventory.FLAGS['KNOWN_REVIEW_HOLD'],)+record[6:]
    require(tuple(expected)==tuple(record) and raw is not None,'full_original_frame_row_binding')
    f=family.execute('SELECT line_offset,line_bytes,ends_LF,line_SHA256,text_SHA256,text_UTF8_bytes,existing_flags,identity_holds,lead_status,lead_root_id FROM rows WHERE source_id=? AND ordinal=?',(sid,ordinal)).fetchone()
    require(f is not None and f[:7]==(offset,n,int(ends),digest,record[17],record[18],record[5]),'family_source_locator_flags_join')
    measured=tokens.execute('SELECT text_SHA256,line_SHA256,UTF8_bytes,content_tokens,language_pass,source_flags,explicit_hold_flags,normalized_SHA256,normalized_words FROM docs WHERE source=? AND source_ordinal=?',(sid,ordinal)).fetchone()
    require(measured is not None and measured[:3]==(record[17],digest,record[18]) and measured[5:7]==(record[5],f[7]),'verified_M1_language_doc_join')
    h=record[17];tok,lang,norm,words=measured[3],measured[4],measured[7],measured[8]
    require(type(tok)==int and tok>=0 and lang in [0,1] and len(norm)==32,'measurement_types')
    if h in known:seenknown.add(h)
    if h in excluded:seenexcluded.add(h)
    prior=db.execute('SELECT normalized_SHA256,normalized_words,UTF8_bytes,M1_content_tokens,language_pass,explicit_known_hold,generic_mask,candidate,fresh_population,occurrences,source_flags,family_uncertainty FROM texts WHERE text_SHA256=?',(h,)).fetchone()
    if prior is None:
     obj=json.loads(raw.decode('utf8'),object_pairs_hook=inventory.unique,parse_constant=inventory.nofloat);text=obj['text'];require(len(text.encode())==record[18] and len(text.encode())<=2196000,'bounded_source_text')
     receipt=bounded_policy.evaluate(text);events+=receipt['events'];require(events<=profile['limits']['all_events'],'aggregate_event_cap_no_truncation');maxevents=max(maxevents,receipt['events']);maxupper=max(maxupper,receipt['event_upper_bound']);maxreceipt=max(maxreceipt,receipt['JSON_bytes'])
     cand=int(bool(lang) and h not in known and receipt['mask']==0);fresh=int(bool(cand) and h not in excluded)
     row=(h,norm,words,record[18],tok,lang,int(h in known),receipt['mask'],cand,fresh,int(h in excluded),sid,ordinal,1,record[5],int(f[8]!=1 or bool(record[5]&64)),receipt['events'],receipt['event_upper_bound'],receipt['JSON_bytes'])
     if pending_bytes+len(receipt['zlib_bytes'])+2048>8000000:commit()
     check(64000000+len(receipt['zlib_bytes'])+4096);db.execute('INSERT INTO texts VALUES('+','.join(['?']*19)+')',row);db.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',(h,receipt['JSON_SHA256'],receipt['zlib_bytes'],receipt['zlib_SHA256'],receipt['codec']));pending_bytes+=len(receipt['zlib_bytes'])+2048;distinct+=1;reasoncounts.update(receipt['reason_counts'])
    else:
     require(prior[:6]==(norm,words,record[18],tok,lang,int(h in known)),'same_raw_SHA_measurement_contradiction')
     db.execute('UPDATE texts SET occurrences=occurrences+1,source_flags=source_flags|?,family_uncertainty=family_uncertainty|? WHERE text_SHA256=?',(record[5],int(f[8]!=1 or bool(record[5]&64)),h))
    db.execute('INSERT INTO occurrences VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,ordinal,offset,n,digest,h,record[5],f[7],f[8],f[9]));rawcount+=1;pending+=1;pending_bytes+=512;phase['last_ordinal']=ordinal
    require(rawcount<=profile['expected']['raw_rows'] and distinct<=profile['expected']['distinct_textSHA'],'whole_frame_caps')
    linehash.update(select_core.transcript([ordinal,offset,n,int(ends),digest.hex()]))
    if pending>=100:commit()
   lines=inventory.Lines(4000000,100000,accept)
   try:
    with source_guard.opened(binding,check) as read:
     counts=inventory.gzip_stream(read,lines.add,{'compressed_bytes':binding['bytes'],'decoded_bytes':2000000000},check);lines.finish();read.assert_custody()
    require(next(current,None) is None and lines.ordinal==frame['rows'] and lines.total==counts['decoded_bytes'],'all_frame_rows_decoded_EOF')
    require(counts['compressed_bytes']==binding['bytes'] and counts['compressed_SHA256']==binding['SHA256'] and linehash.hexdigest()==frame['ordered_line_locator_SHA256'],'source_full_SHA_crc_EOF_transcript')
    require(source_guard.ident(Path(frame['path']).stat())==frame['stat'],'source_frame_stat_postflight')
    sources.append({'source_id':sid,'rows':lines.ordinal,'counts':counts,'ordered_line_locator_SHA256':linehash.hexdigest()});commit()
   finally:fdb.close()
  require(rawcount==profile['expected']['raw_rows'] and distinct==profile['expected']['distinct_textSHA'] and seenknown==known and seenexcluded==excluded,'full_raw_distinct_known_review_population_coverage')
  require(db.execute('SELECT count(*) FROM receipts').fetchone()==(distinct,),'receipt_text_bijection')
  require(db.execute('SELECT count(*) FROM occurrences').fetchone()==(profile['expected']['raw_rows'],) and db.execute('SELECT sum(occurrences) FROM texts').fetchone()==(profile['expected']['raw_rows'],),'occurrence_reconciliation')
  require(db.execute('PRAGMA integrity_check').fetchone()==('ok',) and db.execute('PRAGMA foreign_key_check').fetchone() is None,'output_SQLite_integrity_FK')
  populations={}
  for name,where in [('all_distinct','1'),('language_pass','language_pass=1'),('language_after_known32','language_pass=1 AND explicit_known_hold=0'),('full_filtered_candidate','candidate=1'),('fresh_review_population','fresh_population=1'),('previously_reviewed_surviving_candidate','candidate=1 AND fresh_population=0')]:
   count,tok,b,occ=db.execute('SELECT count(*),coalesce(sum(M1_content_tokens),0),coalesce(sum(UTF8_bytes),0),coalesce(sum(occurrences),0) FROM texts WHERE '+where).fetchone();populations[name]={'distinct_raw_textSHA':count,'M1_content_tokens':tok,'one_EOS_each_separate':count,'UTF8_bytes':b,'raw_occurrences':occ,'usable_or_admitted':False}
  for name,baseline in profile.get('expected_baselines',{}).items():
   require(all(populations[name][k]==v for k,v in baseline.items()),'frozen_previous_count_baseline_'+name)
  normalized={'scope':'Candidate exact stored case/punctuation-losing normalization, no representative selected or near/protected clearance.','groups':0,'multiple_raw_SHA_groups':0,'excess_raw_SHA':0,'max_group':0,'one_per_group_tokens_min':0,'one_per_group_tokens_max':0,'ambiguous_tokens_groups':0}
  for _,count,tmin,tmax in db.execute('SELECT normalized_SHA256,count(*),min(M1_content_tokens),max(M1_content_tokens) FROM texts WHERE candidate=1 GROUP BY normalized_SHA256'):
   check();normalized['groups']+=1;normalized['multiple_raw_SHA_groups']+=count>1;normalized['excess_raw_SHA']+=count-1;normalized['max_group']=max(normalized['max_group'],count);normalized['one_per_group_tokens_min']+=tmin;normalized['one_per_group_tokens_max']+=tmax;normalized['ambiguous_tokens_groups']+=tmin!=tmax
  def context(s,o):
   row=family.execute('SELECT r.lead_status,r.existing_flags,r.identity_holds,a.value,b.value,c.value,d.value FROM rows r LEFT JOIN strings a ON a.string_id=r.id_id LEFT JOIN strings b ON b.string_id=r.url_id LEFT JOIN strings c ON c.string_id=r.book_url_id LEFT JOIN strings d ON d.string_id=r.lead_root_id WHERE r.source_id=? AND r.ordinal=?',(s,o)).fetchone();require(row is not None,'selected_context_row');return dict(zip(['lead_status','source_flags','prior_identity_hold_bits','source_id_URL','source_url','book_url','derived_book_root_LEAD_NOT_verified_family'],row))
  selection=select_core.select(db,profile['sampling_seed'],200,check,context);data=(json.dumps(selection,ensure_ascii=False,indent=2)+'\n').encode();require(len(data)<=profile['limits']['selection_bytes'],'selection_output_cap');check(len(data))
  with (out/'fresh-review-selection.json').open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  commit()
  return {'status':'COMPLETE_FULL_PRESSBOOKS_RAW_FILTER_AND_FRESH_SELECTION_NO_ADMISSION','sources':sources,'raw_rows':rawcount,'distinct_raw_SHA':distinct,'known_exact_hold_SHA':len(known),'fresh_exclusion_SHA':len(excluded),'populations':populations,'normalized_exact_candidate_diagnostics':normalized,'reason_counts_distinct_raw_SHA':dict(reasoncounts),'all_policy_events':events,'max_events_per_text':maxevents,'max_event_upper_bound_per_text':maxupper,'max_lossless_policy_JSON_bytes':maxreceipt,'progress_bytes':progress_bytes,'sampling':{k:v for k,v in selection.items() if k!='draws'},'all_policy_events_losslessly_retained_compressed':True,'no_source_text_duplicates_written':True,'all_candidate_rights_family_near_protected_uncleared':True,'not_M2_final_acceptance':True,'new_admitted_documents':0,'new_admitted_tokens':0}
 except BaseException:
  db.rollback();raise
 finally:family.close();tokens.close();db.close()
