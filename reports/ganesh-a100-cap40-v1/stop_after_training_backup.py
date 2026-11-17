"""Shorten only this final lease after fresh post-training backups and joined jobs."""
import datetime as dt,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
proof=json.loads((P/'assessment/closeout/fit-closeout/backup.json').read_text())
assert json.loads((P/'assessment/closeout/packing-diagnosis/backup.json').read_text())['full_readback_verified']
local=json.loads((P/'local-fit-weights.json').read_text());smoke=json.loads((P/'local-fit-smoke.json').read_text());review=json.loads((P/'review-backup.json').read_text())
assert proof['evidence_full_readback'] and proof['gpu_children_joined'] and proof['controller_failure_preserved']
assert {x['step'] for x in proof['checkpoint_readbacks']}=={0,16,20,30} and all(x['full_readback_verified'] for x in proof['checkpoint_readbacks'])
assert {x['step'] for x in local['checkpoints']}=={20,30} and all(x['full_payload_readback_verified'] for x in local['checkpoints'])
assert smoke['device']=='mps' and len(smoke['records'])==3 and not smoke['default_changed'] and review['full_readback_verified']
assert not (P/'final-provider-stop-request.json').exists()
base=['gcloud','compute'];common=['--project=executespecv1','--zone=us-central1-c'];name='ganesh-a100-1117-203113'
def call(a):return subprocess.check_output(a,text=True,timeout=120)
i=json.loads(call(base+['instances','describe',name,*common,'--format=json']))
assert i['id']=='3789763232438224727' and i['status']=='RUNNING' and i['scheduling']['instanceTerminationAction']=='STOP' and not i['disks'][0]['autoDelete']
cmd="sudo flock -n /tmp/ganesh-gpu-writer.lock /bin/bash -c 'test -f /opt/english-eager/fit-closeout/backup.json && test ! -f /opt/english-eager/fit-closeout/backup-failure.txt && for u in ganesh-english-fit-train ganesh-stopped-fit-assessment ganesh-termination-diagnosis-env ganesh-fit-closeout ganesh-packing-diagnosis; do case \"$(systemctl show \"$u\" -p ActiveState --value)\" in inactive|failed) ;; *) exit 2 ;; esac; done; test -z \"$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)\" || exit 3; cat /run/systemd/shutdown/scheduled'"
remote=call(base+['ssh',name,*common,'--tunnel-through-iap','--quiet','--command='+cmd]);guest={k:v for line in remote.splitlines() if '=' in line for k,v in [line.split('=',1)]}
now=dt.datetime.now(dt.timezone.utc);deadline=now+dt.timedelta(minutes=2)
assert deadline.timestamp()+60<int(guest['USEC'])/1e6
assert deadline<dt.datetime.fromisoformat('2026-11-18T03:05:59+00:00')
stamp=deadline.strftime('%Y-%m-%dT%H:%M:%SZ');request={'instance':name,'instance_id':i['id'],'provider_deadline_utc':stamp,'previous_deadline_utc':i['scheduling']['terminationTime'],'requested_utc':now.isoformat(),'guest_shutdown_epoch':int(guest['USEC'])/1e6,'fresh_post_training_backups_verified':True,'local_best_last_verified':True,'writers_joined':True,'disk_auto_delete':False,'guest_stop_not_invoked':True}
(P/'final-provider-stop-request.json').write_text(json.dumps(request,indent=2)+'\n')
call(base+['instances','set-scheduling',name,*common,'--termination-time='+stamp,'--instance-termination-action=STOP','--no-restart-on-failure','--quiet'])
i=json.loads(call(base+['instances','describe',name,*common,'--format=json']));assert i['scheduling']['terminationTime']==stamp and not i['disks'][0]['autoDelete']
(P/'final-provider-stop-bound.json').write_text(json.dumps(i,indent=2)+'\n');print(stamp)
