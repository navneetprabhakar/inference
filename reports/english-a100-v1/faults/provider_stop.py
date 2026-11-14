"""Shorten the final lease after verified backups; observe provider STOP separately."""
import datetime as dt,json,subprocess
from pathlib import Path
p=Path(__file__).parent;parent=p.parent
if (p/'provider-stop-request.json').exists():raise ValueError('Provider drill already requested')
proof=json.loads((p/'worker-backup-check.json').read_text());result=json.loads((p/'worker-qualification.json').read_text())
if not proof['local_archive_readback_verified'] or not proof['all_required_checkpoint_readbacks'] or result['status']!='signal_upload_pass_pending_provider_stop':raise ValueError('Fault/backups prerequisite incomplete')
r=json.loads((p/'lease-request.json').read_text());name=r['instance'];zone=r['zone']
def call(args):return subprocess.check_output(['gcloud',*args],text=True,timeout=120)
i=json.loads(call(['compute','instances','describe',name,'--zone='+zone,'--project=executespecv1','--format=json']))
if i['status']!='RUNNING' or i['scheduling']['instanceTerminationAction']!='STOP' or i['disks'][0]['autoDelete']:raise ValueError('VM not in safe drill state')
# No training writer and no worker-owned shutdown near the new provider deadline.
cmd="sudo flock -n /opt/english/worker.lock /bin/bash -c 'test -f /opt/english-faults/backup-ready && test ! -f /opt/english-faults/backup-failure.txt && cat /run/systemd/shutdown/scheduled'"
remote=call(['compute','ssh',name,'--zone='+zone,'--project=executespecv1','--tunnel-through-iap','--quiet','--command='+cmd])
guest={k:v for line in remote.splitlines() if '=' in line for k,v in [line.split('=',1)]}
if 'USEC' not in guest:raise ValueError('Cannot establish guest shutdown deadline')
now=dt.datetime.now(dt.timezone.utc);deadline=now+dt.timedelta(minutes=2)
if deadline.timestamp()+60>=int(guest['USEC'])/1e6 or deadline>=dt.datetime.fromisoformat(r['deadline_utc'].replace('Z','+00:00')):raise ValueError('Insufficient separation for independent provider STOP')
stamp=deadline.strftime('%Y-%m-%dT%H:%M:%SZ')
request={'instance':name,'zone':zone,'instance_id':i['id'],'requested_utc':now.isoformat(),'provider_deadline_utc':stamp,'previous_deadline_utc':r['deadline_utc'],'guest_shutdown_epoch':int(guest['USEC'])/1e6,'writers_joined':True,'backups_verified':True,'boot_disk_auto_delete':False,'guest_stop_not_invoked':True,'only_shortens_current_final_lease':True}
(p/'provider-stop-request.json').write_text(json.dumps(request,indent=2)+'\n')
call(['compute','instances','set-scheduling',name,'--zone='+zone,'--project=executespecv1','--termination-time='+stamp,'--instance-termination-action=STOP','--no-restart-on-failure','--quiet'])
check=json.loads(call(['compute','instances','describe',name,'--zone='+zone,'--project=executespecv1','--format=json']))
if check['scheduling']['terminationTime']!=stamp or check['disks'][0]['autoDelete']:raise ValueError('Provider STOP not bound as requested')
(p/'provider-stop-bound.json').write_text(json.dumps(check,indent=2)+'\n');print(stamp)
