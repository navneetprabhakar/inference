import hashlib,json,os,pathlib,signal,subprocess,sys,time
P=pathlib.Path(__file__).resolve().parent;started=time.monotonic();p=None;peak=0;reason=None
try:
 with (P/'verification-worker.log').open('xb') as log:
  p=subprocess.Popen([sys.executable,str(P/'verify.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  while p.poll() is None:
   ps=subprocess.run(['/bin/ps','-axo','pid=,ppid=,rss='],capture_output=True,text=True,check=True,timeout=1);rows=[tuple(map(int,line.split())) for line in ps.stdout.splitlines()];owned={os.getpid()}
   while True:
    grown=owned|{pid for pid,ppid,rss in rows if ppid in owned}
    if grown==owned:break
    owned=grown
   rss=sum(rss*1024 for pid,ppid,rss in rows if pid in owned);peak=max(peak,rss)
   if time.monotonic()-started>=295:reason='300secondcap_cleanup_reserve'
   if rss>1000000000:reason='observed_owned_tree1GB_RSS_cap'
   if reason:
    os.killpg(p.pid,signal.SIGTERM)
    try:p.wait(timeout=2)
    except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=3)
    break
   time.sleep(.2)
  code=p.wait(timeout=3)
except BaseException:
 if p and p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait(timeout=3)
 raise
result={'status':'PASS' if code==0 and reason is None else 'FAILED','worker_exit_code':code,'reason':reason,'elapsed_seconds':time.monotonic()-started,'peak_observed_owned_tree_RSS_bytes':peak,'RSS_scope':'0.2second observations; transient unobserved peaks not proven absent','limits':{'seconds':300,'observed_owned_tree_RSS_bytes':1000000000},'verifier_SHA256':hashlib.sha256((P/'verify.py').read_bytes()).hexdigest(),'worker_log_SHA256':hashlib.sha256((P/'verification-worker.log').read_bytes()).hexdigest(),'no_detector_rerun':True,'no_network':True,'no_admission':True};(P/'supervisor.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0 if result['status']=='PASS' else 1)
