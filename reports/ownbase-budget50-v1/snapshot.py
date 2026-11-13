"""Read-only live snapshot and conservative incremental cost envelope."""
import datetime,json,time
from pathlib import Path
from urllib.parse import quote
from gcp_api import request
P=Path('reports/ownbase-budget50-v1');R=Path('runs/ownbase-budget50-v1');bucket='forge-ownbase-a100-20261110';obj='ownbase-v2/budget50-v1/'
def read(name):return request('https://storage.googleapis.com/storage/v1/b/'+bucket+'/o/'+quote(obj+name,safe='')+'?alt=media',timeout=30)
vm=request('https://compute.googleapis.com/compute/v1/projects/executespecv1/zones/us-central1-b/instances/forge-ownbase-budget50-v1',timeout=30)
state=read('controller.json');phase=state['phase'];progress=None;telemetry_note=None
if phase=='base_training':
 try:progress=read('bootstrap/results/budget50-v1/base-'+str(state['goal_step'])+'/progress.json')
 except RuntimeError as exc:
  if '404' not in str(exc):raise
  telemetry_note='Stage announced; first progress object not published yet. No current-step inference.'
start=datetime.datetime.fromisoformat(vm['lastStartTimestamp']);now=datetime.datetime.now(datetime.timezone.utc);end=now
if vm['status']=='TERMINATED' and vm.get('lastStopTimestamp'):end=min(now,datetime.datetime.fromisoformat(vm['lastStopTimestamp']))
hours=max(0,(end-start).total_seconds()/3600)
validation_ce=None
if progress:
 (R/'base-progress-latest.json').write_text(json.dumps(progress,indent=2)+'\n')
 validation=progress.get('validation') or progress.get('pilot_validation_start',{});shards=validation.get('shards',[])
 if validation.get('complete') and shards:
  count=sum(v['target_tokens'] for v in shards);validation_ce=sum(v['cross_entropy_nats']*v['target_tokens'] for v in shards)/count
row={'utc':now.isoformat(),'provider_status':vm['status'],'machine_type':vm['machineType'].rsplit('/',1)[-1],'provisioning_model':vm['scheduling'].get('provisioningModel','STANDARD'),'phase':phase,'elapsed_hours':round(hours,3),'conservative_compute_accrual_usd':round(hours*2.5,2),'ancillary_reserved_usd':15,'total_envelope_to_date_usd':round(hours*2.5+15,2),'incremental_cap_usd':50,'invoice_verified':False,'last_heldout_ce':validation_ce,'telemetry_note':telemetry_note,'provider_duration_seconds':vm['scheduling']['maxRunDuration']['seconds'],'progress':{k:progress.get(k) for k in ['status','step','targets','train_loss','tokens_per_second_last_update','last_checkpoint']} if progress else None,'controller':state}
(R/'latest-snapshot.json').write_text(json.dumps(row,indent=2)+'\n')
with (R/'snapshots.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
brief={k:v for k,v in row.items() if k not in ['progress','controller']}
if progress:brief.update({k:progress.get(k) for k in ['step','targets','train_loss','tokens_per_second_last_update']});brief['last_backed_step']=progress.get('last_checkpoint',{}).get('step')
print(json.dumps(brief,indent=2))
