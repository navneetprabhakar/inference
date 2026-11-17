"""Single allocation with durable intent; every non-success requires reconciliation."""
import json,subprocess,fcntl,datetime as dt,hashlib
from pathlib import Path
from cloud_training.nano_recovery_gate import inspect
P=Path(__file__).resolve().parent;ROOT=Path.cwd()
def write(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
def cloud(a):return json.loads(subprocess.check_output(['gcloud',*a,'--project=executespecv1','--format=json'],text=True,timeout=90))
with (P/'allocation.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 if (P/'allocation-intent.json').exists():raise RuntimeError('Allocation already attempted; reconcile, never repeat')
 request=json.loads((P/'launch-request.json').read_text());gate=inspect(ROOT,request,'qualification');assert gate['allowed'],gate
 assert not cloud(['compute','instances','list']) and not cloud(['compute','disks','list'])
 argv=request['launch_argv'];assert argv.count('--machine-type=g2-standard-8')==1
 for flag in ('--instance-termination-action=STOP','--no-boot-disk-auto-delete','--no-restart-on-failure','--no-address','--boot-disk-size=200GB'):assert flag in argv
 assert json.loads((P/'adverse-checks.json').read_text())['checks'] and 'Ran 202 tests' in (P/'local-tests.log').read_text() and '\nOK\n' in (P/'local-tests.log').read_text()
 config=json.loads((P/'config.json').read_text())
 write('allocation-intent.json',{'name':config['run_id'],'zone':'us-east1-d','requested_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'spec_sha256':gate['spec_sha256'],'status':'in_flight','approved_cap_usd':20,'reserved_campaign_usd':request['maximum_incremental_cost_usd']})
 response=subprocess.run(argv,capture_output=True,text=True,timeout=120)
 write('create-response.json',{'returncode':response.returncode,'stdout':response.stdout,'stderr':response.stderr})
 if response.returncode:raise RuntimeError('Create returned error; reconciliation required, no retry')
 operations=json.loads(response.stdout);write('operations.json',operations)
 print(json.dumps({'status':'request_submitted','name':config['run_id'],'operations':[o['name'] for o in operations]}))
