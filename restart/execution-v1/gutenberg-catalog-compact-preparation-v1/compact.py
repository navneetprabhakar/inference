"""OFFLINE ONLY lossless compact catalog inventory. No downloader/ledger APIs.
Original compressed archive and terminal failed run are read only inputs.
"""
import argparse,hashlib,json,os,platform,re,shutil,signal,sqlite3,subprocess,sys,time,zlib
from pathlib import Path
from lxml import etree
import archive_reader,parse_rdf
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;ROOT=EXEC/'m2-intake'
READER_DIR=EXEC/'wikibooks-identity-frame-preparation-v1';sys.path.insert(0,str(READER_DIR))
from inventory import terminal_write
from supervisor import tree_rss_from_ps
PROFILE=HERE/'profile.json';PROFILE_SHA='1fd5d46862a5fbb6c753ba6c3c1ca9549d057477cc999b90827414aaf8b6d636';MANIFEST=HERE/'manifest.json'
ORIGINAL=ROOT/'gutenberg-complete-native-catalog-v1';ARCHIVE=ORIGINAL/'rdf-files.tar.bz2';ARCHIVE_SHA='93988fc1c6e4171e41dab67f8f21cbcd0b2babde99c659acfacc9ce58150db38'
DEST=ROOT/'gutenberg-complete-native-catalog-compact-v1';OUTPUT_CAP=1000000000;DB_CAP=400000000;HEADROOM=32000000;TERMINAL=1048576;DECODED_CAP=4000000000;WORKER_SECONDS=570;EXTERNAL_SECONDS=600;RSS_CAP=1000000000;RAW_JSON_CAP=16000000
CODEC='lossless-json-zlib-v1;level=6;runtime='+zlib.ZLIB_RUNTIME_VERSION

def sha(b):return hashlib.sha256(b).hexdigest()
def clock():return time.clock_gettime(time.CLOCK_MONOTONIC)
def file_sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def size(root):return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
def environment():return {'python':sys.version,'executable':str(Path(sys.executable).resolve()),'sqlite':sqlite3.sqlite_version,'zlib_runtime':zlib.ZLIB_RUNTIME_VERSION,'zlib_build':zlib.ZLIB_VERSION,'lxml':list(etree.LXML_VERSION),'platform':platform.platform()}
def bound_paths():return [HERE/'compact.py',HERE/'archive_reader.py',HERE/'parse_rdf.py',HERE/'check_offline.py',PROFILE,EXEC/'gutenberg-catalog-preparation-v1/catalog.py',EXEC/'gutenberg-catalog-preparation-v1/parse_rdf.py',EXEC/'gutenberg-catalog-preparation-v1/profile.json',EXEC/'gutenberg-catalog-preparation-v1/manifest.json',EXEC/'gutenberg-catalog-verification-v1/independent-terminal-verification.json',ORIGINAL/'worker-result.json',ORIGINAL/'supervisor-result.json',ORIGINAL/'transfer-receipt.json',ORIGINAL/'catalog.sqlite3',ARCHIVE,READER_DIR/'inventory.py',READER_DIR/'supervisor.py',READER_DIR/'shared_clock.py',EXEC/'disk-budget.json']
def pins(expected):
 if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected) or MANIFEST.is_symlink() or not MANIFEST.is_file():raise ValueError('Explicit parent reviewed manifest digest required')
 if file_sha(MANIFEST)!=expected:raise ValueError('Parent manifest SHA mismatch')
 manifest=json.loads(MANIFEST.read_text());files=manifest.get('files_SHA256',{})
 if set(files)!={str(p.resolve()) for p in bound_paths()} or manifest.get('environment')!=environment():raise ValueError('Exact offline input/dependency inventory and runtime required')
 for name,h in files.items():
  p=Path(name)
  if p.is_symlink() or not p.is_file() or file_sha(p)!=h:raise ValueError('Pinned offline source changed:'+name)
 if file_sha(PROFILE)!=PROFILE_SHA or ARCHIVE.stat().st_size!=126801976 or file_sha(ARCHIVE)!=ARCHIVE_SHA:raise ValueError('Exact source/profile identity required')
 return manifest

class Guards:
 def __init__(self,output,start,limits=None,reserve=None):self.output=output;self.start=start;self.limits=limits or {'decoded_bytes':DECODED_CAP};self.reserve=reserve
 def check(self,additional=0):
  if not 0<=clock()-self.start<WORKER_SECONDS:raise TimeoutError('Offline shared worker deadline')
  if additional<0 or size(self.output)+additional>OUTPUT_CAP-TERMINAL-HEADROOM:raise ValueError('Output prewrite bound including32MB journal/cache headroom')
  db=self.output/'catalog.sqlite3'
  if db.exists() and db.stat().st_size>DB_CAP:raise ValueError('Database400MB hard bound')
  if self.reserve is not None and shutil.disk_usage(self.output).free<self.reserve+additional+HEADROOM:raise ValueError('Protected weights/scratch/freefloor')
def storage():
 p=json.loads((EXEC/'disk-budget.json').read_text());reserve=p['weights_checkpoints_reserved_bytes']+p['scratch_cap_bytes']+p['free_disk_floor_bytes']
 if size(ROOT)+OUTPUT_CAP>p['processed_data_cap_bytes']:raise ValueError('Combined64GB processed ceiling')
 if shutil.disk_usage(ROOT).free<reserve+OUTPUT_CAP:raise ValueError('Preflight weights/scratch/freefloor')
 return reserve

def pack(value):
 raw=json.dumps(value,ensure_ascii=True,separators=(',',':')).encode('utf-8')
 if len(raw)>RAW_JSON_CAP:raise ValueError('Lossless record JSON bound')
 compressed=zlib.compress(raw,level=6)
 return (len(raw),sha(raw),sha(compressed),CODEC,compressed)
def unpack(rawbytes,rawhash,compressedhash,codec,blob):
 if codec!=CODEC or not isinstance(rawbytes,int) or not 0<=rawbytes<=RAW_JSON_CAP:raise ValueError('Unexpected codec/rawlength')
 if sha(blob)!=compressedhash:raise ValueError('Compressed payload hash mismatch')
 decoder=zlib.decompressobj();raw=decoder.decompress(blob,rawbytes+1)
 if len(raw)!=rawbytes or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail or sha(raw)!=rawhash:raise ValueError('LosslessJSON rawhash/length/stream mismatch')
 return json.loads(raw)
def indexes(row):
 creators=[p for p in row['contributors_and_all_roles'] if p['role_qualified_name']=='{'+parse_rdf.DCT+'}creator']
 missing={'languages':not row['languages'],'types':not row['types'],'formats':not row['formats'],'subjects':not row['subjects'],'contributors':not row['contributors_and_all_roles'],'titles':not row['titles'],'primary_creator':not creators,'creator_birthdate':not creators or any(not p['birthdates'] for p in creators),'creator_deathdate':not creators or any(not p['deathdates'] for p in creators)}
 mask=sum((1<<i) for i,v in enumerate(missing.values()) if v)
 return (int(row['metadata_English_Text_view']),json.dumps(row['types'],separators=(',',':')),json.dumps(row['languages'],separators=(',',':')),mask,json.dumps(missing,separators=(',',':')),len(row['holds']))
def save(name,data,guard):
 b=data if isinstance(data,bytes) else (json.dumps(data,indent=2)+'\n').encode();guard.check(len(b))
 with (guard.output/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())

def inventory(archive,guard):
 path=guard.output/'catalog.sqlite3';guard.check(131072);os.environ['SQLITE_TMPDIR']=str(guard.output);db=sqlite3.connect(path)
 db.execute('pragma page_size=4096');db.execute('pragma journal_mode=DELETE');db.execute('pragma synchronous=FULL');db.execute('pragma cache_size=-4096');db.execute('pragma temp_store=FILE');pagebound=DB_CAP//4096;db.execute('pragma max_page_count='+str(pagebound))
 db.execute('create table members(ordinal integer primary key,name text,bytes integer,body_hash text,hold text,raw_bytes integer,raw_hash text,packed_hash text,codec text,payload blob)')
 db.execute('create table records(member integer primary key,ebook_ID integer,English_Text integer,types text,languages text,missing_mask integer,missingness text,hold_count integer,raw_bytes integer,raw_hash text,packed_hash text,codec text,payload blob)')
 db.execute('create index ebook_identity on records(ebook_ID)');db.execute('create index English_type_discovery on records(English_Text,types,missing_mask)');db.commit()
 stats={'members':0,'RDF_members':0,'parsed_ebook_records':0,'held_potential_records':0,'directories':0,'nonRDF_files':0,'member_body_bytes':0,'actual_decoded_tar_bytes':0,'full_tar_EOF_verified':False,'full_bzip2_CRC_EOF_verified':False,'lossless_record_roundtrips':0}
 try:
  for member in archive_reader.tar_members(archive,guard,stats):
   raw=member.pop('raw');row=None;hold=member['hold']
   if member['kind']=='directory':stats['directories']+=1
   elif member['name'].endswith('.rdf'):
    stats['RDF_members']+=1
    if raw is not None:
     try:row=parse_rdf.parse(raw,member['name'])
     except Exception as error:hold='invalid_or_unknown_RDF:'+type(error).__name__+':'+str(error)[:400]
    if row is None:stats['held_potential_records']+=1
   else:stats['nonRDF_files']+=1;hold='non_RDF_member_not_ebook_metadata'
   member['hold']=hold;packed_member=pack(member)
   if unpack(*packed_member)!=member:raise ValueError('Member lossless roundtrip')
   packed_row=pack(row) if row is not None else None
   if packed_row and unpack(*packed_row)!=row:raise ValueError('Record lossless roundtrip')
   extra=8*(len(packed_member[-1])+(len(packed_row[-1]) if packed_row else 0))+131072;guard.check(extra)
   db.execute('insert into members values(?,?,?,?,?,?,?,?,?,?)',(member['ordinal'],member['name'],member['size'],member['body_SHA256'],hold,*packed_member))
   if row is not None:
    db.execute('insert into records values(?,?,?,?,?,?,?,?,?,?,?,?,?)',(member['ordinal'],row['ebook_ID'],*indexes(row),*packed_row));stats['parsed_ebook_records']+=1;stats['lossless_record_roundtrips']+=1
   if stats['members']%100==0:db.commit();guard.check()
  db.commit();guard.check()
  if not stats['full_tar_EOF_verified'] or not stats['full_bzip2_CRC_EOF_verified']:raise ValueError('Full source archive EOF required')
  n,total=db.execute('select count(*),sum(bytes) from members').fetchone();records=db.execute('select count(*) from records').fetchone()[0]
  if n!=stats['members'] or (total or 0)!=stats['member_body_bytes'] or records!=stats['parsed_ebook_records']:raise ValueError('Complete frame member/record/byte reconciliation')
  duplicate_ids=[x[0] for x in db.execute('select ebook_ID from records group by ebook_ID having count(*)>1')]
  for eid in duplicate_ids:
   for record in list(db.execute('select member,raw_bytes,raw_hash,packed_hash,codec,payload from records where ebook_ID=?',(eid,))):
    member=record[0];row=unpack(*record[1:]);row['holds']=sorted(set(row['holds']+['duplicate_native_ebook_ID_in_catalog_requires_family_reconciliation']));packed=pack(row);guard.check(8*len(packed[-1])+131072)
    db.execute('update records set hold_count=?,raw_bytes=?,raw_hash=?,packed_hash=?,codec=?,payload=? where member=?',(len(row['holds']),*packed,member))
  db.commit();guard.check();stats['duplicate_ebook_ID_groups']=len(duplicate_ids)
  db.set_progress_handler(lambda:1 if clock()-guard.start>=WORKER_SECONDS else 0,10000)
  if db.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failure')
  stats['SQLite_integrity']='ok';stats['archive_identity_inventory_complete']=True;stats['all_potential_RDF_records_parsed_without_duplicate_ID']=stats['held_potential_records']==0 and not duplicate_ids and stats['nonRDF_files']==0
  stats['English_Text_metadata_rows']=db.execute('select count(*) from records where English_Text=1').fetchone()[0]
  stats['rows_with_metadata_holds']=db.execute('select count(*) from records where hold_count>0').fetchone()[0]
  stats['rows_with_missing_language_metadata']=db.execute('select count(*) from records where missing_mask & 1 !=0').fetchone()[0]
  stats['rows_with_missing_type_metadata']=db.execute('select count(*) from records where missing_mask & 2 !=0').fetchone()[0]
  stats['database_bytes']=path.stat().st_size;stats['SQLite_max_page_count']=pagebound;stats['codec']=CODEC;stats['no_originalEnglish_or_rights_clearance']=True
  return stats
 finally:db.commit();db.close()

def worker(expected):
 pins(expected)
 if os.getppid()!=int(os.environ['PGCOMPACT_PARENT_PID']):raise ValueError('Live direct supervisor required')
 start=float(os.environ['PGCOMPACT_SHARED_START']);guard=Guards(DEST,start)
 try:
  terminal_write(DEST/'worker-result.json',{'status':'RUNNING_NOT_COMPLETE'},OUTPUT_CAP);guard.reserve=storage();guard.check()
  save('preflight.json',{'manifest_SHA256':expected,'profile_SHA256':PROFILE_SHA,'readonly_original_archive':str(ARCHIVE),'source_archive_bytes':126801976,'source_archive_SHA256':ARCHIVE_SHA,'no_network_or_ledger_API_imports':True,'codec':CODEC,'database_hard_bytes':DB_CAP,'prewrite_headroom_bytes':HEADROOM},guard)
  stats=inventory(ARCHIVE,guard);guard.check()
  result={'status':'COMPLETE_LOSSLESS_COMPACT_CATALOG_METADATA_ONLY_NO_ADMISSION','manifest_SHA256':expected,'profile_SHA256':PROFILE_SHA,'source_archive_SHA256':ARCHIVE_SHA,'source_archive_referenced_not_copied':True,'stats':stats,'database_SHA256':file_sha(DEST/'catalog.sqlite3'),'elapsed_seconds':clock()-start,'network_requests':0,'ledger_mutations':0,'book_bodies_fetched':0,'new_admitted_documents':0,'new_admitted_tokens':0,'models_initialized':0,'metadata_fields_dropped':0,'limitations':['Native metadata language/type and author dates do not establish originalEnglish, editionrights, narrativequality, dedup/protected/split/token counts.','No summaries become prose; every originalmetadatafield remains in losslessJSON.','Anyunknown/unparsed/duplicate records remain explicitheld evidence; completearchiveidentity distinct from selectioncoverage.']}
  guard.check();terminal_write(DEST/'worker-result.json',result,OUTPUT_CAP)
 except BaseException as error:
  terminal_write(DEST/'worker-result.json',{'status':'TERMINAL_OFFLINE_COMPACT_FAILED_NO_RETRY','error':str(error),'elapsed_seconds':clock()-start,'network_requests':0,'ledger_mutations':0,'new_admitted_documents':0,'new_admitted_tokens':0},OUTPUT_CAP);raise

def decision(elapsed,rss,used,dbbytes,free,reserve):
 if elapsed>=EXTERNAL_SECONDS:return 'external600secondcap'
 if rss>RSS_CAP:return 'observed_process_tree1GB_RSS_cap'
 if used>OUTPUT_CAP-TERMINAL-HEADROOM:return 'aggregate_output_with32MB_headroom_cap'
 if dbbytes>DB_CAP:return 'database400MB_hard_cap'
 if free<reserve+HEADROOM:return 'weights_scratch_freefloor'
 return None

def execute(expected):
 start=clock();pins(expected);DEST.mkdir(exist_ok=False);terminal_write(DEST/'supervisor-result.json',{'status':'RUNNING_NOT_COMPLETE'},OUTPUT_CAP,'supervisor');terminal_write(DEST/'worker-result.json',{'status':'NOT_STARTED_NOT_COMPLETE'},OUTPUT_CAP)
 env=dict(os.environ,PGCOMPACT_PARENT_PID=str(os.getpid()),PGCOMPACT_SHARED_START=str(start));proc=None;peak=0;reason=None
 def stop():
  if proc and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=2)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=3)
 try:
  reserve=storage()
  with (DEST/'worker.log').open('xb') as log:
   proc=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker','--manifest-sha256',expected],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   while proc.poll() is None:
    remaining=EXTERNAL_SECONDS-(clock()-start)
    if remaining<=0:reason='external600secondcap';stop();break
    ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=min(1,remaining));rss,_=tree_rss_from_ps(ps.stdout,os.getpid());peak=max(peak,rss);db=DEST/'catalog.sqlite3'
    reason=decision(clock()-start,rss,size(DEST),db.stat().st_size if db.exists() else 0,shutil.disk_usage(DEST).free,reserve)
    if reason:stop();break
    time.sleep(min(.5,max(0,EXTERNAL_SECONDS-(clock()-start))))
   code=proc.wait(timeout=3)
  w=json.loads((DEST/'worker-result.json').read_text());success=code==0 and reason is None and w['status']=='COMPLETE_LOSSLESS_COMPACT_CATALOG_METADATA_ONLY_NO_ADMISSION'
  if success and file_sha(DEST/'catalog.sqlite3')!=w['database_SHA256']:success=False;reason='Postworker database hash mismatch'
  db=DEST/'catalog.sqlite3';final=decision(clock()-start,peak,size(DEST),db.stat().st_size if db.exists() else 0,shutil.disk_usage(DEST).free,reserve)
  if final:success=False;reason=reason or final
  terminal_write(DEST/'supervisor-result.json',{'status':'COMPLETE' if success else 'FAILED','reason':reason,'worker_exit_code':code,'worker_pid':proc.pid,'elapsed_seconds':clock()-start,'peak_observed_process_tree_RSS_bytes':peak,'worker_result_SHA256':file_sha(DEST/'worker-result.json'),'manifest_SHA256':expected,'network_requests':0,'ledger_mutations':0,'retry':False,'new_admitted_tokens':0,'RSS_scope':'0.5secobservations,notproofagainsttransientpeaks'},OUTPUT_CAP,'supervisor');raise SystemExit(0 if success else 1)
 except SystemExit:raise
 except BaseException as error:
  stop();terminal_write(DEST/'supervisor-result.json',{'status':'FAILED','reason':'supervisor_exception:'+str(error)[:2000],'elapsed_seconds':clock()-start,'network_requests':0,'ledger_mutations':0,'retry':False,'new_admitted_tokens':0},OUTPUT_CAP,'supervisor');raise

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--manifest-sha256',required=True);args=p.parse_args();pins(args.manifest_sha256)
 if args.worker:return worker(args.manifest_sha256)
 if args.execute:return execute(args.manifest_sha256)
 print(json.dumps({'status':'READY_OFFLINE_NOT_EXECUTED','manifest_SHA256':args.manifest_sha256,'source_archive_SHA256':ARCHIVE_SHA,'no_network':True,'no_ledger_API':True}))
if __name__=='__main__':main()
