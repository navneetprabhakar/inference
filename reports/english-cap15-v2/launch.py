"""Single fresh approved qualification allocation; no retry or fit launch."""
import datetime as dt,fcntl,hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
with (P/'launch.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if (P/'launch-response.json').exists():raise ValueError('Attempt already recorded: reconcile, never retry automatically')
 r=json.loads((P/'launch-request.json').read_text());l=json.loads((P/'spend-ledger.json').read_text())
 assert len(l['allocations'])==1 and l['approved_total_usd']==15 and l['reserve_usd']==4 and not l['fit_started']
 a=l['allocations'][0];assert a['state']=='reserved_before_provisioning' and a['request_sha256']==sha(P/'launch-request.json')
 assert a['compute_reserved_usd']==r['compute_reserved_usd']<=l['qualification_slice_usd']==5
 assert a['compute_reserved_usd']+l['fit_slice_usd']+l['reserve_usd']<=15
 assert r['qualification_only'] and r['max_runtime_seconds']==3600
 for n,h in json.loads((P/'local-preflight.json').read_text())['bound_files'].items():assert sha(ROOT/n)==h
 assert sha(P/'bootstrap.sh')==r['bootstrap_sha256']
 proof=json.loads((P/'input-backup-receipt.json').read_text());assert proof['all_verified'] and proof['files']==r['inputs']
 for x in proof['files']:assert x['independent_readback'] and sha(Path(x['path']))==x['sha256']
 remaining=(dt.datetime.fromisoformat(r['provider_stop_utc'].replace('Z','+00:00'))-dt.datetime.now(dt.timezone.utc)).total_seconds()
 assert 2700<remaining<=3600
 argv=r['create_argv'];assert argv[:4]==['gcloud','compute','instances','create'] and argv[4]==r['run_id']
 for v in ['--termination-time='+r['provider_stop_utc'],'--instance-termination-action=STOP','--no-boot-disk-auto-delete','--no-restart-on-failure','--no-address','--machine-type=a2-highgpu-1g','--zone=us-central1-f','--project=executespecv1','--provisioning-model=STANDARD']:assert v in argv
 inventory=json.loads(subprocess.check_output(['gcloud','compute','instances','list','--project=executespecv1','--format=json(name,status)'],text=True,timeout=60))
 assert all(i['status']=='TERMINATED' for i in inventory)
 (P/'second-pass-launch-check.json').write_text(json.dumps({'checks_passed':True,'remaining_seconds':remaining,'inventory':inventory,'request_sha256':sha(P/'launch-request.json'),'utc':dt.datetime.now(dt.timezone.utc).isoformat()},indent=2)+'\n')
 a['state']='create_requested';(P/'spend-ledger.json').write_text(json.dumps(l,indent=2)+'\n')
 # Record intent BEFORE provider call; ambiguity can never result in blind retry.
 (P/'launch-response.json').write_text(json.dumps({'state':'request_in_flight_reconcile_before_any_action'})+'\n')
 try:
  p=subprocess.run(argv,capture_output=True,text=True,timeout=120)
  response={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
 except BaseException as e:response={'state':'uncertain_reconcile_provider','error':repr(e)}
 (P/'launch-response.json').write_text(json.dumps(response,indent=2)+'\n');print(json.dumps(response))
