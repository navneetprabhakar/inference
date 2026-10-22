"""Parent-authorized single bounded second-shard SHA pass; never gzip decode."""
import time
START=time.clock_gettime(time.CLOCK_MONOTONIC)
import hashlib,json,os,signal,stat,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def identity(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def stop(*args):raise TimeoutError('shared30sec_hash_cap')
def verify(binding):
 p=Path(binding['path']);expected=binding['stat']
 if p.is_symlink() or str(p.resolve())!=str(p) or identity(p.stat())!=expected:raise ValueError('source_before_path_stat')
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:
  if identity(os.fstat(fd))!=expected or not stat.S_ISREG(os.fstat(fd).st_mode):raise ValueError('source_FD_stat_regular')
  digest=hashlib.sha256();n=0
  while n<binding['bytes']:
   raw=os.read(fd,min(1048576,binding['bytes']-n))
   if not raw:raise ValueError('short_file')
   n+=len(raw);digest.update(raw)
  if os.read(fd,1):raise ValueError('unexpected_EOF_probe_byte')
  if identity(os.fstat(fd))!=expected or identity(p.stat())!=expected or p.is_symlink():raise ValueError('source_after_FD_path_stat')
  if n!=binding['bytes'] or digest.hexdigest()!=binding['SHA256']:raise ValueError('exact_second_file_publisher_length_SHA256')
  return {'status':'PASS_EXACT_SECOND_SHARD_LOCAL_INTEGRITY_ONLY',**binding,'elapsed_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-START,'method':'O_RDONLY_NOFOLLOW_BEFORE_FD_AFTER_STAT_STREAM_SHA256_1MiB_EOF_PROBE','gzip_decoded':False,'network_requests':0,'new_admitted_documents':0}
 finally:os.close(fd)

def checks():
 import tempfile
 with tempfile.TemporaryDirectory() as z:
  p=Path(z).resolve()/'fixture';p.write_bytes(b'abc');binding={'path':str(p),'stat':identity(p.stat()),'bytes':3,'SHA256':hashlib.sha256(b'abc').hexdigest()};assert verify(binding)['bytes']==3
  try:verify({**binding,'SHA256':'0'*64})
  except ValueError:pass
  else:raise AssertionError('wrong SHA accepted')
 return {'status':'PASS_SYNTHETIC_ONLY','controls':2,'retained_source_bytes':0}
if __name__=='__main__':
 if '--checks' in sys.argv:print(json.dumps(checks()));raise SystemExit()
 signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,max(.001,30-(time.clock_gettime(time.CLOCK_MONOTONIC)-START)))
 p=json.loads((HERE/'profile.json').read_text());sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
 if sha(HERE/'code-pins.json')!=sys.argv[sys.argv.index('--code-pins-sha256')+1]:raise ValueError('external_codepins')
 reg=json.loads((HERE/'code-pins.json').read_text())['SHA256']
 if set(reg)!={str(HERE/'profile.json'),str(HERE/'hash.py'),p['combined_manifest'],p['python']}:raise ValueError('exact_metadata_inventory')
 for f,h in reg.items():
  if sha(f)!=h:raise ValueError('pinned_input_changed')
 if str(Path(sys.executable).resolve())!=p['python']:raise ValueError('runtime')
 if json.loads(Path(p['combined_manifest']).read_text())['new_second']!=p['source']:raise ValueError('exact_combined_manifest_second')
 out=Path(p['output'])
 if out.exists():raise ValueError('once_only_output')
 result=verify(p['source']);out.mkdir();(out/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));signal.setitimer(signal.ITIMER_REAL,0)
