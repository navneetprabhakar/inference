"""Bounded one-source-pass metadata frame. No book fetch, model or network APIs."""
import argparse,collections,gzip,hashlib,json,os,re,shutil,signal,sqlite3,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent
sys.path.insert(0,str(EXEC/'gutenberg-catalog-compact-preparation-v2'));import compact as c
import classify
SOURCE=c.DEST;PARTIAL=c.ROOT/'gutenberg-selective-native-six-v1';VERIFICATION=EXEC/'gutenberg-selective-native-partial-verification-v1';PROPOSAL=EXEC/'gutenberg-English-frame-overlay-proposal-v1/proposal.json'
DEST=c.ROOT/'gutenberg-complete-English-metadata-frame-v2';PROFILE=HERE/'profile.json';MANIFEST=HERE/'manifest.json';PROFILE_SHA='3e88f52e825afbb41c0a5b6ed29b1923ef37cdc62eebfb2a0f31924ede3f503b'
OUTPUT=600000000;DB_CAP=540000000;JOURNAL_CAP=16000000;HEADROOM=32000000;TERMINAL=1048576;WORKER=570;EXTERNAL=600;RSS=1000000000;PAGE=65536;BATCH=50
SCHEMA=['create table frame(ordinal integer primary key,ebook_ID integer unique,source_layer text,discovery_status text,English_Text integer,genres text,era text,raw_bytes integer,raw_hash text,packed_hash text,codec text,payload blob)','create index discovery on frame(discovery_status,era)','create table families(ebook_ID integer primary key,component_ID integer,priority text,roles text)','create index family_components on families(component_ID)']
def database(path):
 db=sqlite3.connect(path)
 try:
  db.execute('pragma page_size='+str(PAGE));db.execute('pragma max_page_count='+str(DB_CAP//PAGE));db.execute('pragma journal_mode=DELETE');db.execute('pragma synchronous=FULL');db.execute('pragma cache_size=-4096');db.execute('pragma temp_store=FILE')
  for sql in SCHEMA:db.execute(sql)
  db.commit();return db
 except BaseException:db.rollback();db.close();raise

def insert(db,row,ordinal,layer,payload=None):
 payload=payload or c.pack(row);db.execute('insert into frame values(?,?,?,?,?,?,?,?,?,?,?,?)',(ordinal,row['ebook_ID'],layer,row['discovery_status'],int(row['languages']==['en'] and row['types']==['Text']),json.dumps(row['observed_genre_strata'],separators=(',',':')),row['creator_era_stratum'],*payload));return payload
NATIVE_MAP={k:k for k in ['ebook_ID','titles','languages','typed_language_fields','types','subjects','bookshelves','contributors_and_all_roles','unresolved_contributor_fields','original_print_dates_and_edition','rights_fields','native_relations_and_credits']}
NATIVE_MAP.update({'formats':'all_formats','PG_issued_dates':'PG_issued_dates_not_print_dates'})
def strict_relation_IDs(native):
 ids=set()
 for relation in native['native_relations_and_credits']:
  for value in list(relation.get('attributes',{}).values())+[relation.get('text','')]:
   match=re.fullmatch(r'https?://(?:www\.)?gutenberg\.org/ebooks/([1-9][0-9]*)',value)
   if match:ids.add(int(match.group(1)))
 return sorted(ids)
def classified(native,binding):
 row=classify.classify(native,binding);row['classifier_provisional_related_ebook_IDs']=row['explicit_related_ebook_IDs'];row['explicit_related_ebook_IDs']=strict_relation_IDs(native);row['family_edge_adapter']='strict_complete_canonical_URL_values_v1';row['priority_key_scope']='provisional_seed_only_final_priority_in_families_table';row['original_native_remaining_fields']={k:v for k,v in native.items() if k not in NATIVE_MAP}
 if restore_native(row)!=native:raise ValueError('Complete native metadata field roundtrip')
 return row
def restore_native(row):return {**row['original_native_remaining_fields'],**{old:row[new] for old,new in NATIVE_MAP.items()}}
class Families:
 def __init__(self):self.parents={};self.seeds={};self.edges=[];self.roles={}
 def root(self,eid):
  while self.parents[eid]!=eid:self.parents[eid]=self.parents[self.parents[eid]];eid=self.parents[eid]
  return eid
 def union(self,a,b):
  a,b=self.root(a),self.root(b)
  if a!=b:self.parents[max(a,b)]=min(a,b)
 def add(self,row):
  eid=row['ebook_ID']
  if eid in self.parents:raise ValueError('Global ebook ID duplicate including overlays')
  self.parents[eid]=eid;seed=row['provisional_family']
  if seed in self.seeds:self.union(eid,self.seeds[seed])
  else:self.seeds[seed]=eid
  self.roles[eid]=sorted({a['role_qualified_name'] for a in row['contributors_and_all_roles']})
  self.edges.extend((eid,target) for target in row['explicit_related_ebook_IDs'])
  if len(self.parents)>79652 or len(self.edges)>1000000:raise ValueError('Bounded family graph')
 def resolve(self):
  missing=0
  for eid,target in self.edges:
   if target in self.parents:self.union(eid,target)
   else:missing+=1
  return missing

def dependencies():
 paths=[HERE/n for n in ['frame.py','classify.py','profile.json','capacity.json','project.py','sample400-capacity.sqlite3','check.py']]
 paths += [EXEC/'gutenberg-English-frame-preparation-v1/derive.py',EXEC/'gutenberg-English-frame-preparation-v1/policy.json',PROPOSAL,VERIFICATION/'manifest.json',VERIFICATION/'verification.json',EXEC/'m2-intake/gutenberg-nativefields-parent-review-v1/review.json',SOURCE/'worker-result.json',SOURCE/'supervisor-result.json',SOURCE/'catalog-0.sqlite3',SOURCE/'catalog-1.sqlite3',PARTIAL/'worker-result.json',PARTIAL/'supervisor-result.json',c.HERE/'compact.py',c.HERE/'parse_rdf.py',c.HERE/'archive_reader.py',c.READER_DIR/'inventory.py',c.READER_DIR/'supervisor.py',c.READER_DIR/'shared_clock.py',EXEC/'disk-budget.json']
 for ordinal in [17579,18683]:paths.extend(PARTIAL/('ordinal-'+str(ordinal)+suffix) for suffix in ['.rdf','.receipt.json','.derived-metadata.json.gz'])
 return paths

def pins(expected):
 if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected) or MANIFEST.is_symlink() or c.file_sha(MANIFEST)!=expected:raise ValueError('Explicit parent manifest SHA required')
 m=json.loads(MANIFEST.read_text());files=m.get('files_SHA256',{})
 if set(files)!={str(p.resolve()) for p in dependencies()} or m.get('environment')!=c.environment():raise ValueError('Exact dependency inventory/runtime required')
 for name,h in files.items():
  p=Path(name)
  if p.is_symlink() or not p.is_file() or c.file_sha(p)!=h:raise ValueError('Pinned input changed:'+name)
 if c.file_sha(PROFILE)!=PROFILE_SHA:raise ValueError('Frozen profile SHA')
 if (HERE/'classify.py').read_bytes()!=(EXEC/'gutenberg-English-frame-preparation-v1/derive.py').read_bytes():raise ValueError('Frozen classifier byte copy')
 return m
class Guard:
 def __init__(self,output,start):
  self.output=output;self.start=start;budget=json.loads((EXEC/'disk-budget.json').read_text());self.reserve=sum(budget[k] for k in ['weights_checkpoints_reserved_bytes','scratch_cap_bytes','free_disk_floor_bytes'])
  if c.size(c.ROOT)+OUTPUT>budget['processed_data_cap_bytes']:raise ValueError('Processed data64GB cap')
  if shutil.disk_usage(output).free<self.reserve+OUTPUT+HEADROOM:raise ValueError('Protected preflight reserves')
 def check(self,additional=0):
  if not 0<=c.clock()-self.start<WORKER:raise TimeoutError('570sec worker deadline')
  if additional<0 or c.size(self.output)+additional>OUTPUT-TERMINAL-HEADROOM:raise ValueError('600MB output prewrite cap with32MB headroom')
  path=self.output/'frame.sqlite3';journal=self.output/'frame.sqlite3-journal'
  if path.exists() and path.stat().st_size>DB_CAP:raise ValueError('540MB DB hardcap')
  if journal.exists() and journal.stat().st_size+additional>JOURNAL_CAP:raise ValueError('16MB journal prewrite cap')
  if shutil.disk_usage(self.output).free<self.reserve+additional+HEADROOM:raise ValueError('Protected disk reserves')

def overlay_records():
 proposal=json.loads(PROPOSAL.read_text());verification=json.loads((VERIFICATION/'verification.json').read_text())
 if verification['status']!='PASS_FIVE_PARTIAL_BODIES_ONLY_ORIGINAL_RUN_TERMINAL_FAILURE_PRESERVED':raise ValueError('Verified partial capture required')
 overlays={}
 for spec in proposal['overlays']:
  ordinal=spec['ordinal'];path=Path(spec['derived_metadata_file']);rawpath=Path(spec['raw_file'])
  if ordinal not in [17579,18683] or ordinal in overlays or c.file_sha(path)!=spec['derived_metadata_compressed_SHA256'] or c.file_sha(rawpath)!=spec['raw_SHA256'] or rawpath.stat().st_size!=spec['raw_bytes']:raise ValueError('Exact2 overlay identity/hash')
  with gzip.open(path,'rb') as f:raw=f.read(16000001);tail=f.read(1)
  if len(raw)>16000000 or tail or c.sha(raw)!=spec['derived_metadata_JSON_SHA256']:raise ValueError('Bounded overlay raw JSON identity')
  row=json.loads(raw)
  if row['ebook_ID']!=spec['ebook_ID'] or row['member']!=spec['native_member']['name'] or row['member_RDF_SHA256']!=spec['raw_SHA256']:raise ValueError('Overlay ID/member/source binding')
  overlays[ordinal]=(row,spec)
 if set(overlays)!={17579,18683}:raise ValueError('Exactly two overlays')
 return overlays

def source_query():
 return ' union all '.join('select '+str(slot)+' as slot,m.ordinal as ordinal,m.raw_bytes,m.raw_hash,m.packed_hash,m.codec,m.payload,r.raw_bytes,r.raw_hash,r.packed_hash,r.codec,r.payload from shard'+str(slot)+'.members m left join shard'+str(slot)+'.records r on m.ordinal=r.member' for slot in range(2))+' order by ordinal'
def source_rows():
 w=json.loads((SOURCE/'worker-result.json').read_text());s=json.loads((SOURCE/'supervisor-result.json').read_text());stats=w['stats']
 if w['status']!='COMPLETE_LOSSLESS_COMPACT_CATALOG_METADATA_ONLY_NO_ADMISSION' or s['status']!='COMPLETE' or s['worker_result_SHA256']!=c.file_sha(SOURCE/'worker-result.json'):raise ValueError('Complete source receipt required')
 if stats['members']!=79652 or stats['parsed_ebook_records']!=79650 or stats['held_potential_records']!=2 or not stats['full_tar_EOF_verified'] or not stats['full_bzip2_CRC_EOF_verified']:raise ValueError('Exact fullsource counts/EOF')
 overlays=overlay_records();source_worker_hash=c.file_sha(SOURCE/'worker-result.json');verification_hash=c.file_sha(VERIFICATION/'verification.json');db=c.readonly_union([SOURCE/x['file'] for x in w['database_shards']]);seen=0;used=set()
 try:
  query=source_query();plan=[row[3] for row in db.execute('explain query plan '+query)]
  if any('MATERIALIZE' in row or 'TEMP B-TREE' in row for row in plan):raise ValueError('Source query must stream indexed joins without whole-source materialization')
  for values in db.execute(query):
   slot,ordinal=values[:2];member=c.unpack(*values[2:7]);seen+=1
   if ordinal!=seen:raise ValueError('Exact contiguous source ordinal coverage')
   if values[7] is not None:
    if ordinal in overlays:raise ValueError('Overlay attempts to duplicate original record')
    native=c.unpack(*values[7:]);layer='ORIGINAL_SOURCE_PARSED';rawhash=values[8]
   else:
    if ordinal not in overlays or member['hold']!='oversize_RDF_member_not_parsed':raise ValueError('Unknown source gap')
    native,spec=overlays[ordinal];used.add(ordinal);layer='VERIFIED_OVERSIZE_DERIVED_OVERLAY'
    if member!=spec['native_member']:raise ValueError('Exact overlay/source member metadata mismatch')
    rawhash=spec['derived_metadata_JSON_SHA256']
   if native['member']!=member['name'] or native['member_RDF_SHA256']!=member['body_SHA256']:raise ValueError('Source record/member identity')
   binding={'source_worker_SHA256':source_worker_hash,'source_shard':w['database_shards'][slot],'source_layer':layer,'member_identity':member,'original_source_hold_history':member['hold'],'record_raw_JSON_SHA256':rawhash,'overlay_independent_verification_SHA256':verification_hash if ordinal in overlays else None}
   yield ordinal,layer,native,binding
  if seen!=79652 or used!={17579,18683}:raise ValueError('Full source/overlay coverage')
 finally:db.close()

def build(rows,guard,expected_rows=79652):
 os.environ['SQLITE_TMPDIR']=str(guard.output);db=database(guard.output/'frame.sqlite3');families=Families();counters={k:collections.Counter() for k in ['status','holds','exclusions','genres','era','roles','missingness','source_layer']};n=0;english=0;native_roundtrips=0;format_records=0
 try:
  for ordinal,layer,native,binding in rows:
   guard.check();row=classified(native,binding);families.add(row);payload=c.pack(row);reservation=8*len(payload[-1])+2097152
   journal=guard.output/'frame.sqlite3-journal'
   if journal.exists() and journal.stat().st_size+reservation>JOURNAL_CAP:db.commit()
   guard.check(reservation);insert(db,row,ordinal,layer,payload)
   if c.unpack(*payload)!=row:raise ValueError('Lossless frame row')
   n+=1;native_roundtrips+=1;format_records+=len(native['formats']);english+=int(row['languages']==['en'] and row['types']==['Text'])
   counters['status'][row['discovery_status']]+=1;counters['holds'].update(row['metadata_hold_reasons']);counters['exclusions'].update(row['exclusion_reasons']);counters['genres'].update(row['observed_genre_strata']);counters['era'][row['creator_era_stratum']]+=1;counters['roles'].update(a['role_qualified_name'] for a in row['contributors_and_all_roles']);counters['missingness'].update({k:int(v) for k,v in row['missingness'].items()});counters['source_layer'][layer]+=1
   if n%BATCH==0:db.commit();guard.check()
  db.commit()
  if n!=expected_rows:raise ValueError('Exact final source ordinal count')
  missing_relations=families.resolve()
  for i,eid in enumerate(sorted(families.parents),1):
   guard.check(262144);component=families.root(eid);priority=classify.sha((classify.POLICY_VERSION+'\ngutenberg-component:'+str(component)).encode());db.execute('insert into families values(?,?,?,?)',(eid,component,priority,json.dumps(families.roles[eid],separators=(',',':'))))
   if i%BATCH==0:db.commit();guard.check()
  db.commit();guard.check();db.set_progress_handler(lambda:1 if c.clock()-guard.start>=WORKER else 0,10000)
  if db.execute('pragma integrity_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity')
  counts=db.execute('select count(*),count(distinct ordinal),count(distinct ebook_ID) from frame').fetchone()
  if counts!=(expected_rows,expected_rows,expected_rows) or db.execute('select count(*) from families').fetchone()[0]!=expected_rows:raise ValueError('Global ordinal/ID/family row reconciliation')
  components=db.execute('select count(distinct component_ID) from families').fetchone()[0]
  return {'rows':n,'native_format_metadata_records_not_documents':format_records,'English_Text_metadata_before_other_filters':english,'counts':{k:dict(v) for k,v in counters.items()},'provisional_family_components':components,'explicit_relation_targets_missing_from_population':missing_relations,'global_duplicate_ebook_IDs':0,'native_metadata_field_roundtrips':native_roundtrips,'SQLite_integrity':'ok','source_stream_passes':1,'new_source_member_identities':0,'original_source_oversize_holds_historically_retained':counters['source_layer']['VERIFIED_OVERSIZE_DERIVED_OVERLAY'],'all_originalEnglish_and_edition_rights_unverified':n,'usable_documents':0,'usable_tokens':0,'training_admitted':0}
 finally:
  try:db.rollback()
  finally:db.close()

def worker(expected):
 pins(expected)
 if os.getppid()!=int(os.environ['PGFRAME_PARENT_PID']):raise ValueError('Direct live supervisor required')
 guard=Guard(DEST,float(os.environ['PGFRAME_START']))
 try:
  stats=build(source_rows(),guard);pins(expected);guard.check();path=DEST/'frame.sqlite3'
  result={'status':'COMPLETE79652_SOURCE_IDENTITIES_ENGLISH_METADATA_FRAME_ONLY_NO_ADMISSION','manifest_SHA256':expected,'profile_SHA256':PROFILE_SHA,'stats':stats,'frame_bytes':path.stat().st_size,'frame_SHA256':c.file_sha(path),'elapsed_seconds':c.clock()-guard.start,'network_requests':0,'book_bodies_fetched':0,'models_initialized':0,'new_admitted_documents':0,'new_admitted_tokens':0,'source_metadata_passes':1,'limits_on_claims':['CatalogEnglish is not originalEnglish proof.','Rights, addedcontributors, editionandjurisdiction remainunverified.','Conservativefamilycomponents are split/dedup groups, not provenworkequivalence.','Sourceoriginaloversizeholds preserved inbinding;2verifiedderivedoverlaysresolveidentityonly.','Unknownnativefieldholdsneverremoved;originalmetadata fullyreconstructable.']}
  guard.check();c.terminal_write(DEST/'worker-result.json',result,OUTPUT)
 except BaseException as error:c.terminal_write(DEST/'worker-result.json',{'status':'TERMINAL_FRAME_FAILED_NO_RETRY','error':str(error),'elapsed_seconds':c.clock()-guard.start,'network_requests':0,'new_admitted_documents':0},OUTPUT);raise

def execute(expected):
 start=c.clock();pins(expected);DEST.mkdir(exist_ok=False);guard=Guard(DEST,start);guard.check();proc=None;peak=0;reason=None
 c.terminal_write(DEST/'worker-result.json',{'status':'NOT_STARTED'},OUTPUT);c.terminal_write(DEST/'supervisor-result.json',{'status':'RUNNING'},OUTPUT,'supervisor')
 def stop():
  if proc and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=1)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=2)
 try:
  with (DEST/'worker.log').open('xb') as log:
   env=dict(os.environ,PGFRAME_PARENT_PID=str(os.getpid()),PGFRAME_START=str(start));proc=subprocess.Popen([sys.executable,str(HERE/'frame.py'),'--worker','--manifest-sha256',expected],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   while proc.poll() is None:
    left=EXTERNAL-(c.clock()-start)
    if left<=0:reason='external600secondcap';stop();break
    ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=min(1,left));rss,_=c.tree_rss_from_ps(ps.stdout,os.getpid());peak=max(peak,rss)
    dbpath=DEST/'frame.sqlite3';journal=DEST/'frame.sqlite3-journal'
    try:jbytes=journal.stat().st_size
    except FileNotFoundError:jbytes=0
    if rss>RSS or c.size(DEST)>OUTPUT-TERMINAL-HEADROOM or (dbpath.exists() and dbpath.stat().st_size>DB_CAP) or jbytes>JOURNAL_CAP or shutil.disk_usage(DEST).free<guard.reserve+HEADROOM:reason='RSS_output_DB_journal_or_disk_cap';stop();break
    time.sleep(min(.25,max(0,EXTERNAL-(c.clock()-start))))
   code=proc.wait(timeout=2)
  w=json.loads((DEST/'worker-result.json').read_text());success=code==0 and reason is None and w['status']=='COMPLETE79652_SOURCE_IDENTITIES_ENGLISH_METADATA_FRAME_ONLY_NO_ADMISSION' and c.clock()-start<EXTERNAL and c.size(DEST)<=OUTPUT-TERMINAL-HEADROOM
  if success and (c.file_sha(DEST/'frame.sqlite3')!=w['frame_SHA256'] or list(DEST.glob('*.sqlite3-journal'))):success=False;reason='FinalDBhash_or_journal'
  c.terminal_write(DEST/'supervisor-result.json',{'status':'COMPLETE' if success else 'FAILED','reason':reason,'worker_exit_code':code,'worker_pid':proc.pid,'elapsed_seconds':c.clock()-start,'manifest_SHA256':expected,'worker_result_SHA256':c.file_sha(DEST/'worker-result.json'),'peak_observed_process_tree_RSS_bytes':peak,'RSS_scope':'0.25sec observations, transientpeaksnotproven','network_requests':0,'retry':False,'new_admitted_documents':0},OUTPUT,'supervisor');raise SystemExit(0 if success else 1)
 except SystemExit:raise
 except BaseException as error:stop();c.terminal_write(DEST/'supervisor-result.json',{'status':'FAILED','error':str(error),'network_requests':0,'retry':False,'new_admitted_documents':0},OUTPUT,'supervisor');raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--manifest-sha256',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');args=p.parse_args();pins(args.manifest_sha256)
 if args.worker:worker(args.manifest_sha256)
 elif args.execute:execute(args.manifest_sha256)
 else:print(json.dumps({'status':'READY_NOT_EXECUTED','manifest_SHA256':args.manifest_sha256}))
