"""Independent local stop watchdog; provider STOP and guest shutdown are separate guards."""
import fcntl,json,time,datetime
from pathlib import Path
from gcp_api import request
R=Path('runs/ownbase-budget50-v1');lock=(R/'guard.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
packet=json.loads((R/'launch-receipt.json').read_text());assert packet['incremental_cap_usd']==50
url='https://compute.googleapis.com/compute/v1/projects/executespecv1/zones/'+packet['zone']+'/instances/'+packet['vm_name']
while time.time()<packet['external_stop_epoch']:time.sleep(min(60,packet['external_stop_epoch']-time.time()))
for attempt in range(10):
 try:
  vm=request(url);state=vm['status']
  if state=='TERMINATED':break
  operation=request(url+'/stop',method='POST',payload={})
  (R/'guard-last-operation.json').write_text(json.dumps(operation,indent=2)+'\n')
 except Exception as ex:(R/'guard-error.json').write_text(json.dumps({'attempt':attempt,'error':str(ex),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
 time.sleep(30)
else:raise RuntimeError('Stop unconfirmed; provider maxRunDuration remains active')
(R/'guard-complete.json').write_text(json.dumps({'status':'TERMINATED','utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}))
