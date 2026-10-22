"""Single source gzip pass; fixed M1/classifier diagnostics, no text outputs."""
import hashlib,json,sqlite3,time,os
from pathlib import Path
import rules,schema,classify
EXPECTED={'documents':15820,'UTF8_bytes':1975336391,'characters':1970148560,'all_windows':1947805}

def require(ok,label):
 if not ok:raise ValueError(label)
def sha(b):return hashlib.sha256(b).digest()
def normalization_diagnostic(text,normalize):
 value=normalize(text);raw=value.encode('utf8');require(len(raw)<=64000000,'normalized_diagnostic_resource_cap');words=len(value.split());require(words<=8000000,'normalized_word_resource_cap');return sha(raw),words

def prepared(text):
 windows=[];n=0
 for meta,chunk in rules.windows(text):
  projected=rules.projection(chunk).encode('utf8');meta={**meta,'raw_SHA256':sha(chunk.encode()),'projection_SHA256':sha(projected)};windows.append((meta,projected))
  if meta['scored']:n+=len(projected)+1
 require(n<=8388608,'single_document_projection_cap')
 return windows,n

def source_record(ordinal,offset,n,lf,lineSHA,raw,meta,inventory):
 require(raw is not None and meta is not None and (ordinal,offset,n,int(lf),lineSHA)==tuple(meta[:5]),'raw_line_frame_binding')
 require(type(raw) is bytes and len(raw)==n and raw.endswith(b'\n')==bool(lf) and sha(raw)==lineSHA,'whole_raw_line_SHA_binding')
 try:
  obj=json.loads(raw.decode('utf8',errors='strict'),object_pairs_hook=inventory.unique,parse_constant=inventory.nofloat);identity=obj['id'];text=obj['text'];require(type(identity) is str and type(text) is str,'original_text_ID_types');encoded=text.encode('utf8',errors='strict')
 except Exception:raise ValueError('source_record_schema_or_UTF8') from None
 require((identity,sha(encoded),len(encoded),len(text))==(meta[6],meta[17],meta[18],meta[19]),'exact_original_ID_and_text_SHA_frame_binding')
 require(len(encoded)<=976482 and len(text)<=976414 and n<=981231,'frozen_document_size_bounds')
 return identity,text,encoded

def explicit_flags(identity,textSHA,targets):return int(textSHA==targets['semantic_text_SHA256'])

class Store:
 def __init__(self,out,limits,check):
  self.out=Path(out);self.check=check;self.limits=limits;check(32000000);self.db=sqlite3.connect(self.out/'screening.sqlite');self.db.execute('pragma page_size=4096');require(self.db.execute('pragma journal_mode=PERSIST').fetchone()==('persist',),'PERSIST_mode');self.db.execute('pragma journal_size_limit=32000000');self.db.execute('pragma synchronous=FULL');self.db.execute('pragma cache_size=-8192');self.db.execute('pragma temp_store=MEMORY');self.db.execute('pragma foreign_keys=ON');self.db.execute('pragma max_page_count='+str(limits['DB_bytes']//4096));self.db.executescript(schema.SCHEMA);self.db.commit();self.windows=0;self.docs=0;self.stats={'documents':0,'UTF8_bytes':0,'characters':0,'content_tokens':0,'all_windows':0,'scored':0,'skipped':0,'batches':0};self.committed={'documents':0,'windows':0}
 def journal(self):
  require((self.out/'screening.sqlite-journal').stat().st_size<=32000000,'journal_reserve_cap')
 def batch(self,profile,batch,remaining,infer=classify.infer):
  if not batch:return
  require(len(batch)<=64,'batch_document_cap')
  allwindows=sum(len(d['windows']) for d in batch);self.check(32000000+allwindows*768+len(batch)*4096)
  lines=[p for d in batch for m,p in d['windows'] if m['scored']];data=b'\n'.join(lines)+b'\n';require(len(data)<=8388608,'batch_projection_cap')
  predictions=infer(profile,data,remaining,self.check);require(len(predictions)==len(lines),'exact_classifier_line_coverage');pi=0
  for d in batch:
   english=[];windowrows=[];skips=0
   for ordinal,(m,p) in enumerate(d['windows']):
    if m['scored']:
     try:
      label,rawprob,top,en,passed=rules.prediction(predictions[pi]);require(len(rawprob)<=64,'probability_resource_width')
     except Exception:raise ValueError('classifier_prediction_parse') from None
     pi+=1;english.append(en);pred=(label,rawprob,top,en,passed)
    else:skips+=1;pred=(None,None,None,None,None)
    windowrows.append((d['doc'],ordinal,0 if m['kind']=='whole' else 1,m['start'],m['end'],m['alphabetics'],m['raw_SHA256'],m['projection_SHA256'],int(m['scored']),None if m['scored'] else 1,*pred))
   require(english and len(english)+skips==len(d['windows']),'whole_and_every_chunk_coverage');minimum=min(english);passed=int(minimum>=.8);identity=d['identity'];textSHA=bytes.fromhex(identity['text_SHA256']);flags=d['explicit_flags'];tokens=d['tokens']
   self.db.execute(schema.DOC_INSERT,(d['doc'],identity['source'],identity['ordinal'],sha(identity['id'].encode()),textSHA,bytes.fromhex(identity['line_SHA256']),identity['characters'],identity['UTF8_bytes'],tokens,1,len(english),skips,passed,minimum,identity['source_flags'],flags,d['normalized_SHA256'],d['normalized_words'],identity.get('rights_unclear_flags',0)))
   for row in windowrows:
    self.db.execute(schema.WINDOW_INSERT,row);self.windows+=1
    if self.windows%256==0:self.journal();self.check()
   prior=self.db.execute('select characters,UTF8_bytes,content_tokens,language_pass,min_english,scored,skipped,occurrences,explicit_hold_flags,source_flags,normalized_SHA256,normalized_words,rights_unclear_flags from texts where text_SHA256=?',(textSHA,)).fetchone();base=(identity['characters'],identity['UTF8_bytes'],tokens,passed,minimum,len(english),skips)
   if prior is None:self.db.execute(schema.TEXT_INSERT,(textSHA,*base,1,flags,identity['source_flags'],d['normalized_SHA256'],d['normalized_words'],identity.get('rights_unclear_flags',0)))
   else:
    require(tuple(prior[:7])==base and tuple(prior[10:12])==(d['normalized_SHA256'],d['normalized_words']),'same_text_hash_diagnostic_disagreement');self.db.execute('update texts set occurrences=occurrences+1,explicit_hold_flags=explicit_hold_flags|?,source_flags=source_flags|?,rights_unclear_flags=rights_unclear_flags|? where text_SHA256=?',(flags,identity['source_flags'],identity.get('rights_unclear_flags',0),textSHA))
   self.docs+=1;st=self.stats;st['documents']+=1;st['UTF8_bytes']+=identity['UTF8_bytes'];st['characters']+=identity['characters'];st['content_tokens']+=tokens;st['all_windows']+=len(d['windows']);st['scored']+=len(english);st['skipped']+=skips
  require(pi==len(predictions) and self.docs<=15820 and self.windows<=1947805,'global_doc_window_upper');self.journal();self.check();self.db.commit();self.journal();self.stats['batches']+=1;self.committed={'documents':self.docs,'windows':self.windows}
 def close(self):self.db.close()
 def summary(self):
  require(self.db.execute('pragma integrity_check').fetchone()==('ok',) and self.db.execute('pragma foreign_key_check').fetchone() is None,'output_SQL_integrity_FK')
  require(self.db.execute('select count(*) from docs').fetchone()==(self.docs,) and self.db.execute('select count(*) from windows').fetchone()==(self.windows,),'SQL_exact_allrow_coverage')
  require(self.db.execute('select count(*) from windows where scored=1 and (label is null or raw_probability is null or policy_pass is null)').fetchone()==(0,),'no_missing_predictions')
  require(self.db.execute('select count(*) from windows where scored=0 and (skip_reason!=1 or label is not null or policy_pass is not null)').fetchone()==(0,),'skip_records_explicit')
  summary={}
  for name,where in [('all_raw','1'),('raw_language_pass','language_pass=1'),('raw_language_pass_after_explicit_known_holds','language_pass=1 and explicit_hold_flags=0')]:
   n,t,b=self.db.execute('select count(*),coalesce(sum(content_tokens),0),coalesce(sum(UTF8_bytes),0) from docs where '+where).fetchone();summary[name]={'documents':n,'M1_content_tokens':t,'EOS_separate':n,'content_plus_EOS':t+n,'UTF8_bytes':b,'usable_or_admitted':False}
  for name,where in [('all_distinct_text_hashes','1'),('distinct_text_language_pass','language_pass=1'),('distinct_text_language_pass_without_any_explicit_hold_occurrence','language_pass=1 and explicit_hold_flags=0')]:
   n,t,b,occ=self.db.execute('select count(*),coalesce(sum(content_tokens),0),coalesce(sum(UTF8_bytes),0),coalesce(sum(occurrences),0) from texts where '+where).fetchone();summary[name]={'distinct_text_hashes':n,'M1_content_tokens':t,'one_EOS_per_distinct_hash_separate':n,'content_plus_EOS':t+n,'UTF8_bytes':b,'raw_occurrences':occ,'usable_or_admitted':False}
  totals=self.db.execute('select sum(occurrences),sum(content_tokens*occurrences),sum(UTF8_bytes*occurrences) from texts').fetchone();require(totals==(self.docs,self.stats['content_tokens'],self.stats['UTF8_bytes']),'distinct_hash_occurrence_reconciliation')
  return summary

def run(profile,out,metadata_iterator,source_context,inventory,check,remaining,tokenizer,normalize,infer=classify.infer):
 store=Store(out,profile['limits'],check);batch=[];projected_bytes=0;docid=0;source_receipts=[];target_seen=[]
 targets=profile['known_targets']
 def flush():
  nonlocal batch,projected_bytes
  if batch:store.batch(profile,batch,remaining(),infer);batch=[];projected_bytes=0
 try:
  for item in profile['sources']:
   cursor=iter(metadata_iterator(item));expected_ordinal=0
   def record(ordinal,offset,n,lf,lineSHA,raw):
    nonlocal expected_ordinal,docid,batch,projected_bytes
    check();expected_ordinal+=1;require(ordinal==expected_ordinal,'source_ordinal_order');m=next(cursor,None);identity,text,encoded=source_record(ordinal,offset,n,lf,lineSHA,raw,m,inventory)
    docid+=1;ident={'source':item['source_id'],'ordinal':ordinal,'id':identity,'text_SHA256':m[17].hex(),'line_SHA256':lineSHA.hex(),'UTF8_bytes':len(encoded),'characters':len(text),'source_flags':m[5],'rights_unclear_flags':m[20]};holds=explicit_flags(identity,ident['text_SHA256'],targets)
    if holds:target_seen.append([item['source_id'],ordinal,sha(identity.encode()).hex(),ident['text_SHA256'],holds])
    normalizedSHA,normalized_words=normalization_diagnostic(text,normalize);windows,nbytes=prepared(text)
    if batch and (len(batch)>=64 or projected_bytes+nbytes>8388608):flush()
    tokens=len(tokenizer.encode(text,add_special_tokens=False).ids);batch.append({'doc':docid,'identity':ident,'explicit_flags':holds,'tokens':tokens,'windows':windows,'normalized_SHA256':normalizedSHA,'normalized_words':normalized_words});projected_bytes+=nbytes
   lines=inventory.Lines(981231,item['rows'],record)
   with source_context(item,check) as read:
    counts=inventory.gzip_stream(read,lines.add,{'compressed_bytes':item['source']['bytes'],'decoded_bytes':2000000000},check);lines.finish();flush()
   require(next(cursor,None) is None and expected_ordinal==item['rows'] and lines.total==counts['decoded_bytes']==item['decoded_bytes'] and counts['compressed_bytes']==item['source']['bytes'] and counts['compressed_SHA256']==item['source']['SHA256'],'complete_source_frame_CRC_SHA_denominator');source_receipts.append({'source':item['source_id'],'rows':expected_ordinal,**counts})
  require(all(store.stats[k]==v for k,v in EXPECTED.items()) and store.stats['scored']+store.stats['skipped']==EXPECTED['all_windows'],'exact_fullframe_token_language_denominators')
  require(target_seen==profile['known_targets']['expected_bindings'],'all_explicit_knownhold_bindings');summary=store.summary();rights_counts=store.db.execute('select rights_unclear_flags,count(*) from docs group by rights_unclear_flags').fetchall();require([list(x) for x in rights_counts]==profile['rights_expected_counts'],'exact_metadata_rights_diagnostic_counts');store.db.commit()
  return {'status':'COMPLETE_RAW_HANSARD_LANGUAGE_M1_DIAGNOSTICS_NO_ADMISSION','stats':store.stats,'summary':summary,'source_receipts':source_receipts,'explicit_hold_bits':{'1':'exact_known_semantic_textSHA_all_copies'},'known_hold_bindings':target_seen,'rights_diagnostic_counts':rights_counts,'all_record_rights_status':'UNCLEARED_REGARDLESS_FLAGS','scope':'Allrawsourcepositions retained including duplicates. Distinct-text-hash diagnostics separate; languagepass and no-knownhold are not sourcequality/rights/leakage/admission.','new_admitted_documents':0,'new_admitted_tokens':0}
 except BaseException as exc:
  store.db.rollback();exc.diagnostic_partial={'committed':store.committed,'processed_stats_may_include_rolledback_batch':store.stats};raise
 finally:store.close()
