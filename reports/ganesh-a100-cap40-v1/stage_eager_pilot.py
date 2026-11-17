"""Stage inert pilot controls and collect live fixed-stop evidence; never train."""
import datetime,json,subprocess,shlex,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;D=P/'pilot-inputs-eager'
r=subprocess.run(['gcloud','compute','instances','list','--project=executespecv1','--format=json'],capture_output=True,text=True,check=True,timeout=60)
j=json.loads(r.stdout);assert len(j)==1;v=j[0];assert v['name']=='ganesh-a100-1117-203113' and v['status']=='RUNNING'
assert v['scheduling']['terminationTime']=='2026-11-18T03:05:59Z' and v['scheduling']['instanceTerminationAction']=='STOP' and not v['scheduling']['automaticRestart'];assert all(not d['autoDelete'] for d in v['disks'])
now=datetime.datetime.now(datetime.timezone.utc).isoformat();(D/'inventory.json').write_text(json.dumps({'checked_utc':now,'instances':j},indent=2)+'\n')
ssh=['gcloud','compute','ssh',v['name'],'--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet']
timer=subprocess.run(ssh+['--command=sudo shutdown --show'],capture_output=True,text=True,check=True,timeout=90);timer_text=timer.stdout+timer.stderr;assert '03:04:31' in timer_text and '2026-11-18' in timer_text
(D/'provider-stop-schedule.json').write_text(json.dumps({'checked_utc':now,'actual_stop_deferred_until_closeout':True,'same_instance_retained':True,'fixed_stop_verified':True,'disk_preserved_on_stop':True,'instance_id':v['id'],'final_provider_stop_utc':v['scheduling']['terminationTime'],'actual_inventory_sha256':hashlib.sha256((D/'inventory.json').read_bytes()).hexdigest(),'guest_timer':timer_text.strip(),'scope':'Configured stop only; observed provider STOP still required at final closeout'},indent=2)+'\n')
subprocess.run(['gcloud','compute','scp','--recurse',str(D),v['name']+':~/','--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet'],check=True,timeout=120)
subprocess.run(ssh+['--command=sudo test ! -e /opt/english-eager/pilot-evidence && sudo cp -r ~/pilot-inputs-eager /opt/english-eager/pilot-evidence'],check=True,timeout=90)
print('Inert pilot controls staged; no training dispatched')
