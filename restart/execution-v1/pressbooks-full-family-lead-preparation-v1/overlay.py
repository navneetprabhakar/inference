"""All two-shard metadata rows, URL-pair interning and additive LEAD/identity holds."""
import contextlib,hashlib,json,os,sqlite3,stat
from pathlib import Path
from derive import derive,STATUS
HOLD={'CONFLICTING_SAME_ID_TEXT':1,'EXACT_KNOWN_CATALOG_ID_TEXT':2,'EXACT_KNOWN_CATALOG_TEXT_CONTENT':4}
SCHEMA='''CREATE TABLE sources(source_id INTEGER PRIMARY KEY,path TEXT NOT NULL,inherited_SHA256 TEXT NOT NULL,stat_json TEXT NOT NULL,rows INTEGER NOT NULL);
CREATE TABLE strings(string_id INTEGER PRIMARY KEY,value TEXT NOT NULL UNIQUE);
CREATE TABLE rows(source_id INTEGER NOT NULL,ordinal INTEGER NOT NULL,line_offset INTEGER NOT NULL,line_bytes INTEGER NOT NULL,ends_LF INTEGER NOT NULL,line_SHA256 BLOB NOT NULL CHECK(length(line_SHA256)=32),text_SHA256 BLOB NOT NULL CHECK(length(text_SHA256)=32),text_UTF8_bytes INTEGER NOT NULL,existing_flags INTEGER NOT NULL,id_id INTEGER,url_id INTEGER,book_url_id INTEGER,url_pair_SHA256 BLOB NOT NULL CHECK(length(url_pair_SHA256)=32),lead_status INTEGER NOT NULL,lead_root_id INTEGER,identity_holds INTEGER NOT NULL,ancestry_status INTEGER NOT NULL DEFAULT0,split_status INTEGER NOT NULL DEFAULT0,rights_status INTEGER NOT NULL DEFAULT0,PRIMARY KEY(source_id,ordinal),FOREIGN KEY(source_id)REFERENCES sources(source_id),FOREIGN KEY(id_id)REFERENCES strings(string_id),FOREIGN KEY(url_id)REFERENCES strings(string_id),FOREIGN KEY(book_url_id)REFERENCES strings(string_id),FOREIGN KEY(lead_root_id)REFERENCES strings(string_id)) WITHOUT ROWID;'''.replace('DEFAULT0','DEFAULT 0')
def ident(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def hash(b):return hashlib.sha256(b).digest()
def transcript(x):return (json.dumps(x,ensure_ascii=False,separators=(',',':'))+'\n').encode()
@contextlib.contextmanager
def frames(profile,check):
 opened=[]
 try:
  for binding in profile['inputs']:
   p=Path(binding['path']);expected=binding['stat']
   if p.is_symlink() or str(p.resolve())!=str(p) or ident(p.stat())!=expected:raise ValueError('input_path_stat')
   fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
   if ident(os.fstat(fd))!=expected or not stat.S_ISREG(os.fstat(fd).st_mode):os.close(fd);raise ValueError('input_FD_stat')
   db=None
   try:
    db=sqlite3.connect(p.as_uri()+'?mode=ro&immutable=1',uri=True)
    for pragma in ['query_only=ON','cache_size=-4096','temp_store=MEMORY','mmap_size=0']:db.execute('PRAGMA '+pragma)
    db.set_progress_handler(lambda:(check() or 0),10000);opened.append((binding,p,fd,db));check()
   except BaseException:
    if not any(item[2]==fd for item in opened):
     if db is not None:db.close()
     os.close(fd)
    raise
  def custody():
   for binding,p,fd,db in opened:
    if p.is_symlink() or ident(p.stat())!=binding['stat'] or ident(os.fstat(fd))!=binding['stat']:raise ValueError('input_changed')
  custody();yield opened,custody;custody()
 finally:
  for binding,p,fd,db in opened:db.close();os.close(fd)

def run(profile,out,check):
 out=Path(out);check(5000000);db=sqlite3.connect(out/'leads.sqlite');db.execute('PRAGMA page_size=4096');db.execute('PRAGMA journal_mode=PERSIST');db.execute('PRAGMA journal_size_limit=4000000');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA temp_store=MEMORY');db.execute('PRAGMA cache_size=-4096');db.execute('PRAGMA max_page_count='+str(profile['limits']['DB_bytes']//4096));db.executescript(SCHEMA);db.commit()
 totals=0;committed=0;counts={};holdcounts={k:0 for k in HOLD};sourceflag64=0;line_digest=hashlib.sha256();url_digest=hashlib.sha256();pending=0;seen_conflicts=set();catalog_seen=[];catalog_content_seen=[]
 conflictmap={(r['source_id'],r['ordinal']):r for r in profile['conflicting_identity_holds']};conflict_ids={r['id'] for r in profile['conflicting_identity_holds']};known=profile['cross_source_catalog_hold']
 def intern(value):
  if value is None:return None
  if type(value) is not str or len(value.encode('utf8'))>4096:raise ValueError('bounded_raw_URL_scalar')
  db.execute('INSERT INTO strings(value)VALUES(?)ON CONFLICT(value)DO NOTHING',(value,));return db.execute('SELECT string_id FROM strings WHERE value=?',(value,)).fetchone()[0]
 def commit(custody):
  nonlocal committed,pending
  check(5000000);custody();db.commit();committed=totals;pending=0
 try:
  with frames(profile,lambda:check()) as (sources,custody):
   for binding,path,fd,source in sources:
    sid=binding['source_id'];db.execute('INSERT INTO sources VALUES(?,?,?,?,?)',(sid,str(path),binding['SHA256'],json.dumps(binding['stat']),binding['rows']));count=0
    cursor=source.execute('SELECT ordinal,line_offset,line_bytes,ends_LF,line_SHA256,text_SHA256,text_UTF8_bytes,flags,id,url,book_url FROM records ORDER BY ordinal')
    for ordinal,off,n,lf,rawSHA,textSHA,textbytes,oldflags,id,url,book in cursor:
     check();count+=1
     if ordinal!=count or type(off)is not int or off<0 or type(n)is not int or n<=0 or lf not in (0,1) or not isinstance(rawSHA,bytes) or len(rawSHA)!=32 or not isinstance(textSHA,bytes) or len(textSHA)!=32 or type(oldflags)is not int or oldflags<0 or type(textbytes)is not int or textbytes<0:raise ValueError('source_exact_metadata_row_fields')
     identity=0;key=(sid,ordinal);expected=conflictmap.get(key)
     if id in conflict_ids:
      if expected is None or expected['id']!=id or expected['line_SHA256']!=rawSHA.hex() or expected['text_SHA256']!=textSHA.hex():raise ValueError('conflicting_identity_binding_drift')
      identity|=HOLD['CONFLICTING_SAME_ID_TEXT'];seen_conflicts.add(key);holdcounts['CONFLICTING_SAME_ID_TEXT']+=1
     if textSHA.hex()==known['text_SHA256']:
      if len(catalog_content_seen)>=profile['expected_catalog_content_occurrences']:raise ValueError('catalog_content_frozen_occurrence_bound')
      evidence={'source_id':sid,'ordinal':ordinal,'line_SHA256':rawSHA.hex(),'text_SHA256':textSHA.hex(),'id':id};identity|=HOLD['EXACT_KNOWN_CATALOG_TEXT_CONTENT'];holdcounts['EXACT_KNOWN_CATALOG_TEXT_CONTENT']+=1;catalog_content_seen.append(evidence)
      if id==known['id']:
       if len(catalog_seen)>=profile['expected_catalog_occurrences']:raise ValueError('catalog_exact_pair_frozen_occurrence_bound')
       identity|=HOLD['EXACT_KNOWN_CATALOG_ID_TEXT'];holdcounts['EXACT_KNOWN_CATALOG_ID_TEXT']+=1;catalog_seen.append(evidence)
     status,root=derive(book,url);counts[status]=counts.get(status,0)+1;sourceflag64+=int(bool(oldflags&64));pair=hash(transcript([id,url,book]));check(5000000+3*(sum(len(v.encode()) for v in [id,url,book,root] if isinstance(v,str))+2048))
     idid,urlid,bookid,rootid=[intern(v) for v in [id,url,book,root]]
     db.execute('INSERT INTO rows VALUES('+','.join(['?']*19)+')',(sid,ordinal,off,n,lf,rawSHA,textSHA,textbytes,oldflags,idid,urlid,bookid,pair,status,rootid,identity,0,0,0));totals+=1;pending+=1
     line_digest.update(transcript([sid,ordinal,off,n,lf,rawSHA.hex(),textSHA.hex(),oldflags]));url_digest.update(transcript([sid,ordinal,id,url,book,pair.hex()]))
     journal=out/'leads.sqlite-journal'
     if journal.stat().st_size>4000000:raise ValueError('journal4MB_reserve')
     if pending>=100:commit(custody)
    if count!=binding['rows']:raise ValueError('complete_source_frame_row_count')
   if totals!=profile['expected_rows'] or sourceflag64!=profile['expected_original_family_unresolved'] or seen_conflicts!=set(conflictmap) or catalog_seen!=profile['expected_catalog_bindings'] or catalog_content_seen!=profile['expected_catalog_content_bindings']:raise ValueError('full_union_exact_identity_hold_coverage')
   commit(custody)
   if db.execute('PRAGMA integrity_check').fetchone()!=('ok',) or db.execute('PRAGMA foreign_key_check').fetchone() is not None:raise ValueError('output_integrity_FK')
   if db.execute('SELECT count(*) FROM rows WHERE ancestry_status!=0 OR split_status!=0 OR rights_status!=0').fetchone()!=(0,):raise ValueError('all_ancestry_split_rights_uncleared')
   result={'status':'COMPLETE_TWO_SHARD_ADDITIVE_STRUCTURAL_LEADS_NO_ADMISSION','raw_metadata_rows':totals,'committed_rows':committed,'lead_status_codes':STATUS,'lead_status_counts':counts,'identity_hold_bits':HOLD,'identity_hold_counts':holdcounts,'catalog_exact_ID_text_occurrences':catalog_seen,'catalog_exact_content_occurrences':catalog_content_seen,'original_FAMILY_UNRESOLVED_flags_preserved':sourceflag64,'all_ancestry_split_rights_status':'UNCLEARED_CODE0','ordered_raw_line_bindings_SHA256':line_digest.hexdigest(),'ordered_exact_URL_pair_bindings_SHA256':url_digest.hexdigest(),'strings':db.execute('SELECT count(*) FROM strings').fetchone()[0],'scope':'Raw URL pairs stored losslessly via bijective string interning. LEADS do not clear family/ancestry/split/rights/quality; no canonical choice or document/text removal.','new_admitted_documents':0,'new_admitted_tokens':0}
   custody();return result
 except BaseException as error:
  db.rollback();error.overlay_partial={'rows_seen':totals,'committed_rows':committed,'status':'PARTIAL_NO_RETRY_NOT_FULL_UNION'};raise
 finally:db.close()
