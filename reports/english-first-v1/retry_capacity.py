"""At most two same-price L4 zone retries, only after proven capacity-only failure."""
import json,hashlib,subprocess,sys
from pathlib import Path
P=Path(__file__).parent
for old,new in ([('c','f')] if sys.argv[1:]==['c'] else [('b','c'),('c','f')]):
 operation=json.loads((P/('operation-'+old+'.json')).read_text())
 if operation.get('status')!='DONE' or operation.get('error',{}).get('errors',[{}])[0].get('code')!='ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS':raise SystemExit('Not a retryable confirmed capacity failure')
 request=json.loads((P/'launch-request.json').read_text());name=request['run_id']
 instances=json.loads(subprocess.check_output(['gcloud','compute','instances','list','--project=executespecv1','--format=json(name,status)'],text=True,timeout=60))
 disks=json.loads(subprocess.check_output(['gcloud','compute','disks','list','--project=executespecv1','--filter=name='+name,'--format=json'],text=True,timeout=60))
 assert not any(i['name']==name for i in instances) and not disks
 (P/('capacity-reconcile-'+old+'.json')).write_text(json.dumps({'instances':instances,'matching_disks':disks,'capacity_failure_confirmed':True},indent=2)+'\n')
 (P/'launch-request.json').rename(P/('launch-request-'+old+'.json'));(P/'launch-response.json').rename(P/('launch-response-'+old+'.json'))
 request['create_argv']=['--zone=us-central1-'+new if a.startswith('--zone=') else a for a in request['create_argv']]
 request['retry_reason']='Confirmed capacity failure, absent VM/disks; same machine/region/cap, next supported zone.'
 (P/'launch-request.json').write_text(json.dumps(request,indent=2)+'\n')
 ledger=json.loads((P/'spend-ledger.json').read_text());a=ledger['allocations'][0]
 a.update(state='reserved_before_provisioning',request_sha256=hashlib.sha256((P/'launch-request.json').read_bytes()).hexdigest())
 a.setdefault('failed_capacity_attempts',[]).append('us-central1-'+old)
 (P/'spend-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 subprocess.run([sys.executable,str(P/'execute_lease.py')],check=True,timeout=150,capture_output=True,text=True)
 response=json.loads((P/'launch-response.json').read_text());op=json.loads(response['stdout'])[0]['name']
 subprocess.run(['gcloud','compute','operations','wait',op,'--project=executespecv1','--zone=us-central1-'+new,'--timeout=60'],capture_output=True,text=True,timeout=75)
 result=json.loads(subprocess.check_output(['gcloud','compute','operations','describe',op,'--project=executespecv1','--zone=us-central1-'+new,'--format=json'],text=True,timeout=60))
 (P/('operation-'+new+'.json')).write_text(json.dumps(result,indent=2)+'\n')
 print(new,result['status'],result.get('error',{}).get('errors',[{}])[0].get('code'),flush=True)
 if not result.get('error'):break
