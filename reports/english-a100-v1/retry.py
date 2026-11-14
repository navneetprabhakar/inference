"""One explicit same-region capacity retry; no lease or budget extension."""
import hashlib,json,subprocess,sys
from pathlib import Path
p=Path(__file__).parent;new=sys.argv[1]
if new not in ('b','f'):raise ValueError('Only remaining same-price zones allowed')
r=json.loads((p/'launch-request.json').read_text());old=next(a.rsplit('-',1)[1] for a in r['create_argv'] if a.startswith('--zone='));name=r['run_id']
o=json.loads((p/('operation-'+old+'.json')).read_text())
if o['status']!='DONE' or o.get('error',{}).get('errors',[{}])[0].get('code')!='ZONE_RESOURCE_POOL_EXHAUSTED_WITH_DETAILS':raise ValueError('Not confirmed capacity failure')
l=json.loads((p/'spend-ledger.json').read_text());allocation=l['allocations'][-1]
if allocation['state']!='create_requested' or 'us-central1-'+new in allocation.get('failed_capacity_attempts',[]):raise ValueError('Not a new bounded retry')
i=json.loads(subprocess.check_output(['gcloud','compute','instances','list','--project=executespecv1','--format=json(name,status)'],text=True,timeout=60));d=json.loads(subprocess.check_output(['gcloud','compute','disks','list','--project=executespecv1','--filter=name='+name,'--format=json'],text=True,timeout=60))
if any(x['name']==name for x in i) or d:raise ValueError('Resources remain')
(p/('reconcile-'+old+'.json')).write_text(json.dumps({'instances':i,'new_disks':d},indent=2)+'\n')
(p/'launch-request.json').rename(p/('launch-request-'+old+'.json'));(p/'launch-response.json').rename(p/('launch-response-'+old+'.json'))
r['create_argv']=['--zone=us-central1-'+new if a.startswith('--zone=') else a for a in r['create_argv']];(p/'launch-request.json').write_text(json.dumps(r,indent=2)+'\n')
allocation.update(state='reserved_before_provisioning',request_sha256=hashlib.sha256((p/'launch-request.json').read_bytes()).hexdigest());allocation.setdefault('failed_capacity_attempts',[]).append('us-central1-'+old);(p/'spend-ledger.json').write_text(json.dumps(l,indent=2)+'\n')
subprocess.run([sys.executable,str(p/'execute_lease.py')],check=True,timeout=150)
