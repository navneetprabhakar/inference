import pathlib,subprocess,sys,time,json,hashlib
D=pathlib.Path(__file__).resolve().parent;start=time.monotonic();code=None;reason=None
with (D/'worker.log').open('xb') as log:
 p=subprocess.Popen([sys.executable,str(D/'metadata.py')],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 try:code=p.wait(timeout=110)
 except subprocess.TimeoutExpired:
  import signal,os
  reason='120second_externalcap_cleanup_reserve';os.killpg(p.pid,signal.SIGTERM)
  try:code=p.wait(timeout=3)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);code=p.wait(timeout=3)
r={'status':'PASS' if code==0 and reason is None else 'FAILED','exit_code':code,'reason':reason,'elapsed_seconds':time.monotonic()-start,'external_seconds':120,'worker_SHA256':hashlib.sha256((D/'metadata.py').read_bytes()).hexdigest(),'automatic_retry':False};(D/'supervisor.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));raise SystemExit(0 if r['status']=='PASS' else 1)
