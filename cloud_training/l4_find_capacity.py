"""Sequential bounded qualification allocation; never launches two GPU writers."""
import datetime,fcntl,json,subprocess,sys
from pathlib import Path
from cloud_training.runtime import atomic_json
ROOT=Path(__file__).resolve().parents[1]
PROJECT='executespecv1'

def call(parts):
 return subprocess.run(['gcloud',*parts,'--project='+PROJECT,'--format=json','--quiet'],capture_output=True,text=True,timeout=90)

def verify_no_resources():
 for kind in ('instances','disks'):
  p=call(['compute',kind,'list']);p.check_returncode()
  if any(x['name'].startswith('forge-ownbase-') for x in json.loads(p.stdout)):raise RuntimeError('Existing own-base resource; reconcile before capacity search')

def close_failed():
 verify_no_resources()
 path=ROOT/'reports/gcp-a100-diagnostic-v1/spend-ledger.json'
 with path.with_suffix('.lock').open('a+') as f:
  fcntl.flock(f,fcntl.LOCK_EX);v=json.loads(path.read_text())
  for a in v['allocations']:
   r=ROOT/'reports/l4-qualification-v1'/(a['id']+'-response.json')
   if a['state']!='reserved_before_provisioning' or not r.exists():continue
   response=json.loads(r.read_text())
   if response['returncode'] and ('ZONE_RESOURCE_POOL_EXHAUSTED' in response['stderr'] or 'Machine type with name' in response['stderr']):
    a.update(original_reservation_usd=a['reserved_usd'],reserved_usd=0,state='closed_verified_no_instance_or_disk_capacity_failure',verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
  v['total_including_ancillary_reserve_usd']=sum(a['reserved_usd'] for a in v['allocations'])+v['ancillary_reserve_usd'];v['remaining_unallocated_usd']=v['cap_usd']-v['total_including_ancillary_reserve_usd'];atomic_json(path,v)

def main():
 zones=['us-east1-b','us-east1-c','us-east1-d','us-west4-a','us-west4-c','europe-west4-a','europe-west4-b','europe-west4-c']
 region_ready=set();network=[];report=ROOT/'reports/l4-qualification-v1/capacity-search.json'
 close_failed()
 for index,zone in enumerate(zones,13):
  region=zone.rsplit('-',1)[0]
  if region not in region_ready:
   p=call(['compute','regions','describe',region]);p.check_returncode();quotas=json.loads(p.stdout)['quotas']
   if not any(q['metric']=='PREEMPTIBLE_NVIDIA_L4_GPUS' and q['limit']-q['usage']>=1 for q in quotas):continue
   p=call(['compute','networks','subnets','describe','default','--region='+region]);p.check_returncode();before=json.loads(p.stdout)
   if not before.get('privateIpGoogleAccess'):
    p=call(['compute','networks','subnets','update','default','--region='+region,'--enable-private-ip-google-access']);p.check_returncode()
   network.append({'region':region,'private_google_access_before':bool(before.get('privateIpGoogleAccess'))})
   region_ready.add(region)
  run=f'forge-ownbase-l4-{index:02d}'
  atomic_json(report,{'state':'attempting','run':run,'zone':zone,'network_changes':network})
  p=subprocess.run([sys.executable,'-m','cloud_training.l4_launch','--run-id',run,'--zone',zone,'--execute'],cwd=ROOT,capture_output=True,text=True,timeout=750)
  print(json.dumps({'run':run,'zone':zone,'returncode':p.returncode}),flush=True)
  if p.returncode==0:
   atomic_json(report,{'state':'allocated','run':run,'zone':zone,'network_changes':network});return
  close_failed()
 atomic_json(report,{'state':'bounded_search_exhausted','network_changes':network,'note':'No additional GPU allocated; do not claim training running'})
 raise SystemExit(2)
if __name__=='__main__':main()
