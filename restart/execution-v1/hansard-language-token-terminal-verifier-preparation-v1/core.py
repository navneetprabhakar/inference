"""Stored Hansard diagnostic metadata verification. Never original text/classifier/tokenizer."""
import hashlib,json,math,re,sqlite3
from pathlib import Path

def require(ok,label):
 if not ok:raise ValueError(label)
def sha(path,check=lambda:None):
 digest=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):digest.update(b);check()
 return digest.hexdigest()
def dbopen(path):
 db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro&immutable=1',uri=True);db.execute('pragma query_only=ON');db.execute('pragma cache_size=-8192');db.execute('pragma mmap_size=0');db.execute('pragma temp_store=MEMORY');return db

def window(row,doc,ordinal,length):
 d,o,kind,start,end,alpha,raw,projection,scored,skip,label,rawprob,top,en,passed=row
 require(d==doc and o==ordinal,'ordered_window_identity')
 expected=(0,0,length) if ordinal==0 else (1,(ordinal-1)*1024,min(ordinal*1024,length))
 require((kind,start,end)==expected and type(alpha)is int and 0<=alpha<=end-start,'whole_chunk_span_alpha_bounds')
 require(type(raw)is bytes and len(raw)==32 and type(projection)is bytes and len(projection)==32,'window_hash_shapes')
 expectedscore=int(ordinal==0 or alpha>=40);require(scored==expectedscore,'whole_or40alpha_score_rule')
 if not scored:require(skip==1 and all(x is None for x in [label,rawprob,top,en,passed]),'explicit_skip_no_prediction');return None
 require(skip is None and type(label)is str and re.fullmatch(r'__label__[a-z_\-]{2,24}',label) and type(rawprob)is str and 0<len(rawprob)<=64,'prediction_label_probability_fields')
 value=float(rawprob);english=value if label=='__label__en' else 0.
 require(math.isfinite(value) and 0<=value<=1.001 and top==value and en==english and passed==int(english>=.8),'exact_top1_English_threshold_projection')
 return english

def verify(db,metadata,producer,profile,check):
 require(db.execute('pragma integrity_check').fetchone()==('ok',) and db.execute('pragma foreign_key_check').fetchone() is None,'SQLite_integrity_FK')
 agg=sqlite3.connect(':memory:');agg.execute('pragma cache_size=-8192');agg.execute('pragma temp_store=MEMORY');agg.execute('create table agg(text_SHA256 blob primary key,characters integer,UTF8_bytes integer,content_tokens integer,language_pass integer,min_english real,scored integer,skipped integer,occurrences integer,explicit_hold_flags integer,source_flags integer,normalized_SHA256 blob,normalized_words integer,rights_unclear_flags integer) without rowid')
 cursors={s['source_id']:iter(metadata[s['source_id']].execute('select * from records where source_id=? order by ordinal',(s['source_id'],))) for s in profile['sources']};sourcecounts={sid:0 for sid in cursors};wins=iter(db.execute('select * from windows order by doc,ordinal'));totals={'documents':0,'UTF8_bytes':0,'characters':0,'content_tokens':0,'all_windows':0,'scored':0,'skipped':0};known=[];rights_counts={0:0,1:0,2:0};semanticSHA=profile['known_targets']['semantic_text_SHA256']
 try:
  for row in db.execute('select * from docs order by doc'):
   doc,source,ordinal,idsha,textsha,linesha,chars,bytes_,tokens,eos,scored,skipped,lang,minimum,flags,held,normsha,nwords,rights=row;totals['documents']+=1
   require(doc==totals['documents'] and source in cursors,'document_identity_order');sourcecounts[source]+=1;require(ordinal==sourcecounts[source],'source_ordinal_coverage');m=next(cursors[source],None);require(m is not None,'source_metadata_missing')
   require((ordinal,idsha,textsha,linesha,chars,bytes_,flags)==(m[1],hashlib.sha256(m[7].encode()).digest(),m[13],m[5],m[15],m[14],m[6]),'exact_source_record_ID_rawline_text_and_flags_join')
   require(type(chars)is int and 0<=chars<=976414 and type(bytes_)is int and 0<=bytes_<=976482 and type(tokens)is int and 0<=tokens<=bytes_ and eos==1,'raw_document_token_EOS_bounds')
   require(type(normsha)is bytes and len(normsha)==32 and type(nwords)is int and 0<=nwords<=8000000,'normalized_diagnostic_shapes')
   actualholds=int(textsha.hex()==semanticSHA);require(held==actualholds,'independent_exact_semantic_textSHA_hold_allcopies');expected_rights=1 if m[8]=='uk-hansard-northern-ireland-assembly' else 2 if m[8]=='uk-hansard-london-mayors-questions' else 0;require(rights==expected_rights,'independent_source_NI_London_rights_diagnostic_flags');rights_counts[rights]+=1
   if held:known.append([source,ordinal,idsha.hex(),textsha.hex(),held])
   n=1+(chars+1023)//1024;english=[];alpha=0;first=None
   for o in range(n):
    w=next(wins,None);require(w is not None,'missing_window');value=window(w,doc,o,chars)
    if o==0:first=w
    else:alpha+=w[5]
    if chars<=1024 and o==1:require(w[5:8]==first[5:8],'whole_shortchunk_alpha_and_raw_projection_hash_identity')
    if value is not None:english.append(value)
   require(alpha==first[5] and len(english)==scored and n-len(english)==skipped and min(english)==minimum and lang==int(minimum>=.8),'whole_chunk_alpha_min_and_document_language_reconciliation')
   values=(chars,bytes_,tokens,lang,minimum,scored,skipped);prior=agg.execute('select * from agg where text_SHA256=?',(textsha,)).fetchone()
   if prior is None:agg.execute('insert into agg values('+','.join('?'*14)+')',(textsha,*values,1,held,flags,normsha,nwords,rights))
   else:
    require(prior[1:8]==values and prior[11:13]==(normsha,nwords),'same_rawhash_all_diagnostics_equal');agg.execute('update agg set occurrences=occurrences+1,explicit_hold_flags=explicit_hold_flags|?,source_flags=source_flags|?,rights_unclear_flags=rights_unclear_flags|? where text_SHA256=?',(held,flags,rights,textsha))
   for k,v in [('UTF8_bytes',bytes_),('characters',chars),('content_tokens',tokens),('all_windows',n),('scored',scored),('skipped',skipped)]:totals[k]+=v
   if doc%256==0:check()
  require(next(wins,None)is None and all(next(c,None)is None for c in cursors.values()),'no_extra_source_or_window_rows')
  require(all(sourcecounts[s['source_id']]==s['rows'] for s in profile['sources']),'all_source_rows_exact')
  for k in ['documents','UTF8_bytes','characters','all_windows']:require(totals[k]==profile['limits'][k],'exact_frozen_full_frame_denominators')
  require(all(producer['stats'][k]==v for k,v in totals.items()) and totals['scored']+totals['skipped']==totals['all_windows'],'producer_all_raw_totals')
  require(known==profile['known_targets']['expected_bindings']==producer['known_hold_bindings'],'exact_all_known_bindings')
  observed=iter(db.execute('select * from texts order by text_SHA256'));unique=0
  for expected in agg.execute('select * from agg order by text_SHA256'):
   require(next(observed,None)==expected,'independent_distinct_hash_occurrence_token_flags_normalized_reconciliation');unique+=1
  require(next(observed,None)is None,'no_extra_distinct_hash_row')
  summary={}
  for name,where in [('all_raw','1'),('raw_language_pass','language_pass=1'),('raw_language_pass_after_explicit_known_holds','language_pass=1 and explicit_hold_flags=0')]:
   n,t,b=db.execute('select count(*),coalesce(sum(content_tokens),0),coalesce(sum(UTF8_bytes),0) from docs where '+where).fetchone();summary[name]={'documents':n,'M1_content_tokens':t,'EOS_separate':n,'content_plus_EOS':t+n,'UTF8_bytes':b,'usable_or_admitted':False}
  for name,where in [('all_distinct_text_hashes','1'),('distinct_text_language_pass','language_pass=1'),('distinct_text_language_pass_without_any_explicit_hold_occurrence','language_pass=1 and explicit_hold_flags=0')]:
   n,t,b,occ=agg.execute('select count(*),coalesce(sum(content_tokens),0),coalesce(sum(UTF8_bytes),0),coalesce(sum(occurrences),0) from agg where '+where).fetchone();summary[name]={'distinct_text_hashes':n,'M1_content_tokens':t,'one_EOS_per_distinct_hash_separate':n,'content_plus_EOS':t+n,'UTF8_bytes':b,'raw_occurrences':occ,'usable_or_admitted':False}
  require(summary==producer['summary'],'all_raw_distinct_language_hold_EOS_summary');rightrows=[[k,v]for k,v in sorted(rights_counts.items())if v];require(rightrows==profile['rights_expected_counts']==producer['rights_diagnostic_counts'] and producer['all_record_rights_status']=='UNCLEARED_REGARDLESS_FLAGS','exact_rights_diagnostic_counts_no_blanket_clearance')
  return {'totals':totals,'source_rows':sourcecounts,'distinct_raw_text_hashes':unique,'summary':summary,'known_bindings':known,'rights_diagnostic_counts':rightrows,'all_record_rights_status':'UNCLEARED_REGARDLESS_FLAGS','independently_recomputed_original_tokens_raw_or_projection_hashes':False,'source_CRC_SHA_inherited_verified_producer_receipt_only':True,'new_admitted_documents':0,'new_admitted_tokens':0}
 finally:agg.close()
