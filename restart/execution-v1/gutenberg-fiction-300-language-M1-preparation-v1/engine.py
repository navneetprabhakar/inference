"""Exact PG envelopes, one at a time; immutable M1/language diagnostics only."""
import hashlib,json,os,sqlite3
from pathlib import Path
import custody,rules,classify
sha=lambda b:hashlib.sha256(b).digest()
def need(v,m):
 if not v:raise ValueError(m)
SCHEMA='''
CREATE TABLE docs(ordinal INTEGER PRIMARY KEY,ebook_ID INTEGER NOT NULL,
 raw_SHA256 BLOB NOT NULL,source_start INTEGER NOT NULL,source_end INTEGER NOT NULL,
 text_SHA256 BLOB NOT NULL,characters INTEGER NOT NULL,UTF8_bytes INTEGER NOT NULL,
 content_tokens INTEGER NOT NULL,EOS_separate INTEGER NOT NULL,scored INTEGER NOT NULL,
 skipped INTEGER NOT NULL,language_pass INTEGER NOT NULL,min_english REAL NOT NULL,
 input_SHA256 BLOB NOT NULL,prediction_logical_lines_SHA256 BLOB NOT NULL);
CREATE TABLE windows(doc INTEGER NOT NULL,ordinal INTEGER NOT NULL,kind INTEGER NOT NULL,
 start INTEGER NOT NULL,end INTEGER NOT NULL,alphabetics INTEGER NOT NULL,
 raw_SHA256 BLOB NOT NULL,projection_SHA256 BLOB NOT NULL,scored INTEGER NOT NULL,
 skip_reason TEXT,label TEXT,raw_probability TEXT,top_probability REAL,english_probability REAL,
 policy_pass INTEGER,prediction_logical_line TEXT,PRIMARY KEY(doc,ordinal),
 FOREIGN KEY(doc) REFERENCES docs(ordinal)) WITHOUT ROWID;
'''
def preflight(p):
 custody.preflight(p)
 need(p['expected']=={'documents':300,'raw_source_bytes_read':153222386,'UTF8_bytes':147256181,'characters':146292356,'all_windows':143311},'frozen_expected_stats')
 need(len(p['envelopes'])==300 and sum(x['bytes'] for x in p['envelopes'])==147256181 and sum(x['characters'] for x in p['envelopes'])==146292356,'fixed300_payload_metadata')
 need(sum(1+(x['characters']+1023)//1024 for x in p['envelopes'])==143311,'fixed_windows_denominator')
 for e,src in zip(p['envelopes'],p['source_files']):
  need(0<=e['start_byte']<e['end_byte']<=src['bytes'] and e['end_byte']-e['start_byte']==e['bytes']<=2400000,'frozen_payload_span_bounds')
 return True

def prepared(text):
 windows=[];projected_bytes=0
 for meta,chunk in rules.windows(text):
  projection=rules.projection(chunk).encode('utf8');meta={**meta,'raw_SHA256':sha(chunk.encode('utf8')),'projection_SHA256':sha(projection)};windows.append((meta,projection))
  if meta['scored']:projected_bytes+=len(projection)+1
 need(projected_bytes<=8388608,'one_envelope_projection_cap')
 return windows

def diagnostics(text,tokenizer,profile,remaining,check,infer=classify.infer):
 windows=prepared(text);need(len(windows)==1+(len(text)+1023)//1024 and len(windows)<=2345,'exact_whole_chunk_window_coverage')
 content_tokens=len(tokenizer.encode(text,add_special_tokens=False).ids)
 data=b'\n'.join(projection for meta,projection in windows if meta['scored'])+b'\n'
 predictions=infer(profile,data,remaining,check);need(len(predictions)==sum(meta['scored'] for meta,_ in windows),'exact_prediction_coverage')
 rows=[];i=0;english=[];skipped=0
 for ordinal,(meta,projection) in enumerate(windows):
  if meta['scored']:
   line=predictions[i];i+=1;label,prob,top,en,passed=rules.prediction(line);need(len(line)<=160 and len(prob)<=64,'prediction_width');english.append(en);pred=(label,prob,top,en,passed,line)
  else:skipped+=1;pred=(None,None,None,None,None,None)
  rows.append((ordinal,0 if meta['kind']=='whole' else 1,meta['start'],meta['end'],meta['alphabetics'],meta['raw_SHA256'],meta['projection_SHA256'],int(meta['scored']),meta['skip_reason'],*pred))
 need(english and i+skipped==len(windows),'every_window_scored_or_explicit_skip')
 return {'tokens':content_tokens,'rows':rows,'scored':i,'skipped':skipped,'minimum':min(english),'passed':int(min(english)>=.8),'input_SHA256':sha(data),'prediction_lines_SHA256':sha(('\n'.join(predictions)+'\n').encode('utf8'))}

def run(p,out,check,tokenizer=None,infer=classify.infer,remaining=None):
 if tokenizer is None:tokenizer=rules.load_tokenizer(p)
 if remaining is None:raise ValueError('shared_remaining_clock_required')
 out=Path(out);check(16000000)
 with (out/'screening.sqlite').open('xb'):pass
 db=sqlite3.connect(out/'screening.sqlite');stats={'documents':0,'raw_source_bytes_read':0,'UTF8_bytes':0,'characters':0,'M1_content_tokens':0,'all_windows':0,'scored':0,'skipped':0,'language_pass':0};committed=0
 try:
  for pragma in ['page_size=4096','journal_mode=PERSIST','journal_size_limit=16000000','synchronous=FULL','cache_size=-8192','temp_store=MEMORY','foreign_keys=ON','max_page_count='+str(128000000//4096)]:db.execute('PRAGMA '+pragma)
  db.executescript(SCHEMA);db.commit()
  def journal():
   q=out/'screening.sqlite-journal';need(not q.exists() or q.stat().st_size<=16000000,'journal_bound')
  for row,src,e in zip(p['records'],p['source_files'],p['envelopes']):
   check();raw=custody.read_source(p['source_output'],src,check);body=raw[e['start_byte']:e['end_byte']];need(len(body)==e['bytes'] and sha(body).hex()==e['SHA256'],'exact_payload_hash_span');text=body.decode('utf8','strict');need(len(text)==e['characters'],'exact_payload_characters')
   d=diagnostics(text,tokenizer,p,remaining(),check,infer);check(16000000+len(d['rows'])*768);doc=row['ordinal']
   db.execute('INSERT INTO docs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(doc,row['ebook_ID'],bytes.fromhex(src['SHA256']),e['start_byte'],e['end_byte'],sha(body),len(text),len(body),d['tokens'],1,d['scored'],d['skipped'],d['passed'],d['minimum'],d['input_SHA256'],d['prediction_lines_SHA256']))
   for i,w in enumerate(d['rows']):
    db.execute('INSERT INTO windows VALUES('+','.join('?' for _ in range(16))+')',(doc,*w))
    if i%256==0:journal();check()
   journal();check();db.commit();journal();committed+=1
   stats['documents']+=1;stats['raw_source_bytes_read']+=len(raw);stats['UTF8_bytes']+=len(body);stats['characters']+=len(text);stats['M1_content_tokens']+=d['tokens'];stats['all_windows']+=len(d['rows']);stats['scored']+=d['scored'];stats['skipped']+=d['skipped'];stats['language_pass']+=d['passed']
  need(all(stats[k]==v for k,v in p['expected'].items()) and stats['scored']+stats['skipped']==stats['all_windows'],'exact300_final_denominators')
  need(db.execute('PRAGMA integrity_check').fetchone()==('ok',) and not db.execute('PRAGMA foreign_key_check').fetchall(),'SQL_integrity_FK')
  need(db.execute('SELECT count(*) FROM docs').fetchone()==(p['expected']['documents'],) and db.execute('SELECT count(*) FROM windows').fetchone()==(p['expected']['all_windows'],),'SQL_full_denominators')
  bad=db.execute('SELECT text_SHA256 FROM docs GROUP BY text_SHA256 HAVING min(content_tokens)!=max(content_tokens) OR min(language_pass)!=max(language_pass) OR min(characters)!=max(characters) OR min(UTF8_bytes)!=max(UTF8_bytes)').fetchall();need(not bad,'exact_text_alias_diagnostics_disagree')
  distinct=db.execute('SELECT count(*),coalesce(sum(t),0),coalesce(sum(b),0),coalesce(sum(lp),0) FROM (SELECT text_SHA256,min(content_tokens)t,min(UTF8_bytes)b,min(language_pass)lp FROM docs GROUP BY text_SHA256)').fetchone()
  for src in p['source_files']:check();need(custody.identity((Path(p['source_output'])/src['path']).stat(follow_symlinks=False))==src['dev_ino_size_mtime_ns_ctime_ns'],'all_original_sources_final_stat')
  return {'status':'COMPLETE_PG300_ENVELOPE_M1_LANGUAGE_PROVISIONAL_NO_ADMISSION','stats':stats,'one_EOS_per_raw_envelope_separate':stats['documents'],'raw_content_plus_EOS':stats['M1_content_tokens']+stats['documents'],'distinct_envelope_SHA_diagnostic':{'count':distinct[0],'M1_content_tokens':distinct[1],'UTF8_bytes':distinct[2],'language_pass':distinct[3],'arbitrary_representative_chosen':False},'source_lineage_metadata':p['boundary_records_path'],'sources_unchanged':True,'full_text_copies_written':0,'scope':'PG envelopes include print front/end matter/notes. Frozen detector pass is not semantic quality, originality, rights, edition, family/near/protected clearance or final recipe-usable supply. Counts are provisional existing-M1 volume only.','new_admitted_documents':0,'new_admitted_tokens':0}
 except BaseException as exc:
  db.rollback();exc.diagnostic_partial={'committed_documents':committed,'processed_stats_may_include_uncommitted_work':stats};raise
 finally:db.close()
