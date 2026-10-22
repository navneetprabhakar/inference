"""One bounded Wikibooks rendered-HTML transfer; metadata pinned, no retries/extraction."""
import datetime,hashlib,json,os,pathlib,re,shutil,signal,subprocess,sys,time,urllib.request
from acquire_sources import ROOT,CONTRACT,IntakeLedger,fetch
O=pathlib.Path(__file__).resolve().parent
D=ROOT/'wikibooks-rendered-pilot-v1'
BASE='https://dumps.wikimedia.org/other/enterprise_html/runs/20250320/'
NAME='enwikibooks-NS0-20250320-ENTERPRISE-HTML.json.tar.gz'
SIZE=798092108
MD5='62100fc4b079f084090541ecbca134c4'
CAP=1000000000
KEY='wikibooks-rendered-20250320-NS0-archive-once-v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def write(name,v):
 with (D/name).open('x') as f:json.dump(v,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def storage():
 disk=json.loads((O/'disk-budget.json').read_text())
 sizes={'raw':0,'processed':0,'scratch':0}
 for top in ROOT.iterdir():
  group='raw' if top.name in {'raw','metadata','wikibooks-rendered-pilot-v1'} else 'processed'
  if top.is_symlink():raise ValueError('Intake top-level symlink refused')
  if top.is_dir():
   for base,dirs,files in os.walk(top):
    for n in files:
     p=pathlib.Path(base)/n
     if p.is_symlink():raise ValueError('Intake file symlink refused')
     sizes[group]+=p.stat().st_size
  elif top.is_file():sizes[group]+=top.stat().st_size
 if sizes['raw']+CAP>disk['raw_download_cap_bytes']:raise ValueError('Raw disk ceiling')
 if sizes['processed']>disk['processed_data_cap_bytes']:raise ValueError('Processed disk ceiling')
 protected=disk['free_disk_floor_bytes']+disk['weights_checkpoints_reserved_bytes']+disk['scratch_cap_bytes']
 free=shutil.disk_usage(ROOT).free
 if free<protected+CAP:raise ValueError('Weight/scratch/free reserves')
 return {'bytes_by_conservative_class':sizes,'free_bytes':free,'protected_free_bytes':protected,'disk_policy_sha256':sha(O/'disk-budget.json')},protected

def worker():
 if os.getppid()!=int(os.environ['WIKIBOOKS_PILOT_PARENT_PID']):raise ValueError('Supervisor parent mismatch')
 l=IntakeLedger(ROOT/'charges',CONTRACT);written=0;started=time.monotonic();reserved=False
 partial=D/'raw.partial';target=D/NAME
 try:
  stats=fetch(l,'wikibooks-rendered-20250320-official-stats',BASE+NAME.replace('HTML.json.tar.gz','STATS.json'),cap=2000000)
  index=fetch(l,'wikibooks-rendered-20250320-official-index',BASE,cap=2000000)
  st=json.loads(stats)
  if set(st)!={'wiki','md5sum','date_modified'} or st['wiki']!='enwikibooks' or st['md5sum']!=MD5 or not st['date_modified'].startswith('2025-03-20T'):raise ValueError('Official stats mismatch')
  matches=re.findall(r'<a href="'+re.escape(NAME)+r'">[^\n]+?</a>\s+20-Mar-2025\s+12:20\s+(\d+)\s*$',index.decode(),re.M)
  if matches!=[str(SIZE)]:raise ValueError('Official fixed-run index size mismatch')
  headroom,protected=storage()
  write('preflight.json',{'status':'PINNED_METADATA_AND_DISK_PASS','url':BASE+NAME,'expected_bytes':SIZE,'publisher_md5':MD5,'stats_sha256':hashlib.sha256(stats).hexdigest(),'index_sha256':hashlib.sha256(index).hexdigest(),'metadata_note':'Official stats has MD5/date/wiki only; exact size independently pinned from official same-run directory index.','storage':headroom,'archive_body_reservation':CAP,'archive_attempts':1,'automatic_retry':False,'script_sha256':sha(pathlib.Path(__file__))})
  if partial.exists() or target.exists():raise FileExistsError('Existing payload; no automatic retry')
  l.reserve(KEY,requests=1,body_bytes=CAP,output_bytes=CAP);reserved=True
  digest=hashlib.sha256();md5=hashlib.md5()
  req=urllib.request.Request(BASE+NAME,headers={'User-Agent':'EnglishSLM-research-source-audit/1.0','Accept-Encoding':'identity'})
  with urllib.request.urlopen(req,timeout=30) as response,partial.open('xb') as f:
   if response.geturl()!=BASE+NAME:raise ValueError('Unexpected redirected snapshot URL')
   if response.headers.get('Content-Length') not in (None,str(SIZE)):raise ValueError('Content-Length mismatch')
   if response.headers.get('Content-Encoding') not in (None,'identity'):raise ValueError('Unexpected response encoding')
   while True:
    if time.monotonic()-started>=1800:raise TimeoutError('1800 second worker deadline')
    l.check_time()
    if shutil.disk_usage(ROOT).free<protected+4*1024**2:raise ValueError('Protected disk headroom reached')
    b=response.read(min(4*1024**2,SIZE+1-written))
    if not b:break
    written+=len(b);f.write(b);digest.update(b);md5.update(b)
    if written>SIZE:raise ValueError('Pinned response size exceeded')
    if written//(64*1024**2)!=(written-len(b))//(64*1024**2):
     print(json.dumps({'bytes_received':written,'expected_bytes':SIZE,'elapsed_seconds':round(time.monotonic()-started,2)}),flush=True)
   f.flush();os.fsync(f.fileno())
  if written!=SIZE or md5.hexdigest()!=MD5:raise ValueError('Full-body size/MD5 mismatch')
  # Same durable streaming completion convention as existing pilot downloaders;
  # avoids loading an 798MB body into memory for IntakeLedger.finish(raw=...).
  cur=l.db.execute('UPDATE attempts SET state=?,actual_bytes=?,body_sha256=? WHERE key=? AND state=?',('complete',written,digest.hexdigest(),KEY,'pending'))
  if cur.rowcount!=1:raise ValueError('Pending ledger completion lost')
  os.rename(partial,target)
  fd=os.open(D,os.O_RDONLY);os.fsync(fd);os.close(fd)
  write('download-receipt.json',{'status':'COMPLETE_COMPRESSED_SNAPSHOT_NOT_ADMITTED','url':BASE+NAME,'local_file':str(target),'bytes':written,'md5':md5.hexdigest(),'sha256':digest.hexdigest(),'elapsed_seconds':time.monotonic()-started,'ledger_reserved':l.totals(),'ledger_actual_successful_body_bytes':l.db.execute('SELECT coalesce(sum(actual_bytes),0) FROM attempts').fetchone()[0],'archive_key':KEY,'training_admitted':False,'integrity_scope':'Exact compressed size and publisher MD5 verified; gzip/tar/schema integrity remains for separately bounded inspection.','extracted_bytes':0,'models_initialized':0})
 except BaseException as e:
  if reserved and l.db.execute('SELECT state FROM attempts WHERE key=?',(KEY,)).fetchone()[0]=='pending':l.finish(KEY,raw=None)
  write('failure.json',{'status':'FAILED_NO_AUTOMATIC_RETRY','error_type':type(e).__name__,'error':str(e),'received_bytes':written,'archive_reserved':reserved,'conservative_body_charge':CAP if reserved else 0,'partial_file':str(partial),'ledger_reserved':l.totals()})
  raise
 finally:l.close()

def main():
 D.mkdir(exist_ok=False)
 env=dict(os.environ,WIKIBOOKS_PILOT_PARENT_PID=str(os.getpid()))
 started=time.monotonic()
 p=subprocess.Popen([sys.executable,str(pathlib.Path(__file__).resolve()),'--worker'],env=env,start_new_session=True)
 write('supervisor-start.json',{'pid':p.pid,'parent_pid':os.getpid(),'worker_max_seconds':1800,'external_timeout_seconds':1830,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'no_retry':True})
 timed_out=False
 try:code=p.wait(timeout=1830)
 except subprocess.TimeoutExpired:
  timed_out=True;os.killpg(p.pid,signal.SIGTERM)
  try:code=p.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);code=p.wait()
 write('supervisor-result.json',{'status':'COMPLETE' if code==0 else 'FAILED','worker_exit_code':code,'external_timeout':timed_out,'elapsed_seconds':time.monotonic()-started,'partial_bytes_observed':(D/'raw.partial').stat().st_size if (D/'raw.partial').exists() else None,'automatic_retry':False})
 raise SystemExit(code if code>=0 else 1)
if __name__=='__main__':worker() if sys.argv[1:]==['--worker'] else main()
