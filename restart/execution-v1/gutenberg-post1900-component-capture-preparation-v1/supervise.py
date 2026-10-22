import argparse,json,os,pathlib,signal,subprocess,sys,time
import capture as c
def rss():
 p=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rows=[tuple(map(int,l.split())) for l in p.stdout.splitlines() if len(l.split())==3];owned={os.getpid()}
 while True:
  more=owned|{pid for pid,ppid,r in rows if ppid in owned}
  if more==owned:return sum(r*1024 for pid,ppid,r in rows if pid in owned)
  owned=more
def kill(p):
 if p.poll() is None:
  try:os.killpg(p.pid,signal.SIGKILL)
  except ProcessLookupError:pass
 p.wait(timeout=5)
def run(a):
 start=c.clk();child=None;out=None;created=False;peak=0;handlers={}
 def stop(*args):raise TimeoutError('external120second_watchdog')
 try:
  for s in [signal.SIGALRM,signal.SIGINT,signal.SIGTERM]:handlers[s]=signal.signal(s,stop)
  signal.setitimer(signal.ITIMER_REAL,max(.001,120-(c.clk()-start)))
  p=c.verify(a.code_pins_sha256,a.profile_sha256);c.mini_fixture();out=pathlib.Path(p['output'])
  if out.exists():raise ValueError('once_only_output_exists')
  out.mkdir();created=True
  for name,n in c.SLOTS.items():c.write(out,name,b' '*n)
  child=subprocess.Popen([sys.executable,'-B',str(c.HERE/'capture.py'),'--worker','--code-pins-sha256',a.code_pins_sha256,'--profile-sha256',a.profile_sha256,'--supervisor-pid',str(os.getpid()),'--start',str(start)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  c.write(out,'ownership.json',{'supervisor_pid':os.getpid(),'worker_pid':child.pid,'shared_start':start,'profile_SHA256':a.profile_sha256,'code_pins_SHA256':a.code_pins_sha256})
  while child.poll() is None:
   peak=max(peak,rss())
   if peak>c.LIMITS['observed_RSS_bytes'] or c.outputsize(out)>c.LIMITS['output_bytes'] or c.clk()-start>=110:raise ValueError('observed_resource_bound')
   time.sleep(.05)
  child.wait(timeout=5);w=json.loads((out/'worker-result.json').read_text());ok=child.returncode==0 and w.get('status')=='COMPLETE_EXACT_BYTE_COMPONENT_CAPTURES'
  c.terminal(out,'supervisor-result.json',{'status':'COMPLETE' if ok else 'PARTIAL_NO_RETRY','worker_exit_code':child.returncode,'elapsed_seconds':c.clk()-start,'peak_observed_process_tree_RSS_bytes':peak,'output_bytes':c.outputsize(out),'worker_receipt_SHA256':c.sha(out/'worker-result.json'),'new_admitted_documents':0});return 0 if ok else 1
 except BaseException as e:
  if child is not None:kill(child)
  if created:c.terminal(out,'supervisor-result.json',{'status':'PARTIAL_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'elapsed_seconds':c.clk()-start,'new_admitted_documents':0})
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0)
  for s,h in handlers.items():signal.signal(s,h)
if __name__=='__main__':
 q=argparse.ArgumentParser();q.add_argument('--execute',action='store_true');q.add_argument('--code-pins-sha256',required=True);q.add_argument('--profile-sha256',required=True);a=q.parse_args()
 if not a.execute:raise SystemExit('explicit--execute required')
 raise SystemExit(run(a))
