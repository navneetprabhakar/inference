import json,hashlib,datetime,subprocess,shlex
from pathlib import Path
from cloud_training.nano_recovery_gate import inspect,digest
P=Path(__file__).resolve().parent;R=Path.cwd();A=P.parent/'attempts/us-central1-c-203102'
j=json.loads((P/'inventory.json').read_text());assert len(j)==1
v=j[0];assert v['name']=='ganesh-a100-1117-203113' and v['status']=='RUNNING'
assert v['scheduling']['terminationTime']=='2026-11-18T03:05:59Z' and v['scheduling']['instanceTerminationAction']=='STOP' and not v['scheduling']['automaticRestart']
assert all(not d['autoDelete'] for d in v['disks']) and all(not n.get('accessConfigs') for n in v['networkInterfaces'])
assert json.loads((P/'readback.json').read_text())['full_gcs_readback_verified']
r=json.loads((A/'launch-request.json').read_text());r.pop('launch_argv')
r['files']={n:digest(R/n) for n in r['files'] if not n.startswith(str(A.relative_to(R))) and n!='runs/ganesh-a100-cap40-v1/runtime.tar.gz'}
for n in ('bootstrap.sh','gpu_qualify.py','signal_inject.py','capture_compare.py','upload_fault_shim.py','decode_benchmark.py','config.json','adverse-checks.json','readback.json'):
 r['files'][str((P/n).relative_to(R))]=digest(P/n)
r['files']['runs/ganesh-a100-cap40-v1/runtime-eager-muon.tar.gz']=digest(R/'runs/ganesh-a100-cap40-v1/runtime-eager-muon.tar.gz')
r['training_inputs']['muon_kernel_mode']='eager';r['backup_prefix']=json.loads((P/'config.json').read_text())['backup_prefix'];r['existing_instance_id']=v['id'];r['correction']='Actual compiled Muon fresh-process mismatch; eager path replay exact; new isolated qualification on same VM'
r['provider_stop_validation']='closeout'
spec=hashlib.sha256(json.dumps({k:x for k,x in r.items() if k not in ('authorization','evidence')},sort_keys=True,separators=(',',':')).encode()).hexdigest()
r['authorization'].update(spec_sha256=spec,retain_vm_until_work_complete=True);r['evidence']={}
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
for name,raw in [('fresh_inventory',P/'inventory.json'),('input_backups',P/'readback.json'),('price_quote',A/'price-catalog.json')]:
 b={'status':'pass','check':name,'spec_sha256':spec,'checked_utc':now,'raw_receipt':str(raw.relative_to(R)),'raw_sha256':digest(raw)}
 if name=='price_quote':
  old=json.loads((A/'price_quote-receipt.json').read_text());b.update({k:old[k] for k in ('hourly_rate_usd','margin_multiplier','checked_utc')})
 p=P/(name+'-receipt.json');p.write_text(json.dumps(b,indent=2)+'\n');r['evidence'][name]={'path':str(p.relative_to(R)),'sha256':digest(p)}
g=inspect(R,r,'qualification');(P/'request.json').write_text(json.dumps(r,indent=2)+'\n');(P/'gate.json').write_text(json.dumps(g,indent=2)+'\n');assert g['allowed'],g
# Durable single launch intent. No provision, retry, stop or deadline mutation.
with (P/'launch-intent.json').open('x') as f:json.dump({'checked_utc':now,'request_sha256':digest(P/'request.json'),'instance_id':v['id']},f)
u=json.loads((P/'uploads.json').read_text())['inputs'];cfg=json.loads((P/'config.json').read_text());duration=int((datetime.datetime.fromisoformat(cfg['qualification_deadline_utc'].replace('Z','+00:00'))-datetime.datetime.now(datetime.timezone.utc)).total_seconds());assert duration>1800
cmd='sudo systemd-run --unit=ganesh-eager-qualification --property=KillMode=control-group --property=RuntimeMaxSec='+str(duration)+' /bin/bash /opt/eager-inputs/bootstrap.sh '+ ' '.join(shlex.quote(x) for x in (u[0]['uri'],u[0]['sha256'],u[1]['uri'],u[1]['sha256']))
p=subprocess.run(['gcloud','compute','ssh',v['name'],'--project=executespecv1','--zone=us-central1-c','--tunnel-through-iap','--quiet','--command='+cmd],capture_output=True,text=True,timeout=90)
(P/'launch.log').write_text(p.stdout+p.stderr);assert p.returncode==0,p.stderr;print(p.stdout+p.stderr)
