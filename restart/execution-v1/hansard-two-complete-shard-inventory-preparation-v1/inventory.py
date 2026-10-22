"""Metadata only; two complete Hansard shards, no utterance/family inference."""
import hashlib,json,os,re,sqlite3,datetime
from pathlib import Path
from stream_core import Lines,gzip_stream
FLAGS={'OVERSIZED_RECORD':1,'MALFORMED_UTF8':2,'MALFORMED_JSON_OR_DUPLICATE_KEY':4,'NONOBJECT':8,'SCHEMA_KEYS_OR_TYPES':16,'SCALAR_OVERFLOW':32,'UNSUPPORTED_ADDED_DATE':64,'UNRECOGNIZED_SOURCE_METADATA':128,'UNSUPPORTED_YEAR_METADATA':256}
TOP={'id','text','source','added','metadata'};META={'language','license','year'};COLS=['id','source','added','year','language','license']
SCHEMA='''CREATE TABLE sources(source_id INTEGER PRIMARY KEY,path TEXT NOT NULL,SHA256 TEXT NOT NULL,bytes INTEGER NOT NULL);CREATE TABLE records(source_id INTEGER NOT NULL,ordinal INTEGER NOT NULL,line_offset INTEGER NOT NULL,line_bytes INTEGER NOT NULL,ends_LF INTEGER NOT NULL,line_SHA256 BLOB NOT NULL CHECK(length(line_SHA256)=32),flags INTEGER NOT NULL,id TEXT,source TEXT,added TEXT,year TEXT,language TEXT,license TEXT,text_SHA256 BLOB,text_UTF8_bytes INTEGER,text_chars INTEGER,PRIMARY KEY(source_id,ordinal),FOREIGN KEY(source_id)REFERENCES sources(source_id)) WITHOUT ROWID;'''
def unique(pairs):
 out={}
 for k,v in pairs:
  if k in out:raise ValueError('duplicate_JSON_key')
  out[k]=v
 return out
def row(sid,ordinal,offset,n,ends,digest,raw):
 flags=0;values={k:None for k in COLS};textSHA=None;textbytes=None;textchars=None;reasons=[]
 if raw is None:flags|=1;reasons.append('whole_oversize_line_hashed_not_parsed')
 else:
  try:s=raw.decode('utf8','strict')
  except UnicodeError:flags|=2;s=None
  if s is not None:
   try:obj=json.loads(s,object_pairs_hook=unique,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite')));parsed=True
   except (ValueError,RecursionError):flags|=4;parsed=False;obj=None
   if parsed:
    if type(obj) is not dict:flags|=8
    else:
     md=obj.get('metadata');md=md if type(md) is dict else {}
     if set(obj)!=TOP or set(md)!=META or any(type(obj.get(k)) is not str for k in TOP-{'metadata'}) or any(type(md.get(k)) is not str for k in META):
      flags|=16
      # Exact unknown values remain source-backed by rawline locator/hash; descriptors bounded below.
      desc=json.dumps({'top':{k:type(v).__name__ for k,v in obj.items()},'metadata':{k:type(v).__name__ for k,v in md.items()}},ensure_ascii=True,sort_keys=True,separators=(',',':')).encode()
      reasons.append('schema_descriptor_SHA256:'+hashlib.sha256(desc).hexdigest())
      if len(desc)<=2048:reasons.append(desc.decode())
      else:reasons.append('descriptor_exceeds2048_source_line_retained_in_original_gzip')
     for k in COLS:
      v=obj.get(k) if k in TOP else md.get(k)
      if type(v) is str:
       try:b=v.encode('utf8','strict')
       except UnicodeError:flags|=2;continue
       if len(b)<=4096:values[k]=v
       else:flags|=32;reasons.append('scalar_overflow:'+k+':'+str(len(b))+':'+hashlib.sha256(b).hexdigest())
     text=obj.get('text')
     if type(text) is str:
      try:b=text.encode('utf8','strict');textSHA=hashlib.sha256(b).digest();textbytes=len(b);textchars=len(text)
      except UnicodeError:flags|=2
     try:datetime.date.fromisoformat(values['added'] or '')
     except ValueError:flags|=64
     if not values['source'] or not values['source'].startswith('uk-hansard-'):flags|=128
     if re.fullmatch('[0-9]{4}',values['year'] or '') is None:flags|=256
 return (sid,ordinal,offset,n,int(ends),digest,flags,*[values[k] for k in COLS],textSHA,textbytes,textchars),reasons
class Sink:
 def __init__(self,path,limits,check,inputs):
  check(8065536);self.path=Path(path);self.check=check;self.rows=0;self.committed=0;self.pending=0;self.flags={k:0 for k in FLAGS};self.digest=hashlib.sha256();self.ex_bytes=0;self.ex_events=0;self.ex_digest=hashlib.sha256();self.exceptions=(self.path.parent/'schema-holds.jsonl').open('xb');self.db=sqlite3.connect(path)
  for q in ['page_size=4096','journal_mode=PERSIST','journal_size_limit=8000000','synchronous=FULL','foreign_keys=ON','cache_size=-4096','temp_store=MEMORY','max_page_count='+str(limits['SQLite_bytes']//4096)]:self.db.execute('PRAGMA '+q)
  self.db.executescript(SCHEMA)
  for b in inputs:self.db.execute('INSERT INTO sources VALUES(?,?,?,?)',(b['source_id'],b['path'],b['SHA256'],b['bytes']))
  self.db.commit()
 def accept(self,sid,*args):
  self.check();r,reasons=row(sid,*args);self.rows+=1
  if r[6]:
   evidence=(json.dumps({'source_id':sid,'ordinal':r[1],'line_offset':r[2],'line_bytes':r[3],'line_SHA256':r[5].hex(),'flags':r[6],'reasons':reasons},ensure_ascii=True,separators=(',',':'))+'\n').encode()
   if len(evidence)>4096 or self.ex_bytes+len(evidence)>64000000:raise ValueError('exception_cap64MB_partial')
   self.check(len(evidence)+8000000);self.exceptions.write(evidence);self.ex_bytes+=len(evidence);self.ex_events+=1;self.ex_digest.update(evidence)
  for name,bit in FLAGS.items():self.flags[name]+=bool(r[6]&bit)
  self.digest.update(json.dumps([*r[:5],r[5].hex()],separators=(',',':')).encode()+b'\n')
  cost=16384+sum(len(v.encode()) if isinstance(v,str) else len(v) if isinstance(v,bytes) else 8 for v in r);self.check(cost*3+8000000)
  self.db.execute('INSERT INTO records VALUES('+','.join('?'*len(r))+')',r);self.pending+=1
  if self.path.with_name(self.path.name+'-journal').stat().st_size>8000000:raise ValueError('journal8MB_cap')
  if self.pending>=100:self.commit()
 def commit(self):self.check(8000000);self.db.commit();self.committed=self.rows;self.pending=0
 def close(self):self.exceptions.flush();os.fsync(self.exceptions.fileno());self.exceptions.close();self.db.close()
def run(profile,out,open_source,check):
 limits=profile['limits'];sink=Sink(Path(out)/'frame.sqlite',limits,check,profile['inputs']);counts=[];decoded=0;rows=0;compressed=0;current=None
 try:
  for binding in profile['inputs']:
   sid=binding['source_id'];lines=Lines(limits['parsed_record_bytes'],limits['encountered_records']-rows,lambda *a:sink.accept(sid,*a));current=lines
   local={'compressed_bytes':binding['bytes'],'decoded_bytes':limits['decoded_bytes']-decoded}
   with open_source(binding,lambda:check()) as read:count=gzip_stream(read,lines.add,local,lambda:check())
   lines.finish()
   if count['compressed_bytes']!=binding['bytes'] or count['compressed_SHA256']!=binding['SHA256']:raise ValueError('full_source_SHA256_size_mismatch')
   if lines.total!=count['decoded_bytes']:raise ValueError('all_line_coverage')
   decoded+=count['decoded_bytes'];rows+=lines.ordinal;compressed+=count['compressed_bytes'];sink.commit();counts.append({'source_id':sid,'rows':lines.ordinal,**count})
  if rows!=sink.rows or decoded!=sink.db.execute('SELECT sum(line_bytes) FROM records').fetchone()[0]:raise ValueError('complete_two_source_coverage')
  if sink.db.execute('PRAGMA integrity_check').fetchone()!=('ok',) or sink.db.execute('PRAGMA foreign_key_check').fetchone() is not None:raise ValueError('SQL_integrity')
  totals=sink.db.execute('SELECT count(*),sum(line_bytes),sum(text_UTF8_bytes),sum(text_chars) FROM records').fetchone()
  return {'status':'COMPLETE_TWO_VERIFIED_SHARD_HANSARD_METADATA_FRAME_NO_ADMISSION','counts':counts,'rows':rows,'committed_rows':sink.committed,'decoded_total_bytes':decoded,'compressed_total_bytes':compressed,'stored_row_line_text_totals':totals,'flag_bits':FLAGS,'flag_counts':sink.flags,'ordered_line_locator_SHA256':sink.digest.hexdigest(),'schema_exceptions':{'events':sink.ex_events,'bytes':sink.ex_bytes,'ordered_SHA256':sink.ex_digest.hexdigest()},'scope':'TWO_COMPLETED_SHARDS_ONLY_OF_FAILED_ELEVEN_SHARD_ACQUISITION; physical records not speeches, sessions, English, usable units or confirmed families. No guessed grouping/canonical pick.','SQLite_journal_mode':'PERSIST','journal_reserve_bytes':8000000,'new_admitted_documents':0,'new_admitted_tokens':0}
 except BaseException as e:
  sink.db.rollback();e.inventory_partial={'rows_encountered':sink.rows,'committed_rows':sink.committed,'completed_sources':counts,'current_source_partial':current.partial() if current else None};raise
 finally:sink.close()
