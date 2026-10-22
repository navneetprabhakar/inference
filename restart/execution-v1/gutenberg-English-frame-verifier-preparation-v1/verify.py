"""Offline independent full-frame verification. Does not launch derivation or fetch bodies."""
import argparse,collections,gzip,hashlib,itertools,json,os,re,shutil,signal,sqlite3,subprocess,sys,time,unicodedata
from pathlib import Path
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent;sys.path.insert(0,str(EXEC/'gutenberg-English-frame-preparation-v2'));import frame as f
c=f.c;PREP_MANIFEST='03acf1b9c14a58cea5b4d4420d6d2b9894e43a7744ec7c0da2aa725db7f14204';MANIFEST=HERE/'manifest.json';PROFILE=HERE/'profile.json';PROFILE_SHA='8b739ebf2c5773ccce0ae84e4215fa72942ec3323936aa150317310aa1ccf936';OUTPUT=16000000;WORKER=570;EXTERNAL=600;RSS=1000000000;DEST=EXEC/'m2-intake/gutenberg-English-frame-independent-verification-v1'
NATIVE_MAP={k:k for k in ['ebook_ID','titles','languages','typed_language_fields','types','subjects','bookshelves','contributors_and_all_roles','unresolved_contributor_fields','original_print_dates_and_edition','rights_fields','native_relations_and_credits']};NATIVE_MAP.update({'formats':'all_formats','PG_issued_dates':'PG_issued_dates_not_print_dates'})
def require(ok,message):
 if not ok:raise ValueError(message)
def dependencies():return [HERE/'verify.py',HERE/'check.py',PROFILE,f.HERE/'manifest.json',f.HERE/'frame.py',f.HERE/'classify.py',f.HERE/'profile.json',c.HERE/'compact.py',c.HERE/'parse_rdf.py',c.HERE/'archive_reader.py',c.READER_DIR/'inventory.py',c.READER_DIR/'supervisor.py',c.READER_DIR/'shared_clock.py',EXEC/'disk-budget.json',f.DEST/'worker-result.json',f.DEST/'supervisor-result.json',f.DEST/'frame.sqlite3']
def pins(expected):
 require(isinstance(expected,str) and re.fullmatch('[0-9a-f]{64}',expected) and not MANIFEST.is_symlink() and c.file_sha(MANIFEST)==expected,'Explicit reviewed verifier manifestSHA')
 m=json.loads(MANIFEST.read_text());require(set(m.get('files_SHA256',{}))=={str(p.resolve()) for p in dependencies()} and m['environment']==c.environment(),'Exact verifier runtime/dependency inventory')
 for name,digest in m['files_SHA256'].items():
  p=Path(name);require(not p.is_symlink() and p.is_file() and c.file_sha(p)==digest,'Verifier dependency changed:'+name)
 require(c.file_sha(PROFILE)==PROFILE_SHA,'Verifier profileSHA');f.pins(PREP_MANIFEST)
class Guard:
 def __init__(self,start):
  self.start=start;p=json.loads((EXEC/'disk-budget.json').read_text());self.reserve=sum(p[k] for k in ['weights_checkpoints_reserved_bytes','scratch_cap_bytes','free_disk_floor_bytes']);require(c.size(c.ROOT)+OUTPUT<=p['processed_data_cap_bytes'],'Processed64GB ceiling')
 def check(self,add=0):
  require(0<=c.clock()-self.start<WORKER,'570sec verificationworker deadline');require(c.size(DEST)+add<=OUTPUT-1048576,'16MB evidence prewrite cap+terminal headroom');require(shutil.disk_usage(DEST).free>=self.reserve+32000000+add,'Protected disk reserves')
class Components:
 def __init__(self):self.parent={};self.seeds={};self.edges=[];self.roles={}
 def root(self,eid):
  while self.parent[eid]!=eid:self.parent[eid]=self.parent[self.parent[eid]];eid=self.parent[eid]
  return eid
 def link(self,a,b):
  a,b=self.root(a),self.root(b)
  if a!=b:self.parent[max(a,b)]=min(a,b)
 def add(self,native):
  eid=native['ebook_ID'];require(eid not in self.parent,'Global source ID duplicate');self.parent[eid]=eid
  creators=[a for a in native['contributors_and_all_roles'] if a['role_qualified_name']=='{http://purl.org/dc/terms/}creator'];ids=tuple(sorted({a['stable_agent_ID'] for a in creators if a['stable_agent_ID'] is not None}));title=native['titles'][0] if len(native['titles'])==1 else '';title=' '.join(re.sub(r'[^\w\s]',' ',unicodedata.normalize('NFKC',title).casefold()).split())
  seed=(ids,title) if ids and title else ('ebook',eid)
  if seed in self.seeds:self.link(eid,self.seeds[seed])
  else:self.seeds[seed]=eid
  related=set()
  for node in native['native_relations_and_credits']:
   for value in list(node.get('attributes',{}).values())+[node.get('text','')]:
    m=re.fullmatch(r'https?://(?:www\.)?gutenberg\.org/ebooks/([1-9][0-9]*)',value)
    if m:related.add(int(m.group(1)))
  self.edges.extend((eid,target) for target in sorted(related));require(len(self.edges)<=1000000,'Family edge bound');self.roles[eid]=sorted({a['role_qualified_name'] for a in native['contributors_and_all_roles']})
 def resolve(self):
  missing=0
  for eid,target in self.edges:
   if target in self.parent:self.link(eid,target)
   else:missing+=1
  return missing

def overlays():
 proposal=json.loads(f.PROPOSAL.read_text());rows={}
 for item in proposal['overlays']:
  ordinal=item['ordinal'];path=Path(item['derived_metadata_file']);rawpath=Path(item['raw_file']);require(ordinal in {17579,18683} and ordinal not in rows,'Exactly2overlay ordinals')
  require(c.file_sha(path)==item['derived_metadata_compressed_SHA256'] and c.file_sha(rawpath)==item['raw_SHA256'],'Independent overlay/raw hash')
  with gzip.open(path,'rb') as handle:raw=handle.read(16000001);tail=handle.read(1)
  require(len(raw)<=16000000 and not tail and c.sha(raw)==item['derived_metadata_JSON_SHA256'],'Bounded exactoverlay JSON');rows[ordinal]=(json.loads(raw),item)
 require(set(rows)=={17579,18683},'Both exact overlays required');return rows

def verify_data(workerSHA,supervisorSHA,guard):
 profile=json.loads(PROFILE.read_text());require(workerSHA==profile['actual_source_worker_SHA256'] and supervisorSHA==profile['actual_source_supervisor_SHA256'],'Exactparentreviewedactualrun receipts');source=f.DEST;wp=source/'worker-result.json';sp=source/'supervisor-result.json';require(c.file_sha(wp)==workerSHA and c.file_sha(sp)==supervisorSHA,'Externally bound actualterminal receipts')
 worker=json.loads(wp.read_text());supervisor=json.loads(sp.read_text());require(worker['status']=='COMPLETE79652_SOURCE_IDENTITIES_ENGLISH_METADATA_FRAME_ONLY_NO_ADMISSION' and supervisor['status']=='COMPLETE' and supervisor['worker_exit_code']==0,'Completed frame required')
 require(worker['manifest_SHA256']==supervisor['manifest_SHA256']==PREP_MANIFEST and supervisor['worker_result_SHA256']==workerSHA,'Source terminal/code chain')
 require(worker['elapsed_seconds']<570 and supervisor['elapsed_seconds']<600 and supervisor['peak_observed_process_tree_RSS_bytes']<=1000000000,'Original job boundedtime/observedRSS')
 require(worker['network_requests']==supervisor['network_requests']==0 and worker['new_admitted_documents']==0 and worker['new_admitted_tokens']==0 and worker['models_initialized']==0 and worker['book_bodies_fetched']==0 and supervisor['retry'] is False,'No source model/admission/body/retry')
 path=source/'frame.sqlite3';require(path.stat().st_size==worker['frame_bytes']<=540000000 and c.file_sha(path)==worker['frame_SHA256'],'Actualframe DB hash/size')
 require(c.size(source)<=600000000-32000000-1048576 and not list(source.glob('*.sqlite3-journal')),'Frameoutputbounds/closedjournal')
 sw=json.loads((f.SOURCE/'worker-result.json').read_text());ov=overlays();source_workerSHA=c.file_sha(f.SOURCE/'worker-result.json');partial_verificationSHA=c.file_sha(f.VERIFICATION/'verification.json')
 sd=c.readonly_union([f.SOURCE/x['file'] for x in sw['database_shards']]);fd=sqlite3.connect('file:'+str(path.resolve())+'?mode=ro',uri=True);fd.execute('pragma query_only=ON')
 for db in [sd,fd]:db.set_progress_handler(lambda:1 if c.clock()-guard.start>=WORKER else 0,10000)
 source_query=' union all '.join('select '+str(slot)+' as slot,m.ordinal as ordinal,m.raw_bytes,m.raw_hash,m.packed_hash,m.codec,m.payload,r.raw_bytes,r.raw_hash,r.packed_hash,r.codec,r.payload from shard'+str(slot)+'.members m left join shard'+str(slot)+'.records r on m.ordinal=r.member' for slot in range(2))+' order by ordinal'
 plan=[r[3] for r in sd.execute('explain query plan '+source_query)];require(not any('MATERIALIZE' in r or 'TEMP B-TREE' in r for r in plan),'Independent indexedstream sourceplan')
 frame_query='select ordinal,ebook_ID,source_layer,discovery_status,English_Text,genres,era,raw_bytes,raw_hash,packed_hash,codec,payload from frame order by ordinal'
 n=0;english=0;format_count=0;overlay_used=set();components=Components();counters={k:collections.Counter() for k in ['status','holds','exclusions','genres','era','roles','missingness','source_layer']}
 try:
  for src,dst in itertools.zip_longest(sd.execute(source_query),fd.execute(frame_query)):
   guard.check();require(src is not None and dst is not None,'Exactsource/framepopulation cardinality');slot,ordinal=src[:2];n+=1;require(ordinal==n and dst[0]==ordinal,'Every79652sourceordinal exactlyonce');member=c.unpack(*src[2:7])
   if src[7] is not None:
    require(ordinal not in ov,'Overlaycannotduplicateexistingoriginal');native=c.unpack(*src[7:]);layer='ORIGINAL_SOURCE_PARSED';rawhash=src[8]
   else:
    require(ordinal in ov and member['hold']=='oversize_RDF_member_not_parsed','Only2historicaloversizegaps');native,item=ov[ordinal];overlay_used.add(ordinal);require(member==item['native_member'],'Exactoverlay/sourceheader/body/memberbinding');layer='VERIFIED_OVERSIZE_DERIVED_OVERLAY';rawhash=item['derived_metadata_JSON_SHA256']
   require(native['member']==member['name'] and native['member_RDF_SHA256']==member['body_SHA256'],'Every originalrecord/memberbinding')
   payload=c.unpack(*dst[7:]);restored=dict(payload['original_native_remaining_fields']);restored.update({old:payload[new] for old,new in NATIVE_MAP.items()});require(restored==native,'FULL ORIGINAL NATIVE FIELD ROUNDTRIP at'+str(ordinal))
   binding={'source_worker_SHA256':source_workerSHA,'source_shard':sw['database_shards'][slot],'source_layer':layer,'member_identity':member,'original_source_hold_history':member['hold'],'record_raw_JSON_SHA256':rawhash,'overlay_independent_verification_SHA256':partial_verificationSHA if ordinal in ov else None};require(payload['source_binding']==binding,'Full sourcebinding/history')
   expected=f.classified(native,binding);require(payload==expected,'Frozenclassification/strict adapter exact at'+str(ordinal));exactEnglish=int(native['languages']==['en'] and native['types']==['Text']);require(dst[1:7]==(native['ebook_ID'],layer,payload['discovery_status'],exactEnglish,json.dumps(payload['observed_genre_strata'],separators=(',',':')),payload['creator_era_stratum']),'Every typed/query field matchespayload')
   if native['languages'] and 'en' not in native['languages']:require(payload['discovery_status'].startswith('EXCLUDED'),'KnownnonEnglish excluded')
   if payload['discovery_status']=='ELIGIBLE_FOR_BODY_REVIEW_METADATA_ONLY':require(exactEnglish and not payload['metadata_hold_reasons'],'Eligible exactEnglishText no metadatahold')
   require(not payload['training_admitted'] and payload['original_English_composition'].startswith('UNVERIFIED') and payload['edition_and_jurisdiction_rights'].startswith('UNVERIFIED'),'No categoricalrights/originalEnglish clearance')
   if native['holds']:require(payload['discovery_status']!='ELIGIBLE_FOR_BODY_REVIEW_METADATA_ONLY','Every nativeunknownhold preserved')
   components.add(native);english+=exactEnglish;format_count+=len(native['formats']);counters['status'][payload['discovery_status']]+=1;counters['holds'].update(payload['metadata_hold_reasons']);counters['exclusions'].update(payload['exclusion_reasons']);counters['genres'].update(payload['observed_genre_strata']);counters['era'][payload['creator_era_stratum']]+=1;counters['roles'].update(a['role_qualified_name'] for a in native['contributors_and_all_roles']);counters['missingness'].update({k:int(v) for k,v in payload['missingness'].items()});counters['source_layer'][layer]+=1
  require(n==79652 and overlay_used=={17579,18683},'Exact79650+2coverage');missing=components.resolve();family_rows=0;roots=set()
  for row in fd.execute('select ebook_ID,component_ID,priority,roles from families order by ebook_ID'):
   guard.check();eid,component,priority,roles=row;require(eid in components.parent,'No orphanfamilymember');root=components.root(eid);roots.add(root);family_rows+=1;expected_priority=hashlib.sha256(('gutenberg-native-catalog-discovery-v1\ngutenberg-component:'+str(root)).encode()).hexdigest();require(component==root and priority==expected_priority and json.loads(roles)==components.roles[eid],'Independent transitivefamily/priority/allroles')
  require(family_rows==n and fd.execute('pragma integrity_check').fetchone()[0]=='ok','FullSQLiteintegrity/familycoverage');summary={'rows':n,'English_Text_metadata_before_other_filters':english,'native_format_metadata_records_not_documents':format_count,'counts':{k:dict(v) for k,v in counters.items()},'provisional_family_components':len(roots),'explicit_relation_targets_missing_from_population':missing,'global_duplicate_ebook_IDs':0,'native_metadata_field_roundtrips':n,'SQLite_integrity':'ok','source_stream_passes':1,'new_source_member_identities':0,'original_source_oversize_holds_historically_retained':2,'all_originalEnglish_and_edition_rights_unverified':n,'usable_documents':0,'usable_tokens':0,'training_admitted':0};require(summary==worker['stats'],'Every terminalstat independently reconciled')
 finally:sd.close();fd.close()
 require(c.file_sha(path)==worker['frame_SHA256'] and c.file_sha(wp)==workerSHA and c.file_sha(sp)==supervisorSHA,'Sourceframe/terminal unchanged afterverification')
 return {'status':'PASS_INDEPENDENT_ALL79652_NATIVE_FIELDS_TYPEDCLASSIFICATION_OVERLAYS_AND_FAMILIES_METADATA_ONLY','summary':summary,'source_frame_SHA256':worker['frame_SHA256'],'source_worker_SHA256':workerSHA,'source_supervisor_SHA256':supervisorSHA,'source_query_plan':plan,'new_admitted_documents':0,'new_admitted_tokens':0,'network_requests':0,'book_bodies_fetched':0,'archive_passes':0,'source_inputs_unchanged':True}

def worker(expected,workerSHA,supervisorSHA):
 pins(expected);require(os.getppid()==int(os.environ['PGVERIFY_PARENT_PID']),'Live direct supervisor required');guard=Guard(float(os.environ['PGVERIFY_START']))
 try:
  guard.check();report=verify_data(workerSHA,supervisorSHA,guard);pins(expected);guard.check();report.update({'manifest_SHA256':expected,'elapsed_seconds':c.clock()-guard.start});c.terminal_write(DEST/'verification.json',report,OUTPUT)
 except BaseException as error:c.terminal_write(DEST/'verification.json',{'status':'TERMINAL_VERIFICATION_FAILED_NO_SOURCE_MUTATION','error':str(error),'network_requests':0,'elapsed_seconds':c.clock()-guard.start,'new_admitted_documents':0},OUTPUT);raise

def execute(expected,workerSHA,supervisorSHA):
 start=c.clock();pins(expected)
 for digest in [workerSHA,supervisorSHA]:require(re.fullmatch('[0-9a-f]{64}',digest),'Exact actualterminalSHA256 required')
 DEST.mkdir(exist_ok=False);guard=Guard(start);guard.check();proc=None;peak=0;reason=None;c.terminal_write(DEST/'verification.json',{'status':'NOT_STARTED'},OUTPUT);c.terminal_write(DEST/'supervisor-result.json',{'status':'RUNNING'},OUTPUT,'supervisor')
 def stop():
  if proc and proc.poll() is None:
   os.killpg(proc.pid,signal.SIGTERM)
   try:proc.wait(timeout=1)
   except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait(timeout=2)
 try:
  with (DEST/'worker.log').open('xb') as log:
   env=dict(os.environ,PGVERIFY_PARENT_PID=str(os.getpid()),PGVERIFY_START=str(start));proc=subprocess.Popen([sys.executable,str(HERE/'verify.py'),'--worker','--manifest-sha256',expected,'--source-worker-sha256',workerSHA,'--source-supervisor-sha256',supervisorSHA],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   while proc.poll() is None:
    left=EXTERNAL-(c.clock()-start)
    if left<=0:reason='external600secondcap';stop();break
    ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=min(1,left));rss,_=c.tree_rss_from_ps(ps.stdout,os.getpid());peak=max(peak,rss)
    if rss>RSS or c.size(DEST)>OUTPUT-1048576 or shutil.disk_usage(DEST).free<guard.reserve+32000000:reason='RSS_output_or_diskcap';stop();break
    time.sleep(min(.25,max(0,EXTERNAL-(c.clock()-start))))
   code=proc.wait(timeout=2)
  report=json.loads((DEST/'verification.json').read_text());success=code==0 and reason is None and report['status']=='PASS_INDEPENDENT_ALL79652_NATIVE_FIELDS_TYPEDCLASSIFICATION_OVERLAYS_AND_FAMILIES_METADATA_ONLY' and c.clock()-start<EXTERNAL and c.size(DEST)<=OUTPUT-1048576
  c.terminal_write(DEST/'supervisor-result.json',{'status':'COMPLETE' if success else 'FAILED','reason':reason,'worker_exit_code':code,'worker_pid':proc.pid,'elapsed_seconds':c.clock()-start,'manifest_SHA256':expected,'verification_SHA256':c.file_sha(DEST/'verification.json'),'peak_observed_process_tree_RSS_bytes':peak,'RSS_scope':'0.25second observations,transientpeaksnotproven','source_worker_SHA256':workerSHA,'source_supervisor_SHA256':supervisorSHA,'network_requests':0,'retry':False,'new_admitted_documents':0},OUTPUT,'supervisor');raise SystemExit(0 if success else 1)
 except SystemExit:raise
 except BaseException as error:stop();c.terminal_write(DEST/'supervisor-result.json',{'status':'FAILED','error':str(error),'network_requests':0,'new_admitted_documents':0,'retry':False},OUTPUT,'supervisor');raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--manifest-sha256',required=True);p.add_argument('--source-worker-sha256',required=True);p.add_argument('--source-supervisor-sha256',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');a=p.parse_args();pins(a.manifest_sha256)
 if a.worker:worker(a.manifest_sha256,a.source_worker_sha256,a.source_supervisor_sha256)
 elif a.execute:execute(a.manifest_sha256,a.source_worker_sha256,a.source_supervisor_sha256)
 else:print(json.dumps({'status':'READY_VERIFIER_NOT_EXECUTED','manifest_SHA256':a.manifest_sha256}))
