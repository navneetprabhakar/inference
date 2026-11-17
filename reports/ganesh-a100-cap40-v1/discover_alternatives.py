"""Read-only global A100 prices/quota discovery; no allocation or network change."""
import datetime,json,subprocess,urllib.request,urllib.parse
from pathlib import Path
P=Path(__file__).resolve().parent
regions=json.loads(subprocess.check_output(['gcloud','compute','regions','list','--project=executespecv1','--format=json'],text=True,timeout=90));(P/'all-region-quotas.json').write_text(json.dumps(regions,indent=2)+'\n')
token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,timeout=60).strip();items=[];page=''
while True:
 url='https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus?currencyCode=USD&pageSize=5000'+('&pageToken='+urllib.parse.quote(page) if page else '')
 with urllib.request.urlopen(urllib.request.Request(url,headers={'Authorization':'Bearer '+token}),timeout=60) as f:data=json.load(f)
 items += [s for s in data.get('skus',[]) if s['category']['usageType']=='OnDemand' and any(t in s['description'].lower() for t in ('a100','a2 ', 'balanced pd'))]
 page=data.get('nextPageToken')
 if not page:break
(P/'global-price-catalog.json').write_text(json.dumps({'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'skus':items},indent=2)+'\n')
supported=json.loads((P/'a100-supported-zones.json').read_text());out=[]
for r in regions:
 q=next((q for q in r['quotas'] if q['metric']=='NVIDIA_A100_GPUS'),None)
 zones=[x['zone'].rsplit('/',1)[-1] for x in supported if x['zone'].rsplit('/',1)[-1].rsplit('-',1)[0]==r['name']]
 if q and q['limit']-q['usage']>=1 and zones:out.append({'region':r['name'],'zones':zones,'quota_free':q['limit']-q['usage']})
(P/'available-quota-regions.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
