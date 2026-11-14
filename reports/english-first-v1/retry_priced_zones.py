"""Finite same-GPU/same-envelope retries across independently priced US regions."""
import datetime as dt,hashlib,json,subprocess,sys,time
from pathlib import Path
P=Path(__file__).parent
prices=json.loads((P/'regional-price-review.json').read_text());supported=set((P/'l4-supported-zones.txt').read_text().splitlines())
last_zone='us-west1-b' if sys.argv[1:]==['westb'] else 'us-west1-a' if sys.argv[1:]==['west'] else 'us-east4-c'
last=json.loads((P/('operation-us-west1-b.json' if sys.argv[1:]==['westb'] else 'operation-us-west1-a.json' if sys.argv[1:]==['west'] else 'operation-east4-c.json')).read_text())
zones=['us-west1-c'] if sys.argv[1:]==['westb'] else ['us-west1-b','us-west1-c'] if sys.argv[1:]==['west'] else ['us-east4-a','us-east1-b','us-east1-c','us-east1-d','us-west1-a','us-west1-b','us-west1-c']
for zone in zones:
 assert last['status']=='DONE' and last.get('error',{}).get('errors',[{}])[0].get('code')=='ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS'
 assert zone in supported and prices['regions'][zone.rsplit('-',1)[0]]['hourly_usd']<=prices['reservation_rate_upper_bound']
 request=json.loads((P/'launch-request.json').read_text());name=request['run_id']
 instances=json.loads(subprocess.check_output(['gcloud','compute','instances','list','--project=executespecv1','--format=json(name,status)'],text=True,timeout=60))
 disks=json.loads(subprocess.check_output(['gcloud','compute','disks','list','--project=executespecv1','--filter=name='+name,'--format=json'],text=True,timeout=60))
 assert not any(i['name']==name for i in instances) and not disks
 subnet=json.loads(subprocess.check_output(['gcloud','compute','networks','subnets','describe','default','--project=executespecv1','--region='+zone.rsplit('-',1)[0],'--format=json'],text=True,timeout=60))
 if not subnet.get('privateIpGoogleAccess'):
  print(zone,'skip: private Google Access unavailable; no network mutation',flush=True);continue
 (P/('capacity-reconcile-'+last_zone+'.json')).write_text(json.dumps({'instances':instances,'matching_disks':disks,'capacity_failure_confirmed':True},indent=2)+'\n')
 (P/'launch-request.json').rename(P/('launch-request-'+last_zone+'.json'));(P/'launch-response.json').rename(P/('launch-response-'+last_zone+'.json'))
 request['create_argv']=['--zone='+zone if a.startswith('--zone=') else a for a in request['create_argv']]
 request['retry_reason']='Capacity-only failure reconciled; verified same-or-lower-priced L4 region, same absolute expiry and reservation.'
 (P/'launch-request.json').write_text(json.dumps(request,indent=2)+'\n')
 ledger=json.loads((P/'spend-ledger.json').read_text());a=ledger['allocations'][0]
 a.update(state='reserved_before_provisioning',request_sha256=hashlib.sha256((P/'launch-request.json').read_bytes()).hexdigest())
 if last_zone not in a['failed_capacity_attempts']:a['failed_capacity_attempts'].append(last_zone)
 (P/'spend-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n')
 completed=subprocess.run([sys.executable,str(P/'execute_lease.py')],capture_output=True,text=True,timeout=240)
 if completed.returncode:
  print(zone,'request/preflight failed',completed.stdout,completed.stderr,flush=True);break
 response=json.loads((P/'launch-response.json').read_text());op=json.loads(response['stdout'])[0]['name'];until=time.monotonic()+90
 while True:
  last=json.loads(subprocess.check_output(['gcloud','compute','operations','describe',op,'--project=executespecv1','--zone='+zone,'--format=json'],text=True,timeout=60))
  if last['status']=='DONE' or time.monotonic()>until:break
  time.sleep(3)
 (P/('operation-'+zone+'.json')).write_text(json.dumps(last,indent=2)+'\n')
 print(zone,last['status'],last.get('error',{}).get('errors',[{}])[0].get('code'),flush=True)
 last_zone=zone
 if last['status']!='DONE' or not last.get('error'):break
