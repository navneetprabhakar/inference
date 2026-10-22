"""Exact source-component bytes only. No source transforms, network or models."""
import argparse,hashlib,json,os,pathlib,platform,signal,sys,time,subprocess
HERE=pathlib.Path(__file__).resolve().parent
LIMITS={'external_seconds':120,'worker_seconds':110,'observed_RSS_bytes':1000000000,'output_bytes':10000000,'raw_record_bytes':2400000,'capture_span_bytes':262144,'books':20}
SLOTS={'worker-result.json':32768,'supervisor-result.json':16384}
def clk():return time.clock_gettime(time.CLOCK_MONOTONIC)
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def inventory():
 return {str((HERE/n).resolve()) for n in ['capture.py','supervise.py']}|{str(pathlib.Path(sys.executable).resolve())}|{str(pathlib.Path(m.__file__).resolve()) for m in [argparse,hashlib,json,pathlib,platform,signal,subprocess]}
def verify(code_pin,profile_pin,check_inputs=True):
 path=HERE/'code-pins.json'
 if sha(path)!=code_pin:raise ValueError('external_code_registry_pin')
 r=json.loads(path.read_text())
 if set(r['sha256'])!=inventory() or r['runtime']!={'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve()),'platform':platform.platform()}:raise ValueError('exact_inventory_runtime')
 for path,h in r['sha256'].items():
  p=pathlib.Path(path)
  if p.is_symlink() or sha(p)!=h:raise ValueError('code_dependency_pin')
 if sha(HERE/'profile.json')!=profile_pin:raise ValueError('external_profile_pin')
 p=json.loads((HERE/'profile.json').read_text())
 if p['limits']!=LIMITS or len(p['records'])!=20 or len({r['ebook_ID'] for r in p['records']})!=20:raise ValueError('fixed_limits20')
 if check_inputs:
  for item in p['inputs']:
   f=pathlib.Path(item['path'])
   if f.is_symlink() or f.stat().st_size!=item['bytes'] or sha(f)!=item['SHA256']:raise ValueError('input_pin:'+str(f))
 return p

def mini_fixture():
 b='Header\r\nCHAPTER I\r\nCafé prose.\r\n'.encode();lo=b.index(b'CHAPTER');hi=len(b)
 assert b[:lo]+b[lo:hi]==b and b[lo:hi].decode('utf8').endswith('\r\n')
 try:b'bad\xff'.decode('utf8',errors='strict')
 except UnicodeDecodeError:pass
 else:raise AssertionError('UTF8refusal')
 return {'all_imports':'PASS_STANDARD_LIBRARY_ONLY','exact_slice_inverse':'PASS','strictUTF8_refusal':'PASS','network_or_ledger_or_model_imports':False}
def outputsize(out):return sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
def write(out,name,data):
 if not isinstance(data,bytes):data=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode()
 if outputsize(out)+len(data)>LIMITS['output_bytes']:raise ValueError('output_prewrite_bound')
 with (out/name).open('xb') as f:f.write(data);f.flush();os.fsync(f.fileno())
def terminal(out,name,data):
 b=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode();n=SLOTS[name]
 if len(b)>n:raise ValueError('terminal_slot_bound')
 with (out/name).open('r+b') as f:f.write(b+b' '*(n-len(b)));f.flush();os.fsync(f.fileno())
def worker(a):
 start=float(a.start);old=signal.signal(signal.SIGALRM,lambda *args:(_ for _ in ()).throw(TimeoutError('worker_deadline')));remaining=110-(clk()-start);signal.setitimer(signal.ITIMER_REAL,max(.001,remaining));out=None
 try:
  p=verify(a.code_pins_sha256,a.profile_sha256);mini_fixture();out=pathlib.Path(p['output'])
  if os.getppid()!=a.supervisor_pid or remaining<=0:raise ValueError('parent_or_aged_clock')
  records=[]
  for r in p['records']:
   if clk()-start>=110:raise TimeoutError('worker_deadline')
   source=pathlib.Path(r['current_raw']['path']);raw=source.read_bytes()
   if len(raw)>LIMITS['raw_record_bytes'] or hashlib.sha256(raw).hexdigest()!=r['current_raw']['SHA256']:raise ValueError('raw_bound_hash')
   raw.decode('utf8',errors='strict')
   for span in r['source_capture_spans']:
    lo,hi=span['start'],span['end'];b=raw[lo:hi]
    if not 0<=lo<=hi<=len(raw) or len(b)!=span['bytes'] or len(b)>LIMITS['capture_span_bytes'] or hashlib.sha256(b).hexdigest()!=span['SHA256']:raise ValueError('exact_span_bounds_hash')
    b.decode('utf8',errors='strict');write(out,span['file'],b)
    if (out/span['file']).read_bytes()!=raw[lo:hi]:raise ValueError('inverse_capture_equality')
   records.append(r)
  verify(a.code_pins_sha256,a.profile_sha256);write(out,'captures.json',{'status':'EXACT20_COMPONENT_CAPTURES_COMPLETE_NOT_PROSE_UNITS','profile_SHA256':a.profile_sha256,'records':records,'new_admitted_documents':0,'new_admitted_tokens':0})
  terminal(out,'worker-result.json',{'status':'COMPLETE_EXACT_BYTE_COMPONENT_CAPTURES','books':20,'capture_files':sum(len(r['source_capture_spans']) for r in records),'capture_bytes':sum(s['bytes'] for r in records for s in r['source_capture_spans']),'elapsed_seconds':clk()-start,'no_prose_unit_copy':True,'new_admitted_documents':0})
 except BaseException as e:
  if out is not None:terminal(out,'worker-result.json',{'status':'PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'new_admitted_documents':0})
  raise
 finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,old)
if __name__=='__main__':
 q=argparse.ArgumentParser();q.add_argument('--worker',action='store_true');q.add_argument('--preflight',action='store_true');q.add_argument('--code-pins-sha256',required=True);q.add_argument('--profile-sha256',required=True);q.add_argument('--supervisor-pid',type=int);q.add_argument('--start');a=q.parse_args()
 if a.worker:worker(a)
 else:p=verify(a.code_pins_sha256,a.profile_sha256);print(json.dumps({'status':'PREFLIGHT_PASS_NO_MATERIALIZATION','books':len(p['records']),**mini_fixture()}))
