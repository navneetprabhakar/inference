"""Pure L4 qualification lease planner. Never provisions or authorizes training.

The caller must reserve cumulative costs BEFORE running argv, bind a verified
bootstrap and preserve disk on backup failure. Old A100/DELETE launchers excluded.
"""
import datetime as dt
import math,re

def plan(*,project,zone,name,image,service_account,bootstrap,now,hours,prior_reserved_usd=0):
    for value in (hours,prior_reserved_usd):
        if type(value) not in (int,float) or not math.isfinite(value):raise ValueError('Finite lease amounts required')
    if not .5<=hours<=6 or prior_reserved_usd<0:raise ValueError('Invalid lease duration or previous reservations')
    if now.tzinfo is None:raise ValueError('Timezone-aware current time required')
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,61}[a-z0-9]',project):raise ValueError('Explicit project required')
    if zone not in ('us-central1-a','us-central1-b','us-central1-c','us-east1-b','us-east1-c','us-east1-d','us-east4-a','us-east4-c','us-west1-a','us-west1-b','us-west1-c'):raise ValueError('Only priced region allowed')
    if not re.fullmatch(r'forge-english-[a-z0-9-]{1,35}',name):raise ValueError('Dedicated English diagnostic name required')
    if not image.startswith('projects/deeplearning-platform-release/global/images/'):raise ValueError('Pinned DLVM image required')
    if not service_account.endswith('.iam.gserviceaccount.com'):raise ValueError('Explicit service account required')
    # $10 operational envelope remains within the previously discussed $15 ceiling.
    rate=.853624312;reserve=3.5;envelope=hours*rate*1.25
    if prior_reserved_usd+envelope+reserve>10:raise ValueError('Cumulative L4 envelope exhausted')
    deadline=now+dt.timedelta(hours=hours)
    stamp=deadline.astimezone(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    argv=['gcloud','compute','instances','create',name,'--project='+project,'--zone='+zone,
          '--machine-type=g2-standard-8','--provisioning-model=STANDARD','--maintenance-policy=TERMINATE',
          '--no-restart-on-failure','--termination-time='+stamp,
          '--metadata=own-deadline-utc='+stamp,
          '--instance-termination-action=STOP','--boot-disk-size=100GB','--boot-disk-type=pd-balanced',
          '--no-boot-disk-auto-delete','--image='+image,'--service-account='+service_account,
          '--scopes=https://www.googleapis.com/auth/devstorage.read_write',
          '--no-address','--subnet=default','--metadata-from-file=startup-script='+bootstrap]
    return {'status':'plan_only_not_launch_ready','create_argv':argv,'machine':'g2-standard-8','gpu':'1x L4',
            'list_rate_usd_per_hour':rate,'compute_envelope_usd':envelope,'reserve_usd':reserve,
            'operational_cap_usd':10,'cumulative_reserved_before_usd':prior_reserved_usd,
            'latest_local_stop_utc':stamp,'max_runtime_seconds':int(hours*3600),
            'worker_reserve_seconds':900,'provider_termination':'STOP','boot_disk_auto_delete':False,
            'requirements':['Reserve complete lease in durable cumulative ledger before provisioning.',
                            'Bootstrap must enforce earlier local deadline from metadata, including reboots.',
                            'Reconcile provider runtime before refunding any reservation.',
                            'Verified GCS readback before normal stop; retain disk on any backup failure.',
                            'No automatic machine/zone-price/budget upgrade. No training until qualification passes.']}
