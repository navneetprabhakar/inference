"""One bounded immutable gzip/JSONL source frame; no text copies or admission."""
import hashlib,json,os,re,sqlite3,zlib,datetime
from pathlib import Path
from urllib.parse import urlsplit

FLAGS={'OVERSIZED_RECORD':1,'MALFORMED_UTF8':2,'MALFORMED_JSON_OR_DUPLICATE_KEY':4,'NONOBJECT':8,'SCHEMA_KEYS_OR_TYPES':16,'SCALAR_OVERFLOW':32,'FAMILY_UNRESOLVED':64,'ID_URL_DIFFER':128,'UNKNOWN_LICENSE_METADATA':256,'SOURCE_NOT_PRESSBOOKS':512,'KNOWN_REVIEW_HOLD':1024,'UNSUPPORTED_DATE_METADATA':2048}
TOP={'id','text','source','added','created','metadata'}
META={'license','url','book_url','title','author','institution','subject'}
COLS=['id','source','added','created','license','url','book_url','title','author','institution','subject']
SCHEMA='''CREATE TABLE records(ordinal INTEGER PRIMARY KEY,line_offset INTEGER NOT NULL,line_bytes INTEGER NOT NULL,ends_LF INTEGER NOT NULL,line_SHA256 BLOB NOT NULL,flags INTEGER NOT NULL,id TEXT,source TEXT,added TEXT,created TEXT,license TEXT,url TEXT,book_url TEXT,title TEXT,author TEXT,institution TEXT,subject TEXT,text_SHA256 BLOB,text_UTF8_bytes INTEGER,text_chars INTEGER,derived_book_root TEXT);'''
def hash(b):return hashlib.sha256(b).digest()
def unique(pairs):
 d={}
 for k,v in pairs:
  if k in d:raise ValueError('duplicate_JSON_key')
  d[k]=v
 return d
def nofloat(value):raise ValueError('nonstandard_JSON_constant')
def family(book,url):
 try:
  b=urlsplit(book);u=urlsplit(url)
  if b.scheme not in ('http','https') or b.username or b.password or not b.hostname or b.hostname!=u.hostname or not u.hostname or 'pressbooks' not in b.hostname:return None
  parts=b.path.split('/');slug=parts[1] if len(parts)>1 else ''
  if not slug or slug in ('chapter','front-matter','back-matter','part') or len(slug)>512:return None
  # Derivation is deliberately a lead, not a canonical/complete-book assertion.
  if len(parts)>2 and parts[2] not in ('','chapter','front-matter','back-matter','part'):return None
  if not u.path.startswith('/'+slug+'/') and u.path!='/'+slug:return None
  return b.scheme+'://'+b.hostname+'/'+slug+'/'
 except (ValueError,TypeError):return None

def _date(value,fmt):
 try:datetime.datetime.strptime(value or '',fmt);return True
 except ValueError:return False

def row(ordinal,offset,n,ends,digest,raw):
 flags=0;values={k:None for k in COLS};textSHA=None;textbytes=None;textchars=None;root=None;reason=[]
 if raw is None:flags|=FLAGS['OVERSIZED_RECORD'];reason.append('oversized_whole_line_hashed_not_parsed')
 else:
  try:s=raw.decode('utf8',errors='strict')
  except UnicodeError:flags|=FLAGS['MALFORMED_UTF8'];s=None
  if s is not None:
   try:obj=json.loads(s,object_pairs_hook=unique,parse_constant=nofloat);parsed=True
   except (ValueError,RecursionError):flags|=FLAGS['MALFORMED_JSON_OR_DUPLICATE_KEY'];obj=None;parsed=False
   if parsed:
    if type(obj) is not dict:flags|=FLAGS['NONOBJECT']
    else:
     md=obj.get('metadata');md=md if type(md) is dict else {}
     if set(obj)!=TOP or set(md)!=META or any(type(obj.get(k)) is not str for k in TOP-{'metadata'}) or any(type(md.get(k)) is not str for k in META):
      flags|=FLAGS['SCHEMA_KEYS_OR_TYPES'];reason.append('schema_keys_or_types:'+hash(json.dumps([list(obj),list(md)],ensure_ascii=True,separators=(',',':')).encode()).hex())
     for k in COLS:
      v=obj.get(k) if k in TOP-{'metadata','text'} else md.get(k)
      if type(v) is str:
       try:size=len(v.encode('utf8',errors='strict'))
       except UnicodeError:flags|=FLAGS['MALFORMED_UTF8'];continue
       if size<=4096:values[k]=v
       else:flags|=FLAGS['SCALAR_OVERFLOW'];reason.append('scalar_overflow:'+k)
     text=obj.get('text')
     if type(text) is str:
      try:encoded=text.encode('utf8',errors='strict');textSHA=hash(encoded);textbytes=len(encoded);textchars=len(text)
      except UnicodeError:flags|=FLAGS['MALFORMED_UTF8']
     try:datetime.datetime.fromisoformat(values['added'] or '')
     except ValueError:flags|=FLAGS['UNSUPPORTED_DATE_METADATA']
     if not any(_date(values['created'],f) for f in ['%m-%d-%Y','%Y-%m-%d']):flags|=FLAGS['UNSUPPORTED_DATE_METADATA']
     if values['source']!='pressbooks':flags|=FLAGS['SOURCE_NOT_PRESSBOOKS']
     if values['id']!=values['url']:flags|=FLAGS['ID_URL_DIFFER']
     root=family(values['book_url'],values['url'])
     if root is None:flags|=FLAGS['FAMILY_UNRESOLVED']
     license=values['license'] or ''
     if re.search(r'https?://creativecommons\.org/(?:licenses/(?:by|by-sa|by-nc|by-nd|by-nc-sa|by-nc-nd)/(?:2\.0|2\.5|3\.0|4\.0)/|publicdomain/(?:zero|mark)/1\.0/)',license) is None:flags|=FLAGS['UNKNOWN_LICENSE_METADATA']
 return (ordinal,offset,n,int(ends),digest,flags,*[values[k] for k in COLS],textSHA,textbytes,textchars,root),reason

class Lines:
 def __init__(self,cap,maximum,callback):self.cap=cap;self.maximum=maximum;self.callback=callback;self.ordinal=0;self.offset=0;self.n=0;self.digest=hashlib.sha256();self.buf=bytearray();self.total=0
 def add(self,data):
  while data:
   if self.ordinal>=self.maximum:raise ValueError('encountered_record_cap_partial_frame')
   end=data.find(b'\n');part=data if end<0 else data[:end+1];data=b'' if end<0 else data[end+1:]
   self.n+=len(part);self.total+=len(part);self.digest.update(part)
   if self.buf is not None:
    if self.n<=self.cap:self.buf.extend(part)
    else:self.buf=None
   if end>=0:self.emit(True)
 def emit(self,ends):
  self.ordinal+=1;raw=bytes(self.buf) if self.buf is not None else None
  self.callback(self.ordinal,self.offset,self.n,ends,self.digest.digest(),raw)
  self.offset+=self.n;self.n=0;self.digest=hashlib.sha256();self.buf=bytearray()
 def finish(self):
  if self.n:self.emit(False)
 def partial(self):return {'consumed_partial_line_offset':self.offset,'consumed_partial_line_bytes':self.n,'consumed_partial_SHA256':self.digest.hexdigest(),'whole_line_hash_claimed':False}

def gzip_stream(read,feed,limits,check):
 pending=b'';d=None;compressed=0;decoded=0;members=0;digest=hashlib.sha256()
 while True:
  check()
  if not pending:
   raw=read(min(65536,limits['compressed_bytes']-compressed+1))
   if raw:
    compressed+=len(raw);digest.update(raw)
    if compressed>limits['compressed_bytes']:raise ValueError('compressed_source_cap')
    pending=raw
   else:
    if d is not None or members==0:raise ValueError('gzip_truncated_missing_CRC_EOF')
    break
  if d is None:
   if len(pending)==1:
    if compressed>=limits['compressed_bytes']:raise ValueError('incomplete_gzip_header_at_compressed_cap')
    extra=read(1);compressed+=len(extra);digest.update(extra);pending+=extra
   if not pending.startswith(b'\x1f\x8b'):raise ValueError('gzip_trailing_or_unknown_member')
   d=zlib.decompressobj(16+zlib.MAX_WBITS)
  if decoded>=limits['decoded_bytes']:raise ValueError('decoded_cap_partial_frame')
  raw=d.decompress(pending,max_length=min(65536,limits['decoded_bytes']-decoded));decoded+=len(raw)
  pending=d.unused_data if d.eof else d.unconsumed_tail
  if raw:feed(raw)
  if d.eof:members+=1;d=None
 return {'compressed_bytes':compressed,'compressed_SHA256':digest.hexdigest(),'decoded_bytes':decoded,'gzip_CRC_EOF_members':members,'trailing_absent':True}

class Sink:
 def __init__(self,path,limits,check,known_holds=()):
  check(8065536);self.known_holds=known_holds;self.path=Path(path);self.limits=limits;self.check=check;self.rows=0;self.committed=0;self.flags={k:0 for k in FLAGS};self.line_digest=hashlib.sha256();self.pending=0;self.exception_bytes=0;self.exception_events=0;self.exception_digest=hashlib.sha256();self.exceptions=(self.path.parent/'schema-holds.jsonl').open('xb')
  self.db=sqlite3.connect(path);self.db.execute('PRAGMA page_size=4096');self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA synchronous=FULL');self.db.execute('PRAGMA cache_size=-4096');self.db.execute('PRAGMA temp_store=MEMORY');self.db.execute('PRAGMA max_page_count='+str(limits['SQLite_bytes']//4096));self.db.executescript(SCHEMA);self.db.commit()
 def accept(self,*args):
  self.check();record,reasons=row(*args);self.rows+=1
  for known in self.known_holds:
   if record[0]==known['source_ordinal']:
    if record[4].hex()!=known['line_SHA256'] or record[6]!=known['id'] or record[17] is None or record[17].hex()!=known['text_SHA256']:raise ValueError('known_review_source_identity_mismatch')
    record=record[:5]+(record[5]|FLAGS['KNOWN_REVIEW_HOLD'],)+record[6:]
  if record[5]&(FLAGS['OVERSIZED_RECORD']|FLAGS['MALFORMED_UTF8']|FLAGS['MALFORMED_JSON_OR_DUPLICATE_KEY']|FLAGS['NONOBJECT']|FLAGS['SCHEMA_KEYS_OR_TYPES']|FLAGS['SCALAR_OVERFLOW']|FLAGS['KNOWN_REVIEW_HOLD']):
   evidence=(json.dumps({'ordinal':record[0],'line_offset':record[1],'line_bytes':record[2],'line_SHA256':record[4].hex(),'flags':record[5],'reasons':reasons},ensure_ascii=True,separators=(',',':'))+'\n').encode()
   if len(evidence)>4096 or self.exception_bytes+len(evidence)>12000000:raise ValueError('schema_exception_output_cap')
   self.check(len(evidence)+8000000);self.exceptions.write(evidence);self.exception_bytes+=len(evidence);self.exception_events+=1;self.exception_digest.update(evidence)
  self.line_digest.update(json.dumps([record[0],record[1],record[2],record[3],record[4].hex()],separators=(',',':')).encode()+b'\n')
  for name,bit in FLAGS.items():self.flags[name]+=int(bool(record[5]&bit))
  # Append-only batches: conservative per-row prewrite growth plus fixed8MB
  # journal/terminal reservation; SQLite itself enforces112MB DB hardlimit.
  cost=16384+sum(len(v.encode()) if isinstance(v,str) else len(v) if isinstance(v,bytes) else 8 for v in record)
  self.check(cost*3+8000000)
  self.db.execute('INSERT INTO records VALUES('+','.join(['?']*len(record))+')',record);self.pending+=1
  if self.pending>=100:self.commit()
 def commit(self):self.check(8000000);self.db.commit();self.committed=self.rows;self.pending=0
 def close(self):
  self.exceptions.flush();os.fsync(self.exceptions.fileno());self.exceptions.close();self.db.close()

def run(profile,out,read,check):
 limits=profile['limits'];sink=Sink(Path(out)/'frame.sqlite',limits,check,profile.get('known_holds',[]));lines=Lines(limits['parsed_record_bytes'],limits['encountered_records'],sink.accept)
 try:
  counts=gzip_stream(read,lines.add,limits,lambda:check());lines.finish();sink.commit()
  if lines.total!=counts['decoded_bytes'] or lines.ordinal!=sink.rows:raise ValueError('all_decoded_line_coverage')
  if counts['compressed_bytes']!=profile['source']['bytes'] or counts['compressed_SHA256']!=profile['source']['SHA256']:raise ValueError('complete_source_publisher_size_SHA256_mismatch')
  if sink.db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('SQLite_integrity')
  totals=sink.db.execute('SELECT count(*),sum(line_bytes),sum(text_UTF8_bytes),sum(text_chars),count(derived_book_root) FROM records').fetchone()
  duplicates={}
  for col in ['id','url','text_SHA256']:
   check();duplicates[col]=sink.db.execute('SELECT count(*),coalesce(sum(n),0) FROM (SELECT count(*) AS n FROM records WHERE '+col+' IS NOT NULL GROUP BY '+col+' HAVING count(*)>1)').fetchone()
  check();derived_roots=sink.db.execute('SELECT count(DISTINCT derived_book_root) FROM records').fetchone()[0]
  return {'status':'COMPLETE_FIRST_SHARD_METADATA_FRAME_NO_ADMISSION','counts':counts,'rows':sink.rows,'committed_rows':sink.committed,'stored_row_line_text_totals':totals,'exact_duplicate_signal_groups_and_occurrences':duplicates,'distinct_derived_book_roots_not_complete_books':derived_roots,'flag_bits':FLAGS,'flag_counts':sink.flags,'ordered_line_locator_SHA256':sink.line_digest.hexdigest(),'schema_exceptions':{'events':sink.exception_events,'bytes':sink.exception_bytes,'ordered_SHA256':sink.exception_digest.hexdigest()},'source_scope':'FIRST_OF_TWO_SHARDS_ONLY; rows not usable documents/books/English/tokens.','derived_family_scope':'Candidate PressBooks root leads, not complete books or cross-source ownership proof.','new_admitted_documents':0,'new_admitted_tokens':0}
 except BaseException as e:
  sink.db.rollback()
  e.inventory_partial={'rows_encountered':sink.rows,'committed_rows':sink.committed,**lines.partial(),'scope':'PARTIAL_FIRST_SHARD_NO_RETRY_NOT_FULL_FRAME'}
  raise
 finally:sink.close()
