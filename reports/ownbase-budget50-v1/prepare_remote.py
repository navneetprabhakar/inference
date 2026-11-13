"""Prepare an isolated GCS lineage; no VM creation/start."""
import json,copy,hashlib,time
from pathlib import Path
from urllib.parse import quote
from gcp_api import request
R=Path('runs/ownbase-budget50-v1');P=Path('reports/ownbase-budget50-v1');bucket='forge-ownbase-a100-20261110';prefix='ownbase-v2/budget50-v1';uri='gs://'+bucket+'/'+prefix
old=json.loads((R/'gcs-journal.json').read_text());entry=max((e for e in old['entries'] if e['state']=='committed'),key=lambda e:e['receipt']['step']);assert entry['receipt']['step']==11445
entry=copy.deepcopy(entry);source=entry['receipt']['remote_prefix'].split(bucket+'/')[1];dest=prefix+'/base/checkpoints/'+source.rsplit('/',1)[1]
for name in ['payload.pt','metadata.json','manifest.json','COMMITTED']:
 url=f'https://storage.googleapis.com/storage/v1/b/{bucket}/o/{quote(source+"/"+name,safe="")}/rewriteTo/b/{bucket}/o/{quote(dest+"/"+name,safe="")}?ifGenerationMatch=0'
 result=request(url,method='POST',payload={},timeout=90);assert result['done'];print('copied',name,flush=True)
entry['receipt']['remote_prefix']='gs://'+bucket+'/'+dest
entry['pins']=sorted(set(entry.get('pins',[])+['milestone']))
journal={'schema':1,'campaign_prefix':uri+'/base/checkpoints','identity':old['identity'],'lease_phase':'ready','entries':[entry]}
(R/'new-base-journal.json').write_text(json.dumps(journal,indent=2)+'\n')
config=json.loads(Path('reports/l4-qualification-v1/retained-recovery-3b-config.json').read_text())
config.pop('retained',None);config.update(run_id='forge-ownbase-budget50-v1',backup_prefix=uri+'/base/checkpoints',resume_step=11445,max_runtime_seconds=50400,checkpoint_seconds=900,deterministic_attention=True,max_updates=7629)
config['budget']={'incremental_total_cap_usd':50,'compute_upper_usd_per_hour':2.5,'max_compute_hours':14,'compute_reservation_usd':35,'storage_transfer_and_uncertainty_reserve_usd':15,'base_deadline_seconds_from_boot':41400,'final_training_deadline_seconds_from_boot':45000,'backup_deadline_seconds_from_boot':49200,'os_stop_seconds_from_boot':49800,'provider_stop_seconds_from_boot':50400,'billing_export_available':False,'prior_project_spend':'Historical; not reset or represented as verified. Latest user authorizes this50USD execution.'}
config['run_prefix']=uri;config['parent_receipt']=entry['receipt'];config['price_sources']=['https://cloud.google.com/products/compute/pricing/accelerator-optimized','https://docs.cloud.google.com/compute/docs/instances/create-flex-start-vm']
(P/'launch-config.json').write_text(json.dumps(config,indent=2)+'\n')
print('Isolated journal/config prepared; upload immutable journal before launch',flush=True)
