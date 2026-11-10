"""Provision one bounded L4 qualification lease after explicit local preparation."""
from pathlib import Path
import argparse,datetime,json,subprocess
from cloud_training.budget import reserve
ROOT=Path(__file__).resolve().parents[1]
PROJECT='executespecv1'
BASE='gs://forge-ownbase-a100-20261110/l4-qualification-v1'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--zone',default='us-central1-a');ap.add_argument('--run-id',required=True)
    ap.add_argument('--machine',choices=('g2-standard-4','g2-standard-8','a2-highgpu-1g'),default='g2-standard-8');ap.add_argument('--provisioning',choices=('SPOT','STANDARD','FLEX_START'),default='SPOT');ap.add_argument('--wait-for',choices=('0s','30m'),default='0s');ap.add_argument('--async-create',action='store_true');ap.add_argument('--hours',type=int,choices=(2,3),default=3);ap.add_argument('--execute',action='store_true');a=ap.parse_args()
    if not a.run_id.startswith('forge-ownbase-l4-') or not all(c.islower() or c.isdigit() or c=='-' for c in a.run_id):raise ValueError('invalid run id')
    if a.zone not in json.loads((ROOT/'reports/l4-qualification-v1/supported-zones.json').read_text()):raise ValueError('Zone not in verified supported-machine inventory')
    receipt=json.loads((ROOT/'reports/l4-qualification-v1/bundle-receipt.json').read_text())
    digest=receipt['bundle_sha256'];uri=f'{BASE}/source/{digest}.tar.gz'
    args=['gcloud','compute','instances','create',a.run_id,'--project='+PROJECT,'--zone='+a.zone,
          '--machine-type='+a.machine,'--provisioning-model='+a.provisioning,
          '--image=pytorch-2-9-cu129-ubuntu-2404-nvidia-580-v20261029','--image-project=deeplearning-platform-release',
          '--boot-disk-size=100GB','--boot-disk-type=pd-balanced','--boot-disk-auto-delete',
          '--maintenance-policy=TERMINATE','--no-restart-on-failure','--max-run-duration='+str(a.hours)+'h',
          '--instance-termination-action=DELETE','--no-address','--subnet=default',
          '--service-account=forge-ownbase-bench@executespecv1.iam.gserviceaccount.com',
          '--scopes=https://www.googleapis.com/auth/devstorage.read_write',
          '--labels=purpose=ownbase-qualification,budget=usd100',
          '--metadata=enable-oslogin=TRUE,block-project-ssh-keys=TRUE,code-sha256='+digest+',bundle-uri='+uri+',run-id='+a.run_id,
          '--metadata-from-file=startup-script='+str(ROOT/'cloud_training/l4_server.sh'),'--quiet','--format=json']
    if a.provisioning=='FLEX_START': args.append('--request-valid-for-duration='+a.wait_for)
    if a.async_create: args.append('--async')
    out=ROOT/'reports/l4-qualification-v1';(out/(a.run_id+'-request.json')).write_text(json.dumps({'args':args,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'max_runtime_hours':a.hours,'reservation_envelope_usd':a.hours*6,'note':'Envelope is conservative, not expected L4 bill. No long-run command.'},indent=2)+'\n')
    if not a.execute:print(json.dumps(args));return
    ledger=json.loads((ROOT/'reports/gcp-a100-diagnostic-v1/spend-ledger.json').read_text())
    if any(x['state']=='reserved_before_provisioning' for x in ledger['allocations']):raise RuntimeError('Outstanding GPU reservation/request; reconcile it before another launch')
    subprocess.run(['gcloud','compute','machine-types','describe',a.machine,'--zone='+a.zone,'--project='+PROJECT,'--format=value(name)'],check=True,capture_output=True,text=True,timeout=60)
    region=a.zone.rsplit('-',1)[0]
    subnet=json.loads(subprocess.check_output(['gcloud','compute','networks','subnets','describe','default','--region='+region,'--project='+PROJECT,'--format=json'],text=True))
    if not subnet.get('privateIpGoogleAccess'):raise RuntimeError('Private Google Access required before private GPU launch')
    instances=json.loads(subprocess.check_output(['gcloud','compute','instances','list','--project='+PROJECT,'--format=json'],text=True))
    if any(x['name'].startswith('forge-ownbase-') for x in instances):raise RuntimeError('Existing project model VM; inspect/clean it before another GPU lease')
    from cloud_training.l4_package import sha
    bundle=ROOT/'runs/l4-qualification-bundle.tar.gz'
    if sha(bundle)!=digest:raise ValueError('Bundle changed after receipt')
    subprocess.run(['gcloud','storage','cp',str(bundle),uri,'--quiet','--no-clobber'],check=True,timeout=600)
    reserve(ROOT/'reports/gcp-a100-diagnostic-v1/spend-ledger.json',a.run_id,a.hours)
    result=subprocess.run(args,capture_output=True,text=True,timeout=600)
    (out/(a.run_id+'-response.json')).write_text(json.dumps({'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr},indent=2)+'\n')
    print(result.stdout);print(result.stderr)
    if result.returncode:raise SystemExit(result.returncode)
if __name__=='__main__':main()
