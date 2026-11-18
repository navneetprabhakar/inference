"""Recovery/backup only after failed qualification; no training or journal rewrite."""
import datetime as dt,hashlib,json,os,subprocess,sys,tarfile,time
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.l4_recovery_check import roundtrip_bundle,COMPONENTS
ROOT=Path('/opt/ganesh-conversation');Q=ROOT/'qualification-v2';cfg=json.loads((ROOT/'config-v2.json').read_text());stop=dt.datetime.fromisoformat(cfg['provider_stop_utc'].replace('Z','+00:00')).timestamp()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for proc in Path('/proc').glob('[0-9]*/cmdline'):
 try:args=proc.read_bytes().split(b'\0')
 except OSError:continue
 if b'cloud_training.nano_sft' in args or any(x.endswith(b'/gpu_qualify.py') for x in args):raise RuntimeError('Training/qualification writer still active')
assert json.loads((Q/'qualification.json').read_text())['status']=='hold'
assert not (ROOT/'pilot').exists(),'Unexpected learning pilot directory'
result={'status':'recovering','pilot_started':False,'writers_joined':True,'checkpoints':[],'provider_stop_utc':cfg['provider_stop_utc']}
# Verify every retained local qualification bundle, preserving failed journals.
for path in sorted(Q.glob('*/step-[0-9]*')):
 branch=path.parent.name;step=int(path.name.split('-')[1]);manifest=validate_bundle(path)
 if stop-time.time()<1800:raise TimeoutError('Insufficient finite lease; retain recovery disk')
 started=time.monotonic();journal=json.loads((path.parent/'retention-journal.json').read_text())
 committed=[e['receipt'] for e in journal['entries'] if e['state']=='committed' and e['receipt']['step']==step and e['receipt']['manifest']==manifest]
 destination=ROOT/f'recovery-readback-{branch}-{step}'
 if committed:
  receipt=dict(committed[0]);destination.mkdir()
  for name in COMPONENTS:
   subprocess.run(['gcloud','storage','cp',receipt['remote_prefix']+'/'+name,str(destination/name),'--quiet'],check=True,timeout=300)
  if validate_bundle(destination)!=manifest:raise ValueError('Remote checkpoint differs')
  if (destination/'metadata.json').read_bytes()!=(path/'metadata.json').read_bytes():raise ValueError('Remote metadata differs')
  receipt.update(independent_sha256_readback=True,status='gcs_bundle_integrity_passed')
 else:
  receipt=roundtrip_bundle(path,remote_prefix=cfg['backup_prefix']+'/recovery/'+branch+'/checkpoints',destination=destination,timeout=900)
 if receipt.get('independent_sha256_readback') is not True:raise ValueError('Missing independent full readback')
 result['checkpoints'].append({'branch':branch,'step':step,'manifest_sha256':sha(path/'manifest.json'),'receipt':receipt,'recovery_roundtrip_seconds':time.monotonic()-started})
 (ROOT/'recovery-backups.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['checkpoints'] and any(r['branch']=='split_first' and r['step']==1 for r in result['checkpoints'])
# All source, controls and raw traces; no huge redundant parent payload/caches.
archive=ROOT/'recovery-evidence.tar.gz'
assert not archive.exists()
with tarfile.open(archive,'w:gz',compresslevel=1) as tar:
 for folder in ('qualification','qualification-v2','reports/ganesh-conversation-pilot-v1','reports/ganesh-conversation-execution-v1','cloud_training'):
  for path in sorted((ROOT/folder).rglob('*')):
   if path.is_file() and path.name!='payload.pt' and '__pycache__' not in path.parts:tar.add(path,arcname=str(path.relative_to(ROOT)),recursive=False)
 for name in ('bootstrap.log','config.json','config-v2.json','package-manifest.json','package-manifest-v1.json','qualification-v1-backup.json','recovery-backups.json'):
  tar.add(ROOT/name,arcname=name,recursive=False)
uri=cfg['backup_prefix']+'/recovery/recovery-evidence.tar.gz'
subprocess.run(['gcloud','storage','cp',str(archive),uri,'--if-generation-match=0','--quiet'],check=True,timeout=300)
copy=ROOT/'recovery-evidence.readback';subprocess.run(['gcloud','storage','cp',uri,str(copy),'--quiet'],check=True,timeout=300)
assert sha(copy)==sha(archive);copy.unlink()
result.update(status='required_backups_verified',evidence={'uri':uri,'sha256':sha(archive),'readback_verified':True},local_parent_preserved=True,quality_accepted=False)
(ROOT/'recovery-backups.json').write_text(json.dumps(result,indent=2)+'\n')
receipt_uri=cfg['backup_prefix']+'/recovery/recovery-backups.json'
subprocess.run(['gcloud','storage','cp',str(ROOT/'recovery-backups.json'),receipt_uri,'--if-generation-match=0','--quiet'],check=True,timeout=120)
copy=ROOT/'recovery-receipt.readback';subprocess.run(['gcloud','storage','cp',receipt_uri,str(copy),'--quiet'],check=True,timeout=120);assert sha(copy)==sha(ROOT/'recovery-backups.json');copy.unlink()
print(json.dumps(result,indent=2))
