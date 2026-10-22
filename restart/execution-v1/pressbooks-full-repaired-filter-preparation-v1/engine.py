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
 family=open_ro(profile['family_frame']['path']);tokens=open_ro(profile['token_frame']['path']);known={bytes.fromhex(h) for h in profile['known_hold_SHA256']};pending_roles={bytes.fromhex(x['text_SHA256']):x for x in profile['overlay_targets'] if x['pending_roles']};overlay_all={bytes.fromhex(x['text_SHA256']) for x in profile['overlay_targets']};seenoverlay=set();excluded={bytes.fromhex(h) for h in profile['fresh_exclusion_SHA256']};seenknown=set();seenexcluded=set();sources=[];rawcount=0;distinct=0;events=0;maxevents=0;maxupper=0;maxreceipt=0;pending=0;pending_bytes=0;reasoncounts=collections.Counter();progress_bytes=0;phase={'source_id':None,'last_ordinal':0}
 for target in profile['overlay_targets']:
  for kind in ['hold_roles','pending_roles']:
   for role in target[kind]:db.execute('INSERT INTO known_roles VALUES(?,?,?,?)',(bytes.fromhex(target['text_SHA256']),role,kind,json.dumps(target['evidence'],ensure_ascii=False)))
 db.commit()
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
    if h in overlay_all:seenoverlay.add(h)
    if h in excluded:seenexcluded.add(h)
    prior=db.execute('SELECT normalized_SHA256,normalized_words,UTF8_bytes,M1_content_tokens,language_pass,explicit_known_hold,generic_mask,candidate,fresh_population,occurrences,source_flags,family_uncertainty FROM texts WHERE text_SHA256=?',(h,)).fetchone()
    if prior is None:
     obj=json.loads(raw.decode('utf8'),object_pairs_hook=inventory.unique,parse_constant=inventory.nofloat);text=obj['text'];require(len(text.encode())==record[18] and len(text.encode())<=2196000,'bounded_source_text')
     receipt=bounded_policy.evaluate(text,{'source_id':sid,'ordinal':ordinal,'text_SHA256':h.hex(),'source_JSON_SHA256':digest.hex()});events+=receipt['events'];require(events<=profile['limits']['all_events'],'aggregate_event_cap_no_truncation');maxevents=max(maxevents,receipt['events']);maxupper=max(maxupper,receipt['events']);maxreceipt=max(maxreceipt,receipt['JSON_bytes'])
     queue=receipt['queue_mask']
     for role in pending_roles.get(h,{}).get('pending_roles',[]):queue|=4 if role.startswith('SOURCE_SPECIFIC_SUSPECTED') else 8
     cand=int(bool(lang) and h not in known and receipt['mask']==0 and queue==0);fresh=int(bool(cand) and h not in excluded)
     row=(h,norm,words,record[18],tok,lang,int(h in known),receipt['mask'],queue,cand,fresh,int(h in excluded),sid,ordinal,1,record[5],int(f[8]!=1 or bool(record[5]&64)),receipt['events'],receipt['event_upper_bound'],receipt['JSON_bytes'])
     if pending_bytes+len(receipt['zlib_bytes'])+2048>8000000:commit()
     check(64000000+len(receipt['zlib_bytes'])+4096);db.execute('INSERT INTO texts VALUES('+','.join(['?']*20)+')',row);db.execute('INSERT INTO receipts VALUES(?,?,?,?,?)',(h,receipt['JSON_SHA256'],receipt['zlib_bytes'],receipt['zlib_SHA256'],receipt['codec']));pending_bytes+=len(receipt['zlib_bytes'])+2048;distinct+=1;reasoncounts.update(receipt['reason_counts'])
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
  require(rawcount==profile['expected']['raw_rows'] and distinct==profile['expected']['distinct_textSHA'] and seenknown==known and seenexcluded==excluded and seenoverlay==overlay_all,'full_raw_distinct_known_review_population_coverage')
  require(db.execute('SELECT count(*) FROM receipts').fetchone()==(distinct,),'receipt_text_bijection')
  require(db.execute('SELECT count(*) FROM occurrences').fetchone()==(profile['expected']['raw_rows'],) and db.execute('SELECT sum(occurrences) FROM texts').fetchone()==(profile['expected']['raw_rows'],),'occurrence_reconciliation')
  require(db.execute('PRAGMA integrity_check').fetchone()==('ok',) and db.execute('PRAGMA foreign_key_check').fetchone() is None,'output_SQLite_integrity_FK')
  populations={}
  clauses=[('all_distinct','1'),('language_pass','language_pass=1'),('known_exact_holds','explicit_known_hold=1'),('representation_holds','generic_mask!=0'),('dependency_queue','(queue_mask&1)!=0'),('component_queue','(queue_mask&10)!=0'),('specific_factual_pending_queue','(queue_mask&4)!=0'),('clear_diagnostic_candidate','candidate=1'),('clear_seen_not_fresh','candidate=1 AND fresh_population=0'),('clear_unreviewed_frame','fresh_population=1')]
  for name,where in clauses:
   count,tok,b,occ=db.execute('SELECT count(*),coalesce(sum(M1_content_tokens),0),coalesce(sum(UTF8_bytes),0),coalesce(sum(occurrences),0) FROM texts WHERE '+where).fetchone();populations[name]={'distinct_raw_textSHA':count,'M1_content_tokens':tok,'one_EOS_each_separate':count,'UTF8_bytes':b,'raw_occurrences':occ,'usable_or_admitted':False}
  buckets={};prefix='language_pass=1 AND explicit_known_hold=0 AND generic_mask=0'
  disjoint=[('LANGUAGE_FAIL','language_pass=0'),('KNOWN_EXACT_HOLD','language_pass=1 AND explicit_known_hold=1'),('REPRESENTATION_HOLD','language_pass=1 AND explicit_known_hold=0 AND generic_mask!=0'),('DEPENDENCY_QUEUE',prefix+' AND (queue_mask&1)!=0'),('COMPONENT_QUEUE',prefix+' AND (queue_mask&1)=0 AND (queue_mask&10)!=0'),('SPECIFIC_FACTUAL_PENDING_QUEUE',prefix+' AND (queue_mask&11)=0 AND (queue_mask&4)!=0'),('CLEAR_ALREADY_SEEN','candidate=1 AND fresh_population=0'),('CLEAR_UNREVIEWED','fresh_population=1')]
  for name,where in disjoint:
   n,tok,b,occ=db.execute('SELECT count(*),coalesce(sum(M1_content_tokens),0),coalesce(sum(UTF8_bytes),0),coalesce(sum(occurrences),0) FROM texts WHERE '+where).fetchone();buckets[name]={'distinct_raw_textSHA':n,'M1_content_tokens':tok,'one_EOS_each_separate':n,'UTF8_bytes':b,'raw_occurrences':occ,'admitted':False}
  require(sum(x['distinct_raw_textSHA'] for x in buckets.values())==distinct and sum(x['raw_occurrences'] for x in buckets.values())==rawcount and sum(x['M1_content_tokens'] for x in buckets.values())==populations['all_distinct']['M1_content_tokens'],'disjoint_bucket_reconciliation')
  for name,baseline in profile.get('expected_baselines',{}).items():require(all(populations[name][k]==v for k,v in baseline.items()),'frozen_previous_count_baseline_'+name)
  commit()
  return {'status':'COMPLETE_FULL_PRESSBOOKS_REPAIRED_DIAGNOSTIC_FILTER_NO_SAMPLING_NO_ADMISSION','sources':sources,'raw_rows':rawcount,'distinct_raw_SHA':distinct,'known_exact_hold_SHA':len(known),'overlay_target_SHA':len(overlay_all),'freshness_exclusion_SHA':len(excluded),'populations_overlapping_axes':populations,'disjoint_buckets':buckets,'reason_counts_distinct_raw_SHA':dict(reasoncounts),'all_policy_events':events,'max_events_per_text':maxevents,'max_lossless_policy_JSON_bytes':maxreceipt,'progress_bytes':progress_bytes,'all_policy_events_losslessly_retained_compressed':True,'no_source_text_duplicates_written':True,'queues_withheld_from_unreviewed_clear_frame':True,'queue_is_not_absence_proof_or_permanent_book_rejection':True,'all_candidate_rights_family_near_protected_uncleared':True,'not_M2_final_acceptance':True,'new_admitted_documents':0,'new_admitted_tokens':0}
 except BaseException:
  db.rollback();raise
 finally:family.close();tokens.close();db.close()
