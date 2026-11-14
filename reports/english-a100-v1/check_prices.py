"""Read public Cloud Billing catalog; credentials remain in memory."""
import json,subprocess,urllib.request,urllib.parse,datetime
from pathlib import Path
p=Path(__file__).parent
token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True,timeout=60).strip();items=[];page=''
while True:
 url='https://cloudbilling.googleapis.com/v1/services/6F81-5844-456A/skus?currencyCode=USD&pageSize=5000'+('&pageToken='+urllib.parse.quote(page) if page else '')
 with urllib.request.urlopen(urllib.request.Request(url,headers={'Authorization':'Bearer '+token}),timeout=60) as f:data=json.load(f)
 items.extend(s for s in data.get('skus',[]) if ('A100' in s['description'] or 'A2 ' in s['description']) and s['category']['usageType']=='OnDemand')
 page=data.get('nextPageToken')
 if not page:break
(p/'price-catalog.json').write_text(json.dumps({'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'skus':items},indent=2)+'\n')
for s in items:
 if any(r in s.get('serviceRegions',[]) for r in ['us-central1','us-east1','us-west1','us-east4']):
  print(s['skuId'],s['description'],s['serviceRegions'],s['pricingInfo'][-1]['pricingExpression']['tieredRates'])
