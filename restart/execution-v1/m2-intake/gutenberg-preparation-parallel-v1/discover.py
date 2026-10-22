"""Two-request PG1342 discovery; preparation is offline until --execute dispatch."""
import argparse,datetime,hashlib,json,os,pathlib,re,shutil,signal,subprocess,sys,time,urllib.request
import xml.etree.ElementTree as ET
HERE=pathlib.Path(__file__).resolve().parent;EXEC=HERE.parents[1];REPO=EXEC.parents[1]
sys.path.insert(0,str(REPO/'src'));sys.path.insert(0,str(EXEC))
from acquire_sources import ROOT,CONTRACT,IntakeLedger
DEST=ROOT/'gutenberg-discovery-pilot-v1'
META='https://www.gutenberg.org/cache/epub/1342/pg1342.rdf'
CANONICAL='https://www.gutenberg.org/cache/epub/1342/pg1342.txt'
TEXT='https://mirror.cs.odu.edu/gutenberg-epub/1342/pg1342.txt'
CAPS={'metadata':2000000,'text':18000000};TOTAL_CAP=20000000;OUTPUT_CAP=100000000
WORKER_SECONDS=290;SUPERVISOR_SECONDS=300;TERMINAL_RESERVE=1000000
NS={'pg':'http://www.gutenberg.org/2009/pgterms/','dct':'http://purl.org/dc/terms/','rdf':'http://www.w3.org/1999/02/22-rdf-syntax-ns#'}
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*a,**kw):raise ValueError('Redirect refused; no implicit uncharged hops')
def sha(b):return hashlib.sha256(b).hexdigest()
def size_tree(root):return sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
def output_guard(root,additional):
 if additional<0 or size_tree(root)+additional>OUTPUT_CAP-TERMINAL_RESERVE:raise ValueError('Aggregate output cap')
def write(root,name,value):
 b=(json.dumps(value,indent=2,ensure_ascii=False)+'\n').encode();output_guard(root,len(b))
 with (root/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def storage():
 policy=json.loads((EXEC/'disk-budget.json').read_text());total=0
 for base,dirs,files in os.walk(ROOT):
  for name in dirs+files:
   if (pathlib.Path(base)/name).is_symlink():raise ValueError('Intake symlink')
  total+=sum((pathlib.Path(base)/n).stat().st_size for n in files)
 if total+OUTPUT_CAP>min(policy['raw_download_cap_bytes'],policy['processed_data_cap_bytes']):raise ValueError('Conservative combined raw/processed cap')
 reserve=policy['free_disk_floor_bytes']+policy['weights_checkpoints_reserved_bytes']+policy['scratch_cap_bytes']
 if shutil.disk_usage(ROOT).free<reserve+OUTPUT_CAP:raise ValueError('Storage reserves')
 return reserve

def parse_metadata(raw):
 if re.search(br'<!DOCTYPE|<!ENTITY',raw,re.I):raise ValueError('DTD/entity denied')
 root=ET.fromstring(raw);book=root.find('pg:ebook',NS)
 if book is None or book.get('{'+NS['rdf']+'}about') not in ['ebooks/1342','https://www.gutenberg.org/ebooks/1342','http://www.gutenberg.org/ebooks/1342']:raise ValueError('PG identifier mismatch')
 title=book.findtext('dct:title',namespaces=NS)
 if title!='Pride and Prejudice':raise ValueError('Unexpected title/edition')
 if not any((x.text or '').strip()=='en' for x in book.findall('dct:language//rdf:value',NS)):raise ValueError('English language metadata missing')
 people=[]
 for role in list(book):
  agent=role.find('pg:agent',NS)
  if agent is not None:people.append({'role':role.tag,'fields':{x.tag:x.text for x in agent},'attributes':dict(agent.attrib)})
 if not any('Austen, Jane' in (p['fields'].get('{'+NS['pg']+'}name') or '') for p in people):raise ValueError('Austen contributor missing')
 if any(p['role'].endswith('}trl') for p in people):raise ValueError('Translated edition; stop for review')
 formats=[]
 for f in book.findall('dct:hasFormat/pg:file',NS):formats.append({'url':f.get('{'+NS['rdf']+'}about'),'fields':ET.tostring(f,encoding='unicode')})
 allowed={CANONICAL,CANONICAL.replace('https:','http:')}
 if not any(f['url'] in allowed for f in formats):raise ValueError('Exact canonical UTF8 artifact absent; no guessed fallback')
 return {'gutenberg_id':1342,'title':title,'all_contributors_and_roles':people,'all_format_metadata':formats,'metadata_xml_sha256':sha(raw),'selected_canonical_text':CANONICAL,'selected_mirror_text':TEXT,'rights_clearance':False}
def inspect_text(raw):
 text=raw.decode('utf-8-sig',errors='strict')
 start=list(re.finditer(r'^\*\*\* START OF THE PROJECT GUTENBERG EBOOK[^\n]*\*\*\*',text,re.M));end=list(re.finditer(r'^\*\*\* END OF THE PROJECT GUTENBERG EBOOK[^\n]*\*\*\*',text,re.M))
 if len(start)!=1 or len(end)!=1 or start[0].start()>=end[0].start():raise ValueError('Complete PG start/end markers required')
 if 'Pride and Prejudice' not in text[:10000] or 'Jane Austen' not in text[:10000]:raise ValueError('Header title/author mismatch')
 if 'PROJECT GUTENBERG LICENSE' not in text[end[0].end():].upper():raise ValueError('Full license footer absent')
 if not all(s.lower() in text[:100000].lower() for s in ['George Saintsbury','Hugh Thomson','George Allen','1894']):raise ValueError('Observed1894edition annotations missing; no edition substitution')
 chapter=re.search(r'^\s*Chapter\s+(?:I|1)\.?\s*$',text[start[0].end():end[0].start()],re.M|re.I)
 boundary=start[0].end()+chapter.start() if chapter else end[0].start()
 return {'raw_utf8_bytes':len(raw),'raw_sha256':sha(raw),'start_marker_offsets':[start[0].start(),start[0].end()],'end_marker_offsets':[end[0].start(),end[0].end()],'chapter1_found':bool(chapter),'frontmatter_until_chapter1_sha256':sha(text[:boundary].encode()),'edition_annotations_detected':{s:s.lower() in text[:boundary].lower() for s in ['George Saintsbury','Hugh Thomson','George Allen','1894','Chuck Greif','Internet Archive']},'preservation':'Exact entire raw file retained including front matter, preface, illustration captions, credits, full PG license and end matter. No strip/edit or chapter corpus created.','rights_status':'Pending edition/contributor/local-jurisdiction review; US public-domain metadata is not India clearance.','training_admitted':False}

def transfer(ledger,kind,root,started,reserve,opener=None):
 cap=CAPS[kind];url=META if kind=='metadata' else TEXT;path=root/(kind+'.raw');partial=root/(kind+'.partial');key='gutenberg1342-discovery-v1-'+kind
 if path.exists() or partial.exists():raise FileExistsError('No replay')
 output_guard(root,cap);ledger.reserve(key,requests=1,body_bytes=cap,output_bytes=cap);n=0
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity'})
  with (opener or urllib.request.build_opener(NoRedirect())).open(req,timeout=20) as response,partial.open('xb') as f:
   if response.geturl()!=url:raise ValueError('Unpinned URL')
   if response.headers.get('Content-Encoding') not in [None,'identity']:raise ValueError('Encoded body refused')
   length=response.headers.get('Content-Length')
   if length is not None and not 0<=int(length)<cap:raise ValueError('Body length reaches cap')
   headers={k:response.headers.get(k) for k in ['Content-Type','Content-Length','ETag','Last-Modified']}
   while n<cap:
    if time.monotonic()-started>=WORKER_SECONDS:raise TimeoutError('Worker deadline')
    ledger.check_time()
    if shutil.disk_usage(ROOT).free<reserve+65536:raise ValueError('Protected disk floor')
    b=response.read(min(65536,cap-n))
    if not b:break
    output_guard(root,len(b));n+=len(b);f.write(b);f.flush()
   if n>=cap:raise ValueError('Body reached cap; no unreserved EOF probe')
   if length is not None and int(length)!=n:raise ValueError('Truncated body')
   f.flush();os.fsync(f.fileno())
  raw=partial.read_bytes()
  # A transferred body stays charged even if later schema/edition review fails.
  ledger.finish(key,raw=raw);os.rename(partial,path)
  fd=os.open(root,os.O_RDONLY);os.fsync(fd);os.close(fd)
  return raw,{'key':key,'url':url,'file':str(path),'body_bytes':n,'sha256':sha(raw),'headers':headers,'reservation':cap}
 except BaseException:
  state=ledger.db.execute('SELECT state FROM attempts WHERE key=?',(key,)).fetchone()
  if state and state[0]=='pending':ledger.finish(key,raw=None)
  write(root,kind+'-failure.json',{'status':'FAILED_NO_RETRY','received_bytes':n,'conservative_reserved_bytes':cap,'url':url,'partial_file':str(partial)})
  raise

def worker():
 if os.getppid()!=int(os.environ['PG_DISCOVERY_PARENT']):raise ValueError('Parent supervisor mismatch')
 ledger=IntakeLedger(ROOT/'charges',CONTRACT);began=time.monotonic();transfers=[]
 try:
  reserve=storage();write(DEST,'preflight.json',{'body_caps':CAPS,'total_body_cap':TOTAL_CAP,'output_cap':OUTPUT_CAP,'worker_seconds':WORKER_SECONDS,'supervisor_seconds':SUPERVISOR_SECONDS,'urls':[META,TEXT],'mirror_mapping':'Official MIRRORS.ALL lists ODU gutenberg-epub generated collection; generated collection has1342/pg1342.txt path. Fetch only if official RDF includes exact canonical text artifact.','preserve_entire_raw':True,'no_retries':True})
  raw,receipt=transfer(ledger,'metadata',DEST,began,reserve);transfers.append(receipt);metadata=parse_metadata(raw);write(DEST,'metadata-inspection.json',metadata)
  raw,receipt=transfer(ledger,'text',DEST,began,reserve);transfers.append(receipt);write(DEST,'text-inspection.json',inspect_text(raw))
  write(DEST,'receipt.json',{'status':'DISCOVERY_RAW_COMPLETE_NOT_ADMITTED','transfers':transfers,'global_reserved':ledger.totals(),'global_actual_successful_bytes':ledger.db.execute('SELECT coalesce(sum(actual_bytes),0) FROM attempts').fetchone()[0],'new_admitted_tokens':0,'elapsed_seconds':time.monotonic()-began})
 except BaseException as e:
  write(DEST,'failure.json',{'status':'TERMINAL_DISCOVERY_FAILURE_NO_RETRY','error_type':type(e).__name__,'error':str(e),'successful_transfers':transfers,'global_reserved':ledger.totals(),'new_admitted_tokens':0});raise
 finally:ledger.close()
def main():
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');a=p.parse_args()
 if a.worker:return worker()
 if not a.execute:print(json.dumps({'status':'PREPARED_NO_NETWORK','urls':[META,TEXT],'total_response_cap':TOTAL_CAP,'output_cap':OUTPUT_CAP,'supervisor_seconds':SUPERVISOR_SECONDS}));return
 DEST.mkdir(exist_ok=False);env=dict(os.environ,PG_DISCOVERY_PARENT=str(os.getpid()));start=time.monotonic()
 child=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),'--worker'],env=env,start_new_session=True)
 write(DEST,'supervisor-start.json',{'worker_pid':child.pid,'parent_pid':os.getpid(),'timeout_seconds':SUPERVISOR_SECONDS,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()});expired=False
 try:code=child.wait(timeout=SUPERVISOR_SECONDS)
 except subprocess.TimeoutExpired:
  expired=True;os.killpg(child.pid,signal.SIGKILL);code=child.wait()
 write(DEST,'supervisor-result.json',{'status':'PASS' if code==0 else 'FAIL','exit_code':code,'timeout':expired,'elapsed_seconds':time.monotonic()-start,'no_retry':True});raise SystemExit(0 if code==0 else 1)
if __name__=='__main__':main()
