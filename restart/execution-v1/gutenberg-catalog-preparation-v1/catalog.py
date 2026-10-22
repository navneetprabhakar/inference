"""One native complete RDF catalog acquisition, bounded streaming inventory.
Reuses reviewed Gutenberg TLS/redirect policy and Wikibooks bounded decoded reads
and process-tree RSS observer. --execute needs explicit parent manifest digest.
"""
import argparse,bz2,hashlib,importlib.util,json,os,platform,re,shutil,signal,sqlite3,ssl,subprocess,sys,tarfile,time,urllib.request
from pathlib import Path,PurePosixPath
from lxml import etree
import parse_rdf
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;REPO=EXEC.parents[1]
sys.path.insert(0,str(EXEC));sys.path.insert(0,str(REPO/'src'))
from acquire_sources import ROOT,CONTRACT,IntakeLedger
READER_DIR=EXEC/'wikibooks-identity-frame-preparation-v1';sys.path.insert(0,str(READER_DIR))
from inventory import Decoded,StopInventory,terminal_write
from supervisor import tree_rss_from_ps
GUTENBERG_TLS=ROOT/'gutenberg-preparation-parallel-v4/discover.py'
spec=importlib.util.spec_from_file_location('frozen_gutenberg_tls',GUTENBERG_TLS);tls=importlib.util.module_from_spec(spec);spec.loader.exec_module(tls)
PROPOSAL=ROOT/'gutenberg-catalog-investigation-v1/catalog-acquisition-proposal.json';PROPOSAL_SHA='159fa30d1194a029b2c358070fface1b95b661dd11f25d0cdee1bfeab6487893'
SELECTION=ROOT/'gutenberg-catalog-investigation-v1/selection-contract.json';SELECTION_SHA='abd777f04ff0301010add91fa36a9925fcb531c38f29ae1324b6991b2ed94bef'
PROFILE=HERE/'profile.json';MANIFEST=HERE/'manifest.json';DEST=ROOT/'gutenberg-complete-native-catalog-v1'
URL='https://www.gutenberg.org/cache/epub/feeds/rdf-files.tar.bz2';KEY='gutenberg-complete-native-catalog-v1-once'
BODY_CAP=160000000;OUTPUT_CAP=1000000000;DECODED_CAP=4000000000;MAX_MEMBERS=150000;MEMBER_CAP=1000000;WORKER_SECONDS=570;EXTERNAL_SECONDS=600;RSS_CAP=1000000000;TERMINAL_RESERVE=1048576
ARCHIVE='rdf-files.tar.bz2'
def sha(b):return hashlib.sha256(b).hexdigest()
def clock():return time.clock_gettime(time.CLOCK_MONOTONIC)
def file_sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def size(root=DEST):return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
def environment():return {'python':sys.version,'executable':str(Path(sys.executable).resolve()),'sqlite':sqlite3.sqlite_version,'OpenSSL':ssl.OPENSSL_VERSION,'lxml':list(etree.LXML_VERSION),'platform':platform.platform()}
def bound_paths():return [HERE/'catalog.py',HERE/'parse_rdf.py',HERE/'check_offline.py',PROFILE,PROPOSAL,SELECTION,ROOT/'gutenberg-catalog-investigation-v1/primary-source-evidence.json',ROOT/'gutenberg-discovery-pilot-v2/metadata.raw',READER_DIR/'inventory.py',READER_DIR/'supervisor.py',READER_DIR/'shared_clock.py',GUTENBERG_TLS,tls.CA_BUNDLE,EXEC/'acquire_sources.py',EXEC/'disk-budget.json',EXEC/'authorization.json',EXEC/'source-acquisition-authorization.json',REPO/'src/slm/data/intake_ledger.py',REPO/'src/slm/data/schema.py']
def pins(expected):
 if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected) or MANIFEST.is_symlink() or not MANIFEST.is_file():raise ValueError('Explicit parent-reviewed manifest digest required')
 if file_sha(MANIFEST)!=expected:raise ValueError('Parent manifest digest mismatch')
 m=json.loads(MANIFEST.read_text());files=m.get('files_SHA256',{})
 if set(files)!={str(p.resolve()) for p in bound_paths()} or m.get('environment')!=environment():raise ValueError('Exact code/policy/dependency inventory and runtime required')
 for name,h in files.items():
  p=Path(name)
  if p.is_symlink() or not p.is_file() or file_sha(p)!=h:raise ValueError('Frozen input mismatch:'+name)
 if file_sha(PROPOSAL)!=PROPOSAL_SHA or file_sha(SELECTION)!=SELECTION_SHA:raise ValueError('Parent-approved policy mismatch')
 return m

class Guards:
 def __init__(self,output,start,limits=None,reserve=None):
  self.output=output;self.start=start;self.limits=limits or {'decoded_bytes':DECODED_CAP};self.reserve=reserve
 def check(self,additional=0):
  if not 0<=clock()-self.start<WORKER_SECONDS:raise TimeoutError('Shared worker deadline')
  if size(self.output)+additional>OUTPUT_CAP-TERMINAL_RESERVE:raise ValueError('Aggregate output prewrite cap')
  if self.reserve is not None and shutil.disk_usage(self.output).free<self.reserve+additional:raise ValueError('Protected weights/scratch/freefloor')
def save(name,data,guard):
 b=data if isinstance(data,bytes) else (json.dumps(data,indent=2)+'\n').encode();guard.check(len(b))
 with (guard.output/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def storage():
 p=json.loads((EXEC/'disk-budget.json').read_text());reserve=p['weights_checkpoints_reserved_bytes']+p['scratch_cap_bytes']+p['free_disk_floor_bytes']
 if size(ROOT)+OUTPUT_CAP>min(p['processed_data_cap_bytes'],p['raw_download_cap_bytes']):raise ValueError('Combined local64GB storage ceiling')
 if shutil.disk_usage(ROOT).free<reserve+OUTPUT_CAP:raise ValueError('Preflight weights/scratch/freefloor')
 return reserve

def fetch(ledger,guard,opener=None):
 ledger.reserve(KEY,requests=1,body_bytes=BODY_CAP,rows=MAX_MEMBERS,output_bytes=OUTPUT_CAP)
 save('request.json',{'key':KEY,'URL':URL,'charged_before_IO':True,'response_body_cap':BODY_CAP,'redirects':False,'retry':False},guard)
 partial=guard.output/(ARCHIVE+'.partial');headers={};h=hashlib.sha256();n=0
 try:
  context=tls.trusted_context();context.minimum_version=ssl.TLSVersion.TLSv1_2
  opener=opener or urllib.request.build_opener(tls.NoRedirect(),urllib.request.HTTPSHandler(context=context))
  request=urllib.request.Request(URL,headers={'User-Agent':'EnglishSLM-native-catalog-discovery/1.0','Accept-Encoding':'identity'})
  with opener.open(request,timeout=min(30,WORKER_SECONDS-(clock()-guard.start))) as response,partial.open('xb') as f:
   headers=dict(response.headers.items())
   if response.geturl()!=URL or response.status!=200:raise ValueError('Exact catalogURL HTTP200 required')
   if response.headers.get('Content-Encoding','identity').lower()!='identity':raise ValueError('Unexpected HTTP content encoding')
   length=response.headers.get('Content-Length')
   if length is not None and not 0<=int(length)<BODY_CAP:raise ValueError('Catalog declared length reaches bound')
   while n<BODY_CAP:
    guard.check(min(65536,BODY_CAP-n));ledger.check_time();b=response.read(min(65536,BODY_CAP-n))
    if not b:break
    f.write(b);f.flush();h.update(b);n+=len(b)
   if n>=BODY_CAP:raise ValueError('Response hits cap; no unreserved EOF probe')
   if length is not None and int(length)!=n:raise ValueError('Catalog truncated ContentLength')
   f.flush();os.fsync(f.fileno())
  # IntakeLedger.finish deliberately requires bytes; bounded reread <=160MB
  # remains under the separately observed1GB process-tree RSS threshold.
  guard.check()
  with partial.open('rb') as f:raw=f.read(BODY_CAP+1)
  if len(raw)!=n or sha(raw)!=h.hexdigest():raise ValueError('Local archive changed before durable ledgerfinish')
  ledger.finish(KEY,raw=raw);del raw
  os.rename(partial,guard.output/ARCHIVE)
  receipt={'key':KEY,'URL':URL,'effective_URL':response.geturl(),'headers':headers,'actual_response_bytes':n,'response_SHA256':h.hexdigest(),'reserved_response_bytes':BODY_CAP,'charged_before_IO':True,'strict_TLS_CERT_REQUIRED_hostname':True,'CA_bundle_SHA256':tls.CA_SHA256,'redirect':False,'retry':False,'snapshot_identity_scope':'Exact local capturedbytes; upstreamfilename mutable daily, no publisherchecksum assumed.'}
  save('transfer-receipt.json',receipt,guard);return receipt
 except BaseException as error:
  if getattr(error,'headers',None) is not None:headers=dict(error.headers.items())
  state=ledger.db.execute('select state from attempts where key=?',(KEY,)).fetchone()
  if state and state[0]=='pending':ledger.finish(KEY,raw=None)
  save('transfer-failure.json',{'status':'TERMINAL_FAILED_NO_RETRY','key':KEY,'URL':URL,'headers':headers,'received_prefix_bytes':n,'received_prefix_SHA256':h.hexdigest(),'error':str(error)},guard);raise


class StrictBZ2:
 """Bounded decompression, complete CRC for every stream, no trailing junk."""
 def __init__(self,handle):
  self.handle=handle;self.decoder=None;self.pending=b'';self.complete=False;self.streams=0
 def read(self,n):
  out=[];used=0
  while used<n and not self.complete:
   if self.decoder is None:
    chunk=self.pending;self.pending=b''
    if len(chunk)<4:chunk+=self.handle.read(4-len(chunk))
    if not chunk:
     if self.streams==0:raise ValueError('Empty compressed archive')
     self.complete=True;break
    if len(chunk)<4 or chunk[:3]!=b'BZh' or chunk[3:4] not in b'123456789':raise ValueError('Invalid or trailing nonbzip2 compressed bytes')
    self.decoder=bz2.BZ2Decompressor();self.pending=chunk
   if self.decoder.needs_input:
    chunk=self.pending;self.pending=b''
    if not chunk:chunk=self.handle.read(65536)
    if not chunk:raise ValueError('Truncated bzip2 stream')
   else:chunk=b''
   part=self.decoder.decompress(chunk,max_length=n-used);out.append(part);used+=len(part)
   if self.decoder.eof:
    self.pending=self.decoder.unused_data;self.streams+=1;self.decoder=None
  return b''.join(out)

def tar_members(archive,guard,stats):
 """Reuse pinned bounded decoded exact reads; never write an expanded tar."""
 with archive.open('rb') as f:
  strict=StrictBZ2(f);decoded=Decoded(strict,guard)
  try:
   while True:
    header=decoded.exact(512)
    if header==b'\0'*512:
     if decoded.exact(512)!=b'\0'*512:raise ValueError('Missing second tar EOF block')
     while True:
      b=decoded.read(65536)
      if not b:break
      if any(b):raise ValueError('Nonzero data after tar EOF')
     if not strict.complete:raise ValueError('Compressed full EOF not established')
     stats['bzip2_streams']=strict.streams;stats['full_tar_EOF_verified']=stats['full_bzip2_CRC_EOF_verified']=True;return
    member=tarfile.TarInfo.frombuf(header,'utf-8','strict');stats['members']+=1
    if stats['members']>MAX_MEMBERS:raise ValueError('150k tar member cap')
    name=PurePosixPath(member.name)
    if name.is_absolute() or '..' in name.parts or len(member.name.encode())>4096:raise ValueError('Unsafe/unbounded tar member path')
    if not member.isfile() and not member.isdir():raise ValueError('Unsupported tar membertype; no alias/longname interpretation')
    if member.isdir() and member.size:raise ValueError('Nonempty directorymember')
    h=hashlib.sha256();remaining=member.size;parts=[];parsed=member.isfile() and member.name.endswith('.rdf') and member.size<=MEMBER_CAP
    while remaining:
     b=decoded.exact(min(65536,remaining));h.update(b);remaining-=len(b)
     if parsed:parts.append(b)
    padding=(-member.size)%512
    if padding and decoded.exact(padding)!=b'\0'*padding:raise ValueError('Nonzero tar padding')
    stats['member_body_bytes']+=member.size
    yield {'ordinal':stats['members'],'name':member.name,'size':member.size,'body_SHA256':h.hexdigest(),'header_SHA256':sha(header),'kind':'directory' if member.isdir() else 'file','raw':b''.join(parts) if parsed else None,'hold':'oversize_RDF_member_not_parsed' if member.isfile() and member.name.endswith('.rdf') and not parsed else None}
  finally:stats['actual_decoded_tar_bytes']=decoded.n

def inventory(archive,guard):
 path=guard.output/'catalog.sqlite3';os.environ['SQLITE_TMPDIR']=str(guard.output);db=sqlite3.connect(path)
 db.execute('pragma journal_mode=DELETE');db.execute('pragma synchronous=FULL');db.execute('pragma cache_size=-4096');db.execute('pragma temp_store=FILE');db.execute('pragma max_page_count='+str((OUTPUT_CAP-TERMINAL_RESERVE)//4096))
 db.execute('create table members(ordinal integer primary key,name text,bytes integer,body_hash text,data text)')
 db.execute('create table records(member integer primary key,ebook_ID integer,data text)');db.execute('create index ebook_identity on records(ebook_ID)')
 stats={'members':0,'RDF_members':0,'parsed_ebook_records':0,'held_potential_records':0,'nonRDF_files':0,'directories':0,'member_body_bytes':0,'actual_decoded_tar_bytes':0,'full_tar_EOF_verified':False,'full_bzip2_CRC_EOF_verified':False};count=0
 try:
  for member in tar_members(archive,guard,stats):
   row=None;recordhold=member['hold'];raw=member.pop('raw')
   if member['kind']=='directory':stats['directories']+=1
   elif member['name'].endswith('.rdf'):
    stats['RDF_members']+=1
    if raw is not None:
     try:row=parse_rdf.parse(raw,member['name'])
     except Exception as error:recordhold='invalid_or_unknown_RDF:'+type(error).__name__+':'+str(error)[:400]
    if row is None:stats['held_potential_records']+=1
   else:stats['nonRDF_files']+=1;recordhold='non_RDF_member_not_ebook_metadata'
   member['hold']=recordhold;meta=json.dumps(member,separators=(',',':'));payload=json.dumps(row,ensure_ascii=True,separators=(',',':')) if row is not None else None
   guard.check(8*(len(meta.encode())+(len(payload.encode()) if payload else 0))+131072)
   db.execute('insert into members values(?,?,?,?,?)',(member['ordinal'],member['name'],member['size'],member['body_SHA256'],meta))
   if row is not None:
    eid=row['ebook_ID']
    if eid>=2**63:raise ValueError('Unbounded ebookID')
    db.execute('insert into records values(?,?,?)',(member['ordinal'],eid,payload));stats['parsed_ebook_records']+=1
   count+=1
   if count%100==0:db.commit()
  db.commit();guard.check()
  if not stats['full_tar_EOF_verified'] or not stats['full_bzip2_CRC_EOF_verified']:raise ValueError('Full archive EOF required')
  count,total=db.execute('select count(*),sum(bytes) from members').fetchone();records=db.execute('select count(*) from records').fetchone()[0]
  if count!=stats['members'] or (total or 0)!=stats['member_body_bytes'] or records!=stats['parsed_ebook_records']:raise ValueError('Catalog member/record/byte reconciliation')
  duplicates=db.execute('select count(*) from (select ebook_ID from records group by ebook_ID having count(*)>1)').fetchone()[0]
  if duplicates:
   duplicate_ids=[x[0] for x in db.execute('select ebook_ID from records group by ebook_ID having count(*)>1')]
   for eid in duplicate_ids:
    for member,payload in list(db.execute('select member,data from records where ebook_ID=?',(eid,))):
     row=json.loads(payload);row['holds']=sorted(set(row['holds']+['duplicate_native_ebook_ID_in_catalog_requires_family_reconciliation']))
     updated=json.dumps(row,separators=(',',':'));guard.check(8*len(updated.encode())+131072);db.execute('update records set data=? where member=?',(updated,member))
   db.commit()
  stats['duplicate_ebook_ID_groups']=duplicates
  db.set_progress_handler(lambda:1 if clock()-guard.start>=WORKER_SECONDS else 0,10000)
  if db.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failure')
  stats['SQLite_integrity']='ok';stats['archive_identity_inventory_complete']=True;stats['all_potential_RDF_records_parsed_without_duplicate_ID']=stats['held_potential_records']==0 and duplicates==0 and stats['nonRDF_files']==0
  stats['English_Text_metadata_rows']=db.execute("select count(*) from records where json_extract(data,'$.metadata_English_Text_view')=1").fetchone()[0]
  stats['rows_with_missing_language_metadata']=db.execute("select count(*) from records where json_array_length(json_extract(data,'$.languages'))=0").fetchone()[0]
  stats['rows_with_unmapped_fields']=db.execute("select count(*) from records where json_array_length(json_extract(data,'$.unmapped_book_fields'))>0").fetchone()[0]
  stats['rows_with_metadata_holds']=db.execute("select count(*) from records where json_array_length(json_extract(data,'$.holds'))>0").fetchone()[0]
  stats['rows_with_missing_type_metadata']=db.execute("select count(*) from records where json_array_length(json_extract(data,'$.types'))=0").fetchone()[0]
  stats['all_native_records_have_language_and_type_metadata']=stats['all_potential_RDF_records_parsed_without_duplicate_ID'] and stats['rows_with_missing_language_metadata']==0 and stats['rows_with_missing_type_metadata']==0
  stats['metadata_English_is_not_originalEnglish_or_usable_frame']=True;return stats
 finally:db.commit();db.close()


def worker(expected):
 pins(expected)
 if os.getppid()!=int(os.environ['PGCAT_PARENT_PID']):raise ValueError('Direct supervisor required')
 start=float(os.environ['PGCAT_SHARED_START']);ledger=None;guard=Guards(DEST,start)
 try:
  terminal_write(DEST/'worker-result.json',{'status':'RUNNING_NOT_COMPLETE'},OUTPUT_CAP)
  guard.reserve=storage();guard.check();ledger=IntakeLedger(ROOT/'charges',CONTRACT)
  save('preflight.json',{'parent_reviewed_manifest_SHA256':expected,'profile_SHA256':file_sha(PROFILE),'proposal_SHA256':PROPOSAL_SHA,'selection_SHA256':SELECTION_SHA,'one_URL':URL,'global_reserved_before':ledger.totals(),'CA_bundle_SHA256':tls.CA_SHA256,'strict_TLS':'CERT_REQUIRED and hostname TLS1.2+; no fallback','no_book_body_requests':True},guard)
  transfer=fetch(ledger,guard);stats=inventory(DEST/ARCHIVE,guard);guard.check()
  result={'status':'COMPLETE_CATALOG_ARCHIVE_IDENTITY_AND_BOUNDED_METADATA_INVENTORY_NO_ADMISSION','transfer':transfer,'stats':stats,'database_SHA256':file_sha(DEST/'catalog.sqlite3'),'manifest_SHA256':expected,'elapsed_seconds':clock()-start,'global_reserved_after':ledger.totals(),'book_bodies_fetched':0,'new_admitted_documents':0,'new_admitted_tokens':0,'models_initialized':0,'limitations':['CatalogEnglish/type/author metadata is discovery only; originalEnglish/edition/jurisdiction/quality/dedup/split/token gates remain.','All summaries excluded fromprose; sourcearchive remainsauthoritative.','Incomplete/unparsed/duplicate members prohibit completeEnglishselectionframe claim.']}
  guard.check();terminal_write(DEST/'worker-result.json',result,OUTPUT_CAP)
 except BaseException as error:
  terminal_write(DEST/'worker-result.json',{'status':'TERMINAL_CATALOG_FAILED_NO_RETRY','error':str(error),'exception_type':type(error).__name__,'elapsed_seconds':clock()-start,'book_bodies_fetched':0,'new_admitted_documents':0,'new_admitted_tokens':0},OUTPUT_CAP);raise
 finally:
  if ledger:ledger.close()

def decision(elapsed,rss,used,free,reserve):
 if elapsed>=EXTERNAL_SECONDS:return 'external600secondcap'
 if rss>RSS_CAP:return 'observed_process_tree1GB_RSS_cap'
 if used>OUTPUT_CAP-TERMINAL_RESERVE:return 'aggregate_output_cap'
 if free<reserve:return 'weights_scratch_freefloor'
 return None

def execute(expected):
 start=clock();pins(expected);DEST.mkdir(exist_ok=False);terminal_write(DEST/'supervisor-result.json',{'status':'RUNNING_NOT_COMPLETE'},OUTPUT_CAP,'supervisor');terminal_write(DEST/'worker-result.json',{'status':'NOT_STARTED_NOT_COMPLETE'},OUTPUT_CAP)
 reserve=None;env=dict(os.environ,PGCAT_PARENT_PID=str(os.getpid()),PGCAT_SHARED_START=str(start));proc=None;peak=0;reason=None
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
    ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=min(1,remaining));rss,_=tree_rss_from_ps(ps.stdout,os.getpid());peak=max(peak,rss)
    reason=decision(clock()-start,rss,size(),shutil.disk_usage(DEST).free,reserve)
    if reason:stop();break
    time.sleep(min(.5,max(0,EXTERNAL_SECONDS-(clock()-start))))
   code=proc.wait(timeout=3)
  w=json.loads((DEST/'worker-result.json').read_text());success=code==0 and reason is None and w['status']=='COMPLETE_CATALOG_ARCHIVE_IDENTITY_AND_BOUNDED_METADATA_INVENTORY_NO_ADMISSION'
  if success and file_sha(DEST/'catalog.sqlite3')!=w['database_SHA256']:success=False;reason='Database postworker hash mismatch'
  final=decision(clock()-start,peak,size(),shutil.disk_usage(DEST).free,reserve)
  if final:success=False;reason=reason or final
  terminal_write(DEST/'supervisor-result.json',{'status':'COMPLETE' if success else 'FAILED','reason':reason,'worker_exit_code':code,'worker_pid':proc.pid,'elapsed_seconds':clock()-start,'peak_observed_process_tree_RSS_bytes':peak,'worker_result_SHA256':file_sha(DEST/'worker-result.json'),'manifest_SHA256':expected,'RSS_scope':'0.5secobservations;transientunobservedpeaksnotprovenabsent','retry':False,'book_bodies_fetched':0,'new_admitted_tokens':0},OUTPUT_CAP,'supervisor');raise SystemExit(0 if success else 1)
 except SystemExit:raise
 except BaseException as error:
  stop();terminal_write(DEST/'supervisor-result.json',{'status':'FAILED','reason':'supervisor_exception:'+str(error)[:2000],'elapsed_seconds':clock()-start,'peak_observed_process_tree_RSS_bytes':peak,'worker_pid':proc.pid if proc else None,'retry':False,'book_bodies_fetched':0,'new_admitted_tokens':0},OUTPUT_CAP,'supervisor');raise

def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--manifest-sha256',required=True);args=p.parse_args();pins(args.manifest_sha256)
 if args.worker:return worker(args.manifest_sha256)
 if args.execute:return execute(args.manifest_sha256)
 print(json.dumps({'status':'READY_NOT_EXECUTED','manifest_SHA256':args.manifest_sha256,'URL':URL,'response_cap':BODY_CAP,'output_cap':OUTPUT_CAP}))
if __name__=='__main__':main()
