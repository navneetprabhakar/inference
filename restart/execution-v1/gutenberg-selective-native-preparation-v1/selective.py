"""Offline six-member prefix capture; intentional partial archive, no full EOF claim."""
import argparse,gzip,hashlib,json,os,platform,re,shutil,signal,subprocess,sys,tarfile,time
from pathlib import Path,PurePosixPath
HERE=Path(__file__).resolve().parent;EXEC=HERE.parent
sys.path.insert(0,str(EXEC/'gutenberg-catalog-compact-preparation-v2'));import compact as c
sys.path.insert(0,str(EXEC/'gutenberg-nativefield-salvage-preparation-v1'));import add_fields
import parse_rdf_2MB
ARCHIVE=c.ARCHIVE;SOURCE=c.DEST;DEST=EXEC/'m2-intake/gutenberg-selective-native-six-v1';MANIFEST=HERE/'manifest.json';PROFILE=HERE/'profile.json'
PROFILE_SHA='06c26f6494d6a18d4d44fa30460de12a96319a762289b02e761eed9884d4ef46'
OUTPUT=8000000;DECODED=1100000000;WORKER=55;EXTERNAL=60;RSS=1000000000;MAX_SELECTED=2000000;FINAL_ORDINAL=27090;HEADROOM=1048576

def bound_paths():
 return [HERE/'selective.py',HERE/'parse_rdf_2MB.py',HERE/'targets.json',HERE/'check.py',PROFILE,EXEC/'gutenberg-nativefield-salvage-preparation-v1/add_fields.py',c.HERE/'compact.py',c.HERE/'parse_rdf.py',c.HERE/'archive_reader.py',c.READER_DIR/'inventory.py',c.READER_DIR/'supervisor.py',c.READER_DIR/'shared_clock.py',EXEC/'disk-budget.json',SOURCE/'worker-result.json',SOURCE/'supervisor-result.json',SOURCE/'catalog-0.sqlite3',SOURCE/'catalog-1.sqlite3',ARCHIVE]
def pins(expected):
 if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected) or MANIFEST.is_symlink() or c.file_sha(MANIFEST)!=expected:raise ValueError('Explicit reviewed manifest digest required')
 m=json.loads(MANIFEST.read_text());files=m.get('files_SHA256',{})
 if set(files)!={str(p.resolve()) for p in bound_paths()} or m['environment']!=c.environment():raise ValueError('Exact dependency inventory/runtime required')
 for name,digest in files.items():
  p=Path(name)
  if p.is_symlink() or not p.is_file() or c.file_sha(p)!=digest:raise ValueError('Pinned input changed:'+name)
 if c.file_sha(PROFILE)!=PROFILE_SHA:raise ValueError('Profile pin mismatch')
 w=json.loads((SOURCE/'worker-result.json').read_text());s=json.loads((SOURCE/'supervisor-result.json').read_text())
 if w['status']!='COMPLETE_LOSSLESS_COMPACT_CATALOG_METADATA_ONLY_NO_ADMISSION' or s['status']!='COMPLETE' or s['worker_result_SHA256']!=c.file_sha(SOURCE/'worker-result.json'):raise ValueError('Complete source receipts required')
 if w['source_archive_SHA256']!=c.ARCHIVE_SHA or c.file_sha(ARCHIVE)!=c.ARCHIVE_SHA or ARCHIVE.stat().st_size!=126801976:raise ValueError('Original archive identity required')
 return m
class Guard:
 def __init__(self,output,start):
  self.output=output;self.start=start;self.limits={'decoded_bytes':DECODED};budget=json.loads((EXEC/'disk-budget.json').read_text());self.reserve=sum(budget[k] for k in ['weights_checkpoints_reserved_bytes','scratch_cap_bytes','free_disk_floor_bytes'])
  if c.size(c.ROOT)+OUTPUT>budget['processed_data_cap_bytes']:raise ValueError('Combined processed-data cap')
  if shutil.disk_usage(output).free<self.reserve+OUTPUT+32000000:raise ValueError('Protected preflight disk reserves')
 def check(self,additional=0):
  if not 0<=c.clock()-self.start<WORKER:raise TimeoutError('55sec worker deadline')
  if additional<0 or c.size(self.output)+additional>OUTPUT-HEADROOM:raise ValueError('8MB aggregate prewrite cap with1MB terminal headroom')
  if shutil.disk_usage(self.output).free<self.reserve+additional+32000000:raise ValueError('Protected disk reserves')
def save(path,data,guard):
 b=data if isinstance(data,bytes) else (json.dumps(data,indent=2)+'\n').encode();guard.check(len(b))
 with path.open('xb') as file:file.write(b);file.flush();os.fsync(file.fileno())
 return {'file':path.name,'bytes':len(b),'SHA256':c.sha(b)}
def scan(archive,targets,guard,stop_at=FINAL_ORDINAL):
 wanted={r['ordinal']:r for r in targets};found=[];ordinal=0
 if len(wanted)!=len(targets) or max(wanted)!=stop_at or any(r['bytes']>MAX_SELECTED for r in targets):raise ValueError('Exact bounded target selection required')
 with archive.open('rb') as handle:
  reader=c.archive_reader.StrictBZ2(handle);decoded=c.archive_reader.Decoded(reader,guard)
  while ordinal<stop_at:
   header=decoded.exact(512)
   if header==b'\0'*512:raise ValueError('Premature tar EOF before selected prefix completed')
   info=tarfile.TarInfo.frombuf(header,'utf-8','strict');ordinal+=1;name=PurePosixPath(info.name)
   if info.size<0 or name.is_absolute() or '..' in name.parts or len(info.name.encode())>4096 or not(info.isfile() or info.isdir()) or(info.isdir() and info.size):raise ValueError('Unsupported/unsafe tar header')
   target=wanted.get(ordinal)
   if target and (not info.isfile() or info.name!=target['name'] or info.size!=target['bytes'] or c.sha(header)!=target['header_SHA256']):raise ValueError('Selected source identity/header/size mismatch')
   chunks=[];h=hashlib.sha256();remaining=info.size
   while remaining:
    b=decoded.exact(min(65536,remaining));remaining-=len(b)
    if target:chunks.append(b);h.update(b)
   padding=(-info.size)%512
   if padding and decoded.exact(padding)!=b'\0'*padding:raise ValueError('Nonzero tar member padding')
   if target:
    raw=b''.join(chunks)
    if h.hexdigest()!=target['body_SHA256'] or len(raw)!=target['bytes']:raise ValueError('Selected raw body hash/length mismatch')
    base='ordinal-'+str(ordinal);artifacts=[save(guard.output/(base+'.rdf'),raw,guard)]
    result={'target':{k:v for k,v in target.items() if k!='original_record'},'raw_body_verified':True,'source_archive_SHA256':c.ARCHIVE_SHA,'training_admitted':False}
    if target['kind']=='NATIVE_250_260_CAPTURE_ONLY':
     added=add_fields.add_native_fields(raw,target['original_record']);result['native_edition_publication_additions_v1']=added['native_edition_publication_additions_v1'];result['original_holds_unchanged']=added['holds'];result['native_roles_all']=added['contributors_and_all_roles']
    else:
     try:row=parse_rdf_2MB.parse(raw,info.name)
     except (ValueError,AssertionError,c.etree.XMLSyntaxError) as error:result.update({'derived_status':'HELD_PARSER_FAILURE_NO_FALLBACK','error':str(error)})
     else:
      payload=gzip.compress(json.dumps(row,ensure_ascii=True,separators=(',',':')).encode(),mtime=0);artifacts.append(save(guard.output/(base+'.derived-metadata.json.gz'),payload,guard));result.update({'derived_status':'PARSED_WITH_ISOLATED2MB_BYTE_BOUND_ONLY_NO_ADMISSION','ebook_ID':row['ebook_ID'],'holds':row['holds'],'original_English':row['original_English_composition'],'rights':row['edition_and_jurisdiction_rights'],'unknown_fields':row['unmapped_book_fields']})
    result['artifacts']=artifacts;save(guard.output/(base+'.receipt.json'),result,guard);found.append(result)
  guard.check()
  if len(found)!=len(targets):raise ValueError('Selected member count reconciliation')
  return {'stop_after_ordinal':ordinal,'selected_members':len(found),'selected_body_bytes':sum(r['target']['bytes'] for r in found),'decoded_prefix_bytes':decoded.n,'full_tar_EOF_verified':False,'full_bzip2_CRC_EOF_verified':False,'intentional_prefix_stop_no_completeness_claim':True,'results':found}
def worker(expected):
 pins(expected)
 if os.getppid()!=int(os.environ['PGSELECT_PARENT_PID']):raise ValueError('Direct live supervisor required')
 guard=Guard(DEST,float(os.environ['PGSELECT_START']))
 try:
  guard.check();targets=json.loads((HERE/'targets.json').read_text())['targets'];result=scan(ARCHIVE,targets,guard)
  c.terminal_write(DEST/'worker-result.json',{'status':'COMPLETE_SIX_SELECTED_RAW_BODIES_NO_ADMISSION','manifest_SHA256':expected,'profile_SHA256':PROFILE_SHA,'elapsed_seconds':c.clock()-guard.start,'network_requests':0,'new_admitted_documents':0,'new_admitted_tokens':0,**result},OUTPUT)
 except BaseException as error:c.terminal_write(DEST/'worker-result.json',{'status':'TERMINAL_FAILED_NO_RETRY','error':str(error),'elapsed_seconds':c.clock()-guard.start,'network_requests':0,'new_admitted_documents':0},OUTPUT);raise

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
   env=dict(os.environ,PGSELECT_PARENT_PID=str(os.getpid()),PGSELECT_START=str(start));proc=subprocess.Popen([sys.executable,str(HERE/'selective.py'),'--worker','--manifest-sha256',expected],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   while proc.poll() is None:
    left=EXTERNAL-(c.clock()-start)
    if left<=0:reason='external60secondcap';stop();break
    ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=min(1,left));rss,_=c.tree_rss_from_ps(ps.stdout,os.getpid());peak=max(peak,rss)
    if rss>RSS or c.size(DEST)>OUTPUT-HEADROOM or shutil.disk_usage(DEST).free<guard.reserve+32000000:reason='RSS_output_or_disk_cap';stop();break
    time.sleep(min(.25,max(0,EXTERNAL-(c.clock()-start))))
   code=proc.wait(timeout=2)
  w=json.loads((DEST/'worker-result.json').read_text());success=code==0 and reason is None and w['status']=='COMPLETE_SIX_SELECTED_RAW_BODIES_NO_ADMISSION' and c.clock()-start<EXTERNAL and c.size(DEST)<=OUTPUT-HEADROOM
  c.terminal_write(DEST/'supervisor-result.json',{'status':'COMPLETE' if success else 'FAILED','reason':reason,'worker_exit_code':code,'worker_pid':proc.pid,'elapsed_seconds':c.clock()-start,'manifest_SHA256':expected,'worker_result_SHA256':c.file_sha(DEST/'worker-result.json'),'peak_observed_process_tree_RSS_bytes':peak,'RSS_scope':'0.25sec observations, transient peaks not proven','network_requests':0,'retry':False,'new_admitted_documents':0},OUTPUT,'supervisor');raise SystemExit(0 if success else 1)
 except SystemExit:raise
 except BaseException as error:stop();c.terminal_write(DEST/'supervisor-result.json',{'status':'FAILED','error':str(error),'network_requests':0,'retry':False,'new_admitted_documents':0},OUTPUT,'supervisor');raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--manifest-sha256',required=True);p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');args=p.parse_args();pins(args.manifest_sha256)
 if args.worker:worker(args.manifest_sha256)
 elif args.execute:execute(args.manifest_sha256)
 else:print(json.dumps({'status':'READY_NOT_EXECUTED','manifest_SHA256':args.manifest_sha256}))
