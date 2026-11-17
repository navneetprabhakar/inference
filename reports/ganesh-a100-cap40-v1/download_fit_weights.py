import datetime,hashlib,json,subprocess
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
P=Path('reports/ganesh-a100-cap40-v1');j=json.loads((P/'assessment/training/retention-journal.json').read_text());receipts=[]
for e in j['entries']:
 r=e['receipt'];step=r['step']
 if e['state']!='committed' or step not in (20,30):continue
 d=Path(f'runs/ganesh-a100-cap40-v1/local-fit/step-{step:08d}');d.mkdir(parents=True,exist_ok=True)
 for name in ('manifest.json','metadata.json','payload.pt','COMMITTED'):
  subprocess.run(['gcloud','storage','cp',r['remote_prefix']+'/'+name,str(d/name),'--quiet'],check=True,timeout=3600)
 validate_bundle(d)
 assert json.loads((d/'manifest.json').read_text())==r['manifest']
 receipts.append({'step':step,'local_path':str(d.resolve()),'remote_prefix':r['remote_prefix'],'manifest_sha256':hashlib.sha256((d/'manifest.json').read_bytes()).hexdigest(),'full_payload_readback_verified':True,'accepted_for_conversation':False})
 (P/'local-fit-weights.json').write_text(json.dumps({'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checkpoints':receipts,'default_changed':False},indent=2)+'\n')
 print('Verified local failed-diagnostic checkpoint',step,flush=True)
assert len(receipts)==2
