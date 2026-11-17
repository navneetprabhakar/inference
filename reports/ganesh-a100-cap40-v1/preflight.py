import subprocess,json,datetime,hashlib,urllib.request,urllib.parse
from pathlib import Path
P=Path(__file__).resolve().parent
def cloud(args,project='executespecv1'):
 return json.loads(subprocess.check_output(['gcloud',*args,'--project='+project,'--format=json'],text=True,timeout=90))
def write(n,x):(P/n).write_text(json.dumps(x,indent=2)+'\n')
instances=cloud(['compute','instances','list']);disks=cloud(['compute','disks','list']);assert not instances and not disks
write('inventory.json',{'instances':instances,'disks':disks,'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()})
region=cloud(['compute','regions','describe','us-central1']);write('region.json',region)
assert any(q['metric']=='NVIDIA_A100_GPUS' and q['limit']-q['usage']>=1 for q in region['quotas'])
image=cloud(['compute','images','describe','pytorch-2-9-cu129-ubuntu-2404-nvidia-580-v20261111'],'deeplearning-platform-release');write('image.json',image);assert image['status']=='READY' and not image.get('deprecated')
machine=cloud(['compute','machine-types','describe','a2-highgpu-1g','--zone=us-central1-a']);write('machine.json',machine);assert machine['memoryMb']==87040
subnet=cloud(['compute','networks','subnets','describe','default','--region=us-central1']);write('subnet.json',subnet);assert subnet.get('privateIpGoogleAccess')
# Fetch only relevant public billing metadata; token never printed or persisted.
token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,timeout=60).strip();items=[];page=''
while True:
 url='https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus?currencyCode=USD&pageSize=5000'+('&pageToken='+urllib.parse.quote(page) if page else '')
 with urllib.request.urlopen(urllib.request.Request(url,headers={'Authorization':'Bearer '+token}),timeout=60) as f:data=json.load(f)
 items += [s for s in data.get('skus',[]) if s['category']['usageType']=='OnDemand' and 'us-central1' in s.get('serviceRegions',[]) and any(t in s['description'].lower() for t in ('a100','a2 ', 'balanced pd'))]
 page=data.get('nextPageToken')
 if not page:break
write('price-catalog.json',{'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'skus':items})
print(json.dumps({'instances':len(instances),'disks':len(disks),'sku_count':len(items),'image':image['name'],'A100_quota':'available','private_google_access':True}))
