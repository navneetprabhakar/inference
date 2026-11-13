"""Independent two-hour-maximum extension watchdog; never changes provider limit."""
import sys,json,time,datetime,fcntl
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from gcp_api import request
R=Path('runs/ownbase-budget50-v1/extension-v5');lock=(R/'guard.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
url='https://compute.googleapis.com/compute/v1/projects/executespecv1/zones/us-central1-b/instances/forge-ownbase-extension-v5'
wait_until=time.time()+7200;started=False
while time.time()<wait_until or started:
 try:
  vm=request(url,timeout=30)
  if vm['status']=='RUNNING':
   started=True
   limit=int(vm['scheduling']['maxRunDuration']['seconds']);assert limit<=7200
   end=datetime.datetime.fromisoformat(vm['lastStartTimestamp']).timestamp()+limit-60
   if time.time()>=end:request(url+'/stop',method='POST',payload={})
  if vm['status']=='TERMINATED':
   (R/'guard-complete.json').write_text(json.dumps({'status':'TERMINATED','utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}));break
 except Exception as e:
  (R/'guard-last-error.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'error':str(e)[:1500]}))
 time.sleep(30)
