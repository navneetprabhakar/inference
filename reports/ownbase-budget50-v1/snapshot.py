"""Read-only live snapshot and conservative incremental cost envelope."""
import datetime,json,time
from pathlib import Path
from urllib.parse import quote
from gcp_api import request
P=Path('reports/ownbase-budget50-v1');R=Path('runs/ownbase-budget50-v1');bucket='forge-ownbase-a100-20261110';obj='ownbase-v2/budget50-v1/'
def read(name):return request('https://storage.googleapis.com/storage/v1/b/'+bucket+'/o/'+quote(obj+name,safe='')+'?alt=media',timeout=30)
vm=request('https://compute.googleapis.com/compute/v1/projects/executespecv1/zones/us-central1-b/instances/forge-ownbase-budget50-v1',timeout=30)
state=read('controller.json');phase=state['phase'];progress=None
if phase=='base_training':progress=read('bootstrap/results/budget50-v1/base-'+str(state['goal_step'])+'/progress.json')
start=datetime.datetime.fromisoformat(vm['lastStartTimestamp']);now=datetime.datetime.now(datetime.timezone.utc);hours=(now-start).total_seconds()/3600
row={'utc':now.isoformat(),'provider_status':vm['status'],'phase':phase,'elapsed_hours':round(hours,3),'conservative_compute_accrual_usd':round(hours*2.5,2),'ancillary_reserved_usd':15,'total_envelope_to_date_usd':round(hours*2.5+15,2),'incremental_cap_usd':50,'invoice_verified':False,'provider_duration_seconds':vm['scheduling']['maxRunDuration']['seconds'],'progress':{k:progress.get(k) for k in ['status','step','targets','train_loss','tokens_per_second_last_update','last_checkpoint']} if progress else None,'controller':state}
(R/'latest-snapshot.json').write_text(json.dumps(row,indent=2)+'\n')
with (R/'snapshots.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
brief={k:v for k,v in row.items() if k not in ['progress','controller']}
if progress:brief.update({k:progress.get(k) for k in ['step','targets','train_loss','tokens_per_second_last_update']});brief['last_backed_step']=progress.get('last_checkpoint',{}).get('step')
print(json.dumps(brief,indent=2))
