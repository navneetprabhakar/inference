"""Once-only local bounded calibration launcher; no source network/model operations."""
import time,signal
START=time.clock_gettime(time.CLOCK_MONOTONIC)
def alarm(*_):raise TimeoutError('30second_external')
signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,30)
import os,json,subprocess,sys,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
child=None;peak=0
try:
 profile=HERE/'profile.json';expected='28d0f1540645d8d4cb0dcf026a2e608c307cbfda828183b462a97933460f1073'
 assert hashlib.sha256(profile.read_bytes()).hexdigest()==expected
 assert not (HERE/'results.json').exists() and not (HERE/'supervisor.json').exists()
 child=subprocess.Popen([sys.executable,'-B',str(HERE/'run.py'),str(profile),expected],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
 while child.poll() is None:
  q=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1)
  rows={}
  for line in q.stdout.splitlines():
   z=line.split();assert len(z)==3 and all(v.isdecimal() for v in z)
   a,b,c=map(int,z);assert a>0 and a!=b and a not in rows;rows[a]=(b,c)
  assert os.getpid() in rows and rows[os.getpid()][1]>0
  own={os.getpid()}
  while True:
   more=own|{a for a,(b,c) in rows.items() if b in own}
   if more==own:break
   own=more
  if child.poll() is None:assert child.pid in own and rows[child.pid][1]>0
  rss=sum(rows[a][1]*1024 for a in own);peak=max(peak,rss);assert rss<=256000000
  assert sum(x.stat().st_size for x in HERE.iterdir() if x.is_file())<7900000
  assert time.clock_gettime(time.CLOCK_MONOTONIC)-START<29
  time.sleep(.01)
 stdout,stderr=child.communicate(timeout=1)
 assert child.returncode==0,(child.returncode,stderr.decode()[:1000])
 receipt={'status':'COMPLETE_DEVELOPMENT_CALIBRATION_SUPERVISED','worker_PID':child.pid,'worker_reaped':True,'elapsed_seconds':time.clock_gettime(time.CLOCK_MONOTONIC)-START,'peak_observed_tree_RSS':peak,'worker_receipt':json.loads(stdout),'profile_SHA256':expected,'new_admissions':0}
except BaseException:
 if child is not None:
  if child.poll() is None:
   try:os.killpg(child.pid,signal.SIGKILL)
   except ProcessLookupError:pass
  child.wait(timeout=1)
 raise
finally:signal.setitimer(signal.ITIMER_REAL,0)
b=(json.dumps(receipt,indent=2)+'\n').encode();assert sum(x.stat().st_size for x in HERE.iterdir() if x.is_file())+len(b)<=8000000
(HERE/'supervisor.json').write_bytes(b)
print(json.dumps(receipt,indent=2))
