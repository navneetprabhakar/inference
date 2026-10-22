"""Two bounded official PyPI requests; inspect wheel as inert bytes, never install/import."""
import argparse,base64,csv,email.parser,hashlib,importlib.util,io,json,os,pathlib,re,shutil,signal,stat,subprocess,sys,time,urllib.request,urllib.error,urllib.parse,zipfile,ssl,sqlite3,platform,socket,http.client
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;REPO=BASE.parents[1];ROOT=BASE/'m2-intake';OUT=ROOT/'mwparserfromhell-0.7.2-inert-wheel-v1'
PACKAGE='mwparserfromhell';VERSION='0.7.2';FILENAME='mwparserfromhell-0.7.2-cp312-cp312-macosx_11_0_arm64.whl';EXPECTED='efe6e5255379ff66a08d2102004b26a456692dafbab0cb1e52bed275a43f1c4c';META_URL='https://pypi.org/pypi/mwparserfromhell/0.7.2/json'
PREFIX='mwparserfromhell-0.7.2-inert-v1-';OUTPUT=5000000;META_CAP=200000;WHEEL_CAP=800000;FREE=53474836480;WORK=55;EXTERNAL=60;RSS=1000000000
CAPS={'requests':2,'body_bytes':1000000,'metadata_body_bytes':META_CAP,'wheel_body_bytes':WHEEL_CAP,'output_bytes':OUTPUT,'worker_seconds':WORK,'external_seconds':EXTERNAL,'observed_RSS_bytes':RSS,'ZIP_entries':512,'ZIP_member_decoded_bytes':1000000,'ZIP_total_decoded_bytes':4000000,'redirects':0,'retries':0,'installations':0,'downloaded_code_imports':0}
SLOTS={'worker-result.json':65536,'supervisor-result.json':32768};DECISION=BASE/'generic-wikitext-parser-path-v1/decision.json';CA=pathlib.Path('/opt/homebrew/etc/ca-certificates/cert.pem');TLS=ROOT/'gutenberg-preparation-parallel-v4/discover.py'
def clk():return time.monotonic()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def size(p):return sum(f.stat().st_size for f in p.rglob('*') if f.is_file())
def runtime():return {'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'openssl':ssl.OPENSSL_VERSION,'sqlite':sqlite3.sqlite_version,'platform':platform.platform()}
def inventory():
 ps=[HERE/n for n in ['acquire.py','checks.py','code_guard.py','profile.json']]+[DECISION,CA,TLS,BASE/'acquire_sources.py',REPO/'src/slm/data/intake_ledger.py',REPO/'src/slm/data/schema.py',BASE/'authorization.json',BASE/'source-acquisition-authorization.json',BASE/'disk-budget.json',pathlib.Path(sys.executable)]
 ps += [pathlib.Path(m.__file__) for m in [zipfile,csv,email.parser,urllib.request,urllib.error,urllib.parse,ssl,sqlite3,socket,http.client,hashlib,subprocess] if getattr(m,'__file__',None)]
 return {str(p.resolve()) for p in ps}
def verify(code,profile):
 import code_guard;code_guard.verify(code)
 if sha(HERE/'profile.json')!=profile:raise ValueError('external_profile_pin')
 p=json.loads((HERE/'profile.json').read_text());d=json.loads(DECISION.read_text())['candidate_dependency']
 if p['limits']!=CAPS or p['metadata_URL']!=META_URL or p['wheel_filename']!=FILENAME or p['wheel_SHA256']!=EXPECTED or p['output']!=str(OUT) or p['ledger_prefix']!=PREFIX:raise ValueError('exact_policy_identity')
 if d['name']!=PACKAGE or d['pinned_stable_release_for_investigation']!=VERSION or d['wheel']!=FILENAME or d['publisher_SHA256']!=EXPECTED:raise ValueError('retained_primary_investigation_pin')
 if sys.version_info[:2]!=(3,12) or sys.platform!='darwin' or platform.machine()!='arm64':raise ValueError('exact_cp312_macos_arm64_runtime')
 return p
def dependencies():
 sys.path[:0]=[str(REPO/'src'),str(BASE)]
 import acquire_sources
 from slm.data import intake_ledger
 if pathlib.Path(acquire_sources.__file__).resolve()!=BASE/'acquire_sources.py' or pathlib.Path(intake_ledger.__file__).resolve()!=REPO/'src/slm/data/intake_ledger.py':raise ValueError('import_origin')
 spec=importlib.util.spec_from_file_location('pinned_wheel_TLS',TLS);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.trusted_context()
 return acquire_sources.IntakeLedger,acquire_sources.CONTRACT,m
def disk(n=0):
 if size(OUT)+n>OUTPUT-131072 or size(ROOT)+n>64000000000 or shutil.disk_usage(ROOT).free<FREE+n:raise ValueError('output_intake_disk_reserves')
def write(name,obj):
 b=(json.dumps(obj,indent=2,ensure_ascii=False)+'\n').encode();disk(len(b))
 with (OUT/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def terminal(name,obj):
 b=(json.dumps(obj,indent=2)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('terminal_slot')
 with (OUT/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def parse_metadata(raw):
 def pairs(xs):
  result={}
  for k,v in xs:
   if k in result:raise ValueError('duplicate_JSON_field')
   result[k]=v
  return result
 m=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs)
 if m['info']['name']!=PACKAGE or m['info']['version']!=VERSION:raise ValueError('exact_PyPI_name_version')
 matches=[x for x in m['urls'] if x['filename']==FILENAME]
 if len(matches)!=1:raise ValueError('one_exact_compatible_wheel')
 w=matches[0];u=urllib.parse.urlsplit(w['url'])
 if w['digests']['sha256']!=EXPECTED or w['packagetype']!='bdist_wheel' or w['python_version']!='cp312' or w.get('yanked') is not False or type(w['size']) is not int or not 0<w['size']<WHEEL_CAP:raise ValueError('publisher_wheel_metadata')
 if u.scheme!='https' or u.netloc!='files.pythonhosted.org' or not u.path.startswith('/packages/') or not u.path.endswith('/'+FILENAME) or u.query or u.fragment or '%' in u.path:raise ValueError('exact_official_metadata_derived_wheel_URL')
 return {'filename':FILENAME,'URL':w['url'],'bytes':w['size'],'SHA256':EXPECTED,'reported_license':m['info'].get('license'),'reported_license_expression':m['info'].get('license_expression'),'no_URL_guessed':True}
def valid_path(name):
 if not isinstance(name,str) or not name or '\x00' in name or '\\' in name or ':' in name or name.startswith('/') or any(x in ['','.','..'] for x in name.rstrip('/').split('/')):raise ValueError('unsafe_ZIP_path')
 return name

def inspect_wheel(raw):
 if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('exact_publisher_wheel_SHA256')
 prefix=PACKAGE+'-'+VERSION+'.dist-info/';members={};digests={};sizes={};held=[];total=0;folded=set()
 with zipfile.ZipFile(io.BytesIO(raw),'r') as z:
  infos=z.infolist()
  if not 1<=len(infos)<=CAPS['ZIP_entries']:raise ValueError('ZIP_entry_cap')
  for i in infos:
   if i.orig_filename!=i.filename:raise ValueError('ZIP_filename_normalization_or_NUL')
   name=valid_path(i.orig_filename);fold=name.casefold()
   if fold in folded:raise ValueError('duplicate_or_casecolliding_ZIP_path')
   folded.add(fold);kind=stat.S_IFMT(i.external_attr>>16)
   if i.flag_bits&1 or i.compress_type not in [zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED] or kind not in [0,stat.S_IFREG,stat.S_IFDIR] or (kind==stat.S_IFDIR)!=i.is_dir():raise ValueError('unsupported_ZIP_member_mode')
   if i.file_size>CAPS['ZIP_member_decoded_bytes'] or i.file_size<0 or total+i.file_size>CAPS['ZIP_total_decoded_bytes']:raise ValueError('ZIP_declared_decode_cap')
   if i.is_dir():continue
   n=0;h=hashlib.sha256();parts=[]
   with z.open(i,'r') as f:
    while True:
     b=f.read(min(65536,CAPS['ZIP_member_decoded_bytes']+1-n))
     if not b:break
     n+=len(b);total+=len(b)
     if n>CAPS['ZIP_member_decoded_bytes'] or total>CAPS['ZIP_total_decoded_bytes']:raise ValueError('ZIP_actual_decode_cap')
     h.update(b)
     # Only inert wheel metadata/license CSV/text held in memory. No code imported.
     if name.startswith(prefix):parts.append(b)
   if n!=i.file_size:raise ValueError('ZIP_size_CRC_mismatch')
   members[name]={'bytes':n,'SHA256':h.hexdigest(),'CRC32':format(i.CRC,'08x')};digests[name]=h.digest();sizes[name]=n
   if name.startswith(prefix):held.append((name,b''.join(parts)))
  data=dict(held);required=[prefix+x for x in ['METADATA','WHEEL','RECORD']]
  if any(n not in data for n in required):raise ValueError('wheel_metadata_missing')
  metadata=email.parser.BytesParser().parsebytes(data[prefix+'METADATA']);wheel=email.parser.BytesParser().parsebytes(data[prefix+'WHEEL'])
  if metadata.get_all('Name')!=[PACKAGE] or metadata.get_all('Version')!=[VERSION] or wheel.get_all('Tag')!=['cp312-cp312-macosx_11_0_arm64']:raise ValueError('internal_wheel_name_version_tag')
  licenses=[(n,b) for n,b in held if n in [prefix+'LICENSE',prefix+'LICENSE.txt'] or n.startswith(prefix+'licenses/')]
  if not licenses:raise ValueError('license_component_missing')
  texts=[]
  for name,b in licenses:
   t=b.decode('utf-8');texts.append({'file':name,'SHA256':hashlib.sha256(b).hexdigest(),'text':t})
  canonical_MIT='Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions: The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.'
  normalized=[' '.join(t['text'].split()) for t in texts]
  if not any(canonical_MIT in t and not t.split(canonical_MIT,1)[1].strip() for t in normalized):raise ValueError('complete_standard_MIT_clauses_not_matched')
  rec=csv.reader(io.StringIO(data[prefix+'RECORD'].decode('utf-8'),newline=''));seen=set()
  for row in rec:
   if len(row)!=3 or row[0] not in members or row[0] in seen:raise ValueError('RECORD_identity_coverage')
   name,digest,n=row;seen.add(name)
   if name==prefix+'RECORD':
    if digest or n:raise ValueError('RECORD_self_hash_must_be_empty')
   elif digest!='sha256='+base64.urlsafe_b64encode(digests[name]).decode().rstrip('=') or n!=str(sizes[name]):raise ValueError('RECORD_hash_size_mismatch')
  if seen!=set(members):raise ValueError('RECORD_all_file_coverage')
 return {'status':'BOUNDED_WHEEL_ZIP_CRC_RECORD_METADATA_LICENSE_VERIFIED_AS_INERT_DATA','files':members,'ZIP_entries':len(infos),'decoded_bytes':total,'name':metadata['Name'],'version':metadata['Version'],'wheel_tag':wheel['Tag'],'license_texts':texts,'complete_standard_MIT_clauses_matched':True,'license_scope':'Captured package license text only, not corpus/model rights clearance.','all_CRCs_complete':True,'all_RECORD_files_hash_and_size_verified':True,'installations':0,'downloaded_code_imports':0,'code_files_extracted_to_filesystem':0}

def reserve_output(l):l.reserve(PREFIX+'output',output_bytes=OUTPUT)
def require_output(l):
 r=l.db.execute('select charge,state from attempts where key=?',(PREFIX+'output',)).fetchone()
 if not r or r[1]!='pending' or json.loads(r[0])!={'requests':0,'body_bytes':0,'rows':0,'output_bytes':OUTPUT}:raise ValueError('exact_output_precharge_required')
def settle(l):
 rows=list(l.db.execute('select key,state from attempts where key in (?,?,?)',(PREFIX+'output',PREFIX+'metadata',PREFIX+'wheel')))
 for k,s in rows:
  if s=='pending':l.finish(k,raw=None)
 return [{'key':k,'state':l.db.execute('select state from attempts where key=?',(k,)).fetchone()[0]} for k,s in rows]
def cleanup():
 try:
  L,C,T=dependencies();l=L(ROOT/'charges',C)
  try:return settle(l)
  finally:l.close()
 except BaseException as e:return {'cleanup_hold':type(e).__name__+':'+str(e)[:300]}
def fetch(l,opener,key,url,cap,filename,start,expected_size=None,expected_sha=None):
 if clk()-start>=WORK:raise TimeoutError('expired_before_request_reservation')
 l.reserve(key,requests=1,body_bytes=cap);p=OUT/filename;raw=bytearray()
 try:
  try:res=opener.open(urllib.request.Request(url,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity'}),timeout=min(15,max(.01,WORK-(clk()-start))))
  except urllib.error.HTTPError as e:res=e
  with res:
   hs=json.dumps(list(res.headers.items()),ensure_ascii=False).encode();write(filename+'-headers.json',{'status':res.code,'URL':res.geturl(),'header_bytes':len(hs),'header_SHA256':hashlib.sha256(hs).hexdigest(),'prefix_hex':hs[:65536].hex(),'prefix_only':len(hs)>65536})
   if len(hs)>65536 or res.code!=200 or res.geturl()!=url or res.headers.get('Content-Encoding') not in [None,'identity']:raise ValueError('exact_HTTP_200_URL_identity_bounded_headers')
   lengths=res.headers.get_all('Content-Length',[])
   if len(lengths)>1 or (lengths and (not lengths[0].isdigit() or int(lengths[0])>=cap)):raise ValueError('advertised_length_bound')
   if expected_size is not None and lengths!=[str(expected_size)]:raise ValueError('publisher_length_exact')
   with p.open('xb') as f:
    try:
     while len(raw)<cap:
      if clk()-start>=WORK:raise TimeoutError('worker_deadline')
      l.check_time();b=res.read1(min(65536,cap-len(raw)))
      if not b:break
      disk(len(b));f.write(b);f.flush();raw.extend(b)
    finally:f.flush();os.fsync(f.fileno())
   if len(raw)==cap or (lengths and len(raw)!=int(lengths[0])):raise ValueError('body_cap_or_truncation')
   if expected_size is not None and len(raw)!=expected_size:raise ValueError('publisher_size_mismatch')
   if expected_sha is not None and hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError('publisher_SHA256_mismatch')
  l.finish(key,raw=bytes(raw));return bytes(raw)
 except BaseException:
  if l.db.execute('select state from attempts where key=?',(key,)).fetchone()==('pending',):l.finish(key,raw=None)
  raise

def worker(a):
 verify(a.code_pins_sha256,a.profile_sha256);start=float(a.start);l=None
 if os.getppid()!=a.supervisor_pid:raise ValueError('parent_identity')
 def stop(s,f):raise TimeoutError('worker_deadline_alarm')
 signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,max(.001,WORK-(clk()-start)))
 try:
  L,C,T=dependencies();l=L(ROOT/'charges',C);require_output(l);opener=urllib.request.build_opener(T.NoRedirect(),urllib.request.HTTPSHandler(context=T.trusted_context()))
  raw=fetch(l,opener,PREFIX+'metadata',META_URL,META_CAP,'metadata.partial',start);selection=parse_metadata(raw);os.rename(OUT/'metadata.partial',OUT/'metadata.json');write('wheel-selection.json',selection)
  wheel=fetch(l,opener,PREFIX+'wheel',selection['URL'],WHEEL_CAP,'wheel.partial',start,selection['bytes'],selection['SHA256']);inspection=inspect_wheel(wheel);write('wheel-inspection.json',inspection)
  verify(a.code_pins_sha256,a.profile_sha256);os.rename(OUT/'wheel.partial',OUT/FILENAME);fd=os.open(OUT,os.O_RDONLY);os.fsync(fd);os.close(fd);l.finish(PREFIX+'output',raw=b'')
  terminal('worker-result.json',{'status':'COMPLETE_INERT_WHEEL_ACQUIRED_AND_INSPECTED_NO_INSTALL','metadata_SHA256':hashlib.sha256(raw).hexdigest(),'wheel_SHA256':hashlib.sha256(wheel).hexdigest(),'wheel_bytes':len(wheel),'physical_requests':2,'global_reserved':l.totals(),'elapsed_seconds':clk()-start,'no_install_or_import':True,'new_admitted_documents':0})
 except BaseException as e:
  state=settle(l) if l is not None else None;terminal('worker-result.json',{'status':'TERMINAL_PARTIAL_NO_RETRY_NO_INSTALL','error':type(e).__name__+':'+str(e)[:1000],'ledger':state,'partials':[{'file':p.name,'bytes':p.stat().st_size,'SHA256':sha(p)} for p in OUT.glob('*.partial')],'new_admitted_documents':0});raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  if l is not None:l.close()
def kill(c):
 if c.poll() is None:
  try:os.killpg(c.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 c.wait(timeout=3)
def supervise(a):
 start=clk();child=None;created=False;charged=False;old={};peak=0
 def stop(s,f):raise RuntimeError('external_alarm_or_signal_'+str(s))
 try:
  for s in [signal.SIGTERM,signal.SIGINT,signal.SIGALRM]:old[s]=signal.signal(s,stop)
  remaining=EXTERNAL-(clk()-start)
  if remaining<=0:raise TimeoutError('expired_before_preflight')
  signal.setitimer(signal.ITIMER_REAL,remaining)
  verify(a.code_pins_sha256,a.profile_sha256);dependencies()
  if OUT.exists() or ROOT.is_symlink() or any(p.is_symlink() for p in ROOT.rglob('*')):raise ValueError('existing_output_or_intake_symlink')
  if size(ROOT)+OUTPUT>64000000000 or shutil.disk_usage(ROOT).free<FREE+OUTPUT:raise ValueError('combined_disk_reserves')
  L,C,T=dependencies();l=L(ROOT/'charges',C)
  try:reserve_output(l);charged=True
  finally:l.close()
  OUT.mkdir();created=True
  for name,n in SLOTS.items():
   with (OUT/name).open('xb') as f:f.write(b' '*n);f.flush();os.fsync(f.fileno())
  child=subprocess.Popen([sys.executable,str(HERE/'acquire.py'),'--worker','--supervisor-pid',str(os.getpid()),'--start',str(start),'--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True);write('ownership.json',{'worker_pid':child.pid,'supervisor_pid':os.getpid(),'start':start})
  while child.poll() is None:
   if clk()-start>=WORK:raise TimeoutError('worker55seconds')
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,timeout=1,check=True);rows=[tuple(map(int,x.split())) for x in ps.stdout.splitlines() if len(x.split())==3];owned={os.getpid()}
   while True:
    n=owned|{p for p,q,r in rows if q in owned}
    if n==owned:break
    owned=n
   rss=sum(r*1024 for p,q,r in rows if p in owned);peak=max(peak,rss)
   if rss>RSS:raise ValueError('observed_RSS_cap')
   disk();time.sleep(.1)
  child.wait(timeout=3);w=json.loads((OUT/'worker-result.json').read_text());state=cleanup();ok=child.returncode==0 and w.get('status')=='COMPLETE_INERT_WHEEL_ACQUIRED_AND_INSPECTED_NO_INSTALL' and sha(OUT/FILENAME)==EXPECTED and isinstance(state,list) and len(state)==3 and all(x['state']=='complete' for x in state)
  verify(a.code_pins_sha256,a.profile_sha256);terminal('supervisor-result.json',{'status':'COMPLETE_INERT_WHEEL_NO_INSTALL' if ok else 'PARTIAL_NO_RETRY_NO_INSTALL','worker_exit_code':child.returncode,'ledger':state,'elapsed_seconds':clk()-start,'peak_observed_RSS_bytes':peak,'worker_receipt_SHA256':sha(OUT/'worker-result.json'),'output_bytes':size(OUT),'new_admitted_documents':0});return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  state=cleanup() if charged else {'uncharged':True}
  if created:
   rec={'status':'PARTIAL_NO_RETRY_NO_INSTALL','reason':type(e).__name__+':'+str(e)[:1000],'ledger':state,'elapsed_seconds':clk()-start,'new_admitted_documents':0}
   if (OUT/'supervisor-result.json').exists():terminal('supervisor-result.json',rec)
   else:write('failure-before-slots.json',rec)
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  for s,h in old.items():signal.signal(s,h)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--supervisor-pid',type=int);p.add_argument('--start');p.add_argument('--code-pins-sha256',required=True);p.add_argument('--profile-sha256',required=True);a=p.parse_args()
 if a.worker:worker(a)
 elif a.execute:raise SystemExit(supervise(a))
 else:verify(a.code_pins_sha256,a.profile_sha256);dependencies();print('PREPARED_PINNED_NO_FETCH_NO_INSTALL')
