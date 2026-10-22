import signal,time
START=time.monotonic()
def timeout(*a):raise TimeoutError('independent_60sec_cap')
signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,60)
import pathlib,json,hashlib,sqlite3,os,fcntl,stat
HERE=pathlib.Path(__file__).resolve().parent;BASE=HERE.parent;OUT=BASE/'m2-intake/common-pile-uk-hansard-raw-v1';KEY='common-pile-uk-hansard-raw-v1'
def load(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def ident(p):
 s=p.stat(follow_symlinks=False);assert stat.S_ISREG(s.st_mode);return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
w=load(OUT/'worker-result.json');s=load(OUT/'supervisor-result.json');o=load(OUT/'ownership.json');a=load(OUT/'current-attempt.json')
assert w['status']=='TERMINAL_PARTIAL_WORKER_NO_RETRY' and w['completed_files']==2 and w['physical_GETs']==6
assert s['status']=='TERMINAL_PARTIAL_SOURCE_NO_RETRY' and s['worker_reaped'] is True
absent=[]
for k in ['worker_pid','supervisor_pid']:
 try:os.kill(o[k],0)
 except ProcessLookupError:absent.append(o[k])
 else:raise AssertionError('owner live')
manifest=load(BASE/'pressbooks-hansard-acquisition-metadata-preparation-v1/uk_hansard-files.json')
print(type(manifest).__name__,list(manifest)[:4] if isinstance(manifest,dict) else len(manifest))
assert sha(BASE/'pressbooks-hansard-acquisition-metadata-preparation-v1/uk_hansard-files.json')=='c50eb91e0a61625f16c051eb3cf707625844c9b032f28eb5386385a18bc3e13b'
files=manifest['files'] if isinstance(manifest,dict) else manifest
verified=[];starts=[]
for n in range(2):
 r=load(OUT/f'file-{n:03d}.receipt.json');p=OUT/r['file'];before=ident(p)
 assert files[n]['path']==r['file'] and files[n]['expected_sha256']==r['SHA256'] and files[n]['expected_bytes']==r['bytes']
 assert before==r['stat'] and before[2]==r['expected_bytes']==r['bytes'];assert sha(p)==r['expected_SHA256']==r['SHA256'];assert ident(p)==before
 for hop in r['hops']:starts.append(hop['start_monotonic'])
 assert r['hops'][-1]['headers']['Content_Length']==before[2]
 verified.append({'ordinal':n,'relative_file':r['file'],'bytes':before[2],'SHA256':r['SHA256'],'stat':before})
for hop in a['hops']:starts.append(hop['start_monotonic'])
assert len(starts)==6 and all(y-x>=1 for x,y in zip(starts,starts[1:]))
assert a['status']=='PARTIAL_FILE_NO_RETRY' and a['error']=='TimeoutError' and a['expected_bytes']==321622887
assert files[2]['expected_sha256']==a['expected_SHA256'] and files[2]['expected_bytes']==a['expected_bytes']
partial=OUT/'uk_hansard/00002_ukhansard.jsonl.gz.partial';ps=ident(partial);assert ps[2]==a['partial_bytes']==321125147
assert not (OUT/'uk_hansard/00002_ukhansard.jsonl.gz').exists()
ledger=BASE/'m2-intake/charges/ledger.sqlite';db=sqlite3.connect(ledger.as_uri()+'?mode=ro',uri=True);db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
rows=db.execute('SELECT key,charge,state,actual_bytes,body_sha256 FROM attempts WHERE key LIKE ? ORDER BY key',(KEY+'-%',)).fetchall();db.execute('COMMIT');db.close()
by={r[0]:r for r in rows};assert len(rows)==10
for expected in s['owned_allocations']:
 key=expected['key']
 if expected['state']=='UNATTEMPTED_NOT_RESERVED':assert key not in by;continue
 row=by[key];assert json.loads(row[1])==expected['charge'] and row[2]==expected['state'] and row[3]==expected['actual_successful_body_bytes'] and row[4]==expected['successful_body_SHA256'];assert row[2] in ['complete','failed']
assert sum(json.loads(r[1])['body_bytes'] for r in rows)==955378403
assert sum(json.loads(r[1])['output_bytes'] for r in rows)==3500000000
assert sum(json.loads(r[1])['requests'] for r in rows)==6
# Existing lock descriptor only, no IntakeLedger constructor/writer/metadata update.
with (BASE/'m2-intake/charges/job.lock').open('rb') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.flock(lock,fcntl.LOCK_UN)
metadata={p.name:{'bytes':p.stat().st_size,'SHA256':sha(p)} for p in OUT.iterdir() if p.is_file()}
assert sum(v['bytes'] for v in verified)==633755513
report={'status':'PASS_TERMINAL_PARTIAL_PRESERVED_NO_RETRY','producer_status':s['status'],'absent_PIDs':absent,'verified_complete_files':verified,'verified_complete_bytes':633755513,'partial_stat_only':{'bytes':ps[2],'expected_bytes':321622887,'shortfall':321622887-ps[2],'stat':ps,'partial_full_hash_recomputed':False,'decompressed':False},'physical_GETs':6,'minimum_observed_start_gap':min(y-x for x,y in zip(starts,starts[1:])),'ledger':{'read_only_transaction':True,'own_allocations':len(rows),'own_pending':0,'charged_body_bytes':955378403,'charged_output_bytes':3500000000,'charged_requests':6,'exclusive_lock_available_and_released':True,'refunds':0},'metadata':metadata,'no_new_GET':True,'no_decompression':True,'new_admitted_documents':0,'elapsed_seconds':time.monotonic()-START}
(HERE/'verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='metadata'},indent=2));signal.setitimer(signal.ITIMER_REAL,0)
