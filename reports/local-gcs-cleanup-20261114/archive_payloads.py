"""Archive explicitly inventoried inactive payloads; verify before local eviction.
Keeps source, small manifests, both current local model bundles and runtime.
"""
import concurrent.futures,datetime,hashlib,json,os,subprocess,sys,tarfile,threading
from pathlib import Path
from urllib.parse import quote
sys.path.insert(0,str(Path('reports/ownbase-budget50-v1').resolve()))
from gcp_api import request
R=Path('reports/local-gcs-cleanup-20261114');W=Path('runs/gcs-cleanup-20261114');W.mkdir(exist_ok=True)
plan=json.loads((R/'plan.json').read_text());lock=threading.Lock();receipts=[]
bucket='forge-ownbase-a100-20261110';prefix='local-archive-20261114'
def digest(p,kind='sha256'):
 with p.open('rb') as f:return hashlib.file_digest(f,kind).digest()
def save():
 with lock:
  (R/'progress.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'completed_groups':len(receipts),'planned_groups':len(plan['groups']),'reclaimed_bytes':sum(r['source_bytes'] for r in receipts),'receipts':receipts},indent=2)+'\n')
def work(item):
 group,files=item;key=group.replace('/','__');receiptfile=R/(key+'.json')
 if receiptfile.exists():
  old=json.loads(receiptfile.read_text())
  if old.get('evicted'):receipts.append(old);save();return
 # Abort rather than archive any open source file or a changed plan.
 proc=subprocess.run(['lsof','-F','n','--',*[r['path'] for r in files]],capture_output=True,text=True)
 if proc.stdout:raise RuntimeError('Open planned source files for '+group)
 assert proc.returncode in (0,1)
 for r in files:
  p=Path(r['path']);st=p.stat();assert st.st_size==r['bytes'] and st.st_mtime_ns==r['mtime_ns'];r['sha256']=digest(p).hex()
 listing=W/(key+'.files');listing.write_text(''.join(r['path']+'\n' for r in files));archive=W/(key+'.tar.zst')
 env=dict(os.environ,CLOUDSDK_STORAGE_PARALLEL_COMPOSITE_UPLOAD_ENABLED='false',COPYFILE_DISABLE='1')
 with archive.open('wb') as f:
  tar=subprocess.Popen(['tar','-cf','-','-T',str(listing)],stdout=subprocess.PIPE,env=env)
  z=subprocess.run(['zstd','-3','-T2','-q'],stdin=tar.stdout,stdout=f,check=True);tar.stdout.close();assert tar.wait()==0
 # Full local round trip verifies each file against its original SHA before upload.
 dec=subprocess.Popen(['zstd','-dc',str(archive)],stdout=subprocess.PIPE)
 expected={r['path']:r for r in files};seen=set()
 with tarfile.open(fileobj=dec.stdout,mode='r|') as t:
  for member in t:
   if not member.isfile():continue
   name=member.name.removeprefix('./');assert name in expected
   stream=t.extractfile(member);assert hashlib.file_digest(stream,'sha256').hexdigest()==expected[name]['sha256'];seen.add(name)
 dec.stdout.read();dec.stdout.close()
 assert dec.wait()==0 and seen==set(expected)
 sha=digest(archive).hex();import base64
 md5=base64.b64encode(digest(archive,'md5')).decode();obj=prefix+'/'+key+'-'+sha+'.tar.zst';uri='gs://'+bucket+'/'+obj
 subprocess.run(['gcloud','storage','cp',str(archive),uri,'--quiet'],env=env,check=True,timeout=21600,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 remote=request('https://storage.googleapis.com/storage/v1/b/'+bucket+'/o/'+quote(obj,safe=''),timeout=60)
 assert int(remote['size'])==archive.stat().st_size and remote.get('md5Hash')==md5
 receipt={'group':group,'source_bytes':sum(r['bytes'] for r in files),'archive_bytes':archive.stat().st_size,'archive_sha256':sha,'archive_md5':md5,'gcs_uri':uri,'generation':remote['generation'],'verification':'Full local decompression SHA256 per file; provider-computed GCS MD5 and size equal local archive; no independent full remote SHA readback claim.','files':files,'evicted':False,'restore_command':'gcloud storage cp '+uri+' /tmp/'+key+'.tar.zst && zstd -dc /tmp/'+key+'.tar.zst | tar -xf - -C "$REPO_ROOT"'}
 receiptfile.write_text(json.dumps(receipt,indent=2)+'\n')
 # Backup restore manifest too, and verify exact JSON after remote readback.
 manifestobj=obj+'.json';subprocess.run(['gcloud','storage','cp',str(receiptfile),'gs://'+bucket+'/'+manifestobj,'--quiet'],env=env,check=True,timeout=120,capture_output=True)
 back=request('https://storage.googleapis.com/storage/v1/b/'+bucket+'/o/'+quote(manifestobj,safe='')+'?alt=media');assert back==receipt
 for r in files:
  p=Path(r['path']);st=p.stat();assert st.st_size==r['bytes'] and st.st_mtime_ns==r['mtime_ns'] and digest(p).hex()==r['sha256']
 # All checks for the group passed. Only the enumerated untracked payloads are removed.
 for r in files:Path(r['path']).unlink()
 receipt['evicted']=True;receipt['utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();receiptfile.write_text(json.dumps(receipt,indent=2)+'\n')
 archive.unlink();listing.unlink();receipts.append(receipt);save();print(json.dumps({'group':group,'reclaimed_bytes':receipt['source_bytes']}),flush=True)
items=sorted(plan['groups'].items(),key=lambda kv:sum(r['bytes'] for r in kv[1]))
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 futures=[pool.submit(work,item) for item in items]
 for f in concurrent.futures.as_completed(futures):
  try:f.result()
  except BaseException:
   for pending in futures:pending.cancel()
   raise
save()
