"""Execute only the reviewed, prepaid-reservation qualification request once."""
import json,hashlib,subprocess,datetime as dt,fcntl
from pathlib import Path
P=Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with (P/'launch.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 request=json.loads((P/'launch-request.json').read_text());ledger=json.loads((P/'spend-ledger.json').read_text())
 if (P/'launch-response.json').exists():raise ValueError('Single attempt already recorded; reconcile before any retry')
 assert ledger['operational_cap_usd']==10 and ledger['reserve_usd']==3.5
 assert len(ledger['allocations'])==1
 allocation=ledger['allocations'][0]
 assert allocation['name']==request['run_id'] and allocation['state']=='reserved_before_provisioning'
 assert allocation['request_sha256']==sha(P/'launch-request.json')
 assert allocation['reserved_compute_usd']+ledger['reserve_usd']<=ledger['operational_cap_usd']
 assert sha(P/'bootstrap.sh')==request['bootstrap_sha256']
 proof=json.loads((P/'input-backup-receipt.json').read_text());assert proof['all_verified']
 assert [{k:x[k] for k in ('path','uri','sha256')} for x in proof['files']]==request['inputs']
 for item in proof['files']:assert item['independent_readback'] and sha(Path(item['path']))==item['sha256']
 instances=json.loads(subprocess.check_output(['gcloud','compute','instances','list','--project=executespecv1','--format=json(name,status)'],text=True,timeout=60))
 assert all(i['status']=='TERMINATED' for i in instances)
 deadline=dt.datetime.fromisoformat(request['latest_local_stop_utc'].replace('Z','+00:00'))
 assert (deadline-dt.datetime.now(dt.timezone.utc)).total_seconds()>3600
 argv=request['create_argv']
 assert '--instance-termination-action=STOP' in argv and '--no-boot-disk-auto-delete' in argv
 assert '--machine-type=g2-standard-8' in argv and '--provisioning-model=STANDARD' in argv
 assert '--termination-time='+request['latest_local_stop_utc'] in argv
 allocation['state']='create_requested';(P/'spend-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 try:
  completed=subprocess.run(argv,capture_output=True,text=True,timeout=120)
  response={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'returncode':completed.returncode,'stdout':completed.stdout,'stderr':completed.stderr}
 except BaseException as e:
  response={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'returncode':None,'error':repr(e),'state':'reconcile_cloud_before_retry'}
 (P/'launch-response.json').write_text(json.dumps(response,indent=2)+'\n')
 print(json.dumps(response));raise SystemExit(0 if response['returncode']==0 else 2)
