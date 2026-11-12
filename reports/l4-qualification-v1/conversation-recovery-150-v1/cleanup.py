"""Remove only local initial snapshots with verified immutable GCS copies."""
import json,time,shutil,hashlib,subprocess
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_retention import _verify_remote
root=Path('/opt/ownbase-nano/results');report={'before_free':shutil.disk_usage(root).free,'removed':[],'skipped':[]}
for journal in sorted(root.glob('*/sft/retention-journal.json')):
 if shutil.disk_usage(root).free>=30*1024**3:break
 try:
  data=json.loads(journal.read_text());initial=journal.parent/'step-00000000'
  finals=[p for p in journal.parent.glob('step-*') if p.name!='step-00000000' and (p/'COMMITTED').is_file()]
  if not initial.is_dir() or not finals:continue
  receipt=next(e['receipt'] for e in data['entries'] if e['state']=='committed' and e['receipt']['step']==0)
  manifest=validate_bundle(initial)
  if manifest!=receipt['manifest']:raise ValueError('Local manifest differs from upload receipt')
  _verify_remote(receipt,time.monotonic()+180)
  size=sum(p.stat().st_size for p in initial.iterdir() if p.is_file())
  shutil.rmtree(initial)
  report['removed'].append({'local':str(initial),'backup':receipt['remote_prefix'],'bytes':size,'verification':'local fullSHA, remote commitment/manifest and object sizes; original checksum-validated upload'})
 except Exception as e:report['skipped'].append({'journal':str(journal),'reason':str(e)})
report['after_free']=shutil.disk_usage(root).free
Path('/run/ownbase-cleanup-receipt.json').write_text(json.dumps(report,indent=2)+'\n')
subprocess.run(['gcloud','storage','cp','/run/ownbase-cleanup-receipt.json','gs://forge-ownbase-a100-20261110/ownbase-v2/conversation-recovery-150-v1/cleanup-receipt.json','--quiet'],check=True,timeout=90)
print(json.dumps(report),flush=True)
if report['after_free']<15*1024**3:raise RuntimeError('Less than15GiB available: training refused')
