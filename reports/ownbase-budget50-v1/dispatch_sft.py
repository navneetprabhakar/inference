"""Single hash-bound dispatch of the prequalified finite2K pilot. No VM start."""
import datetime,fcntl,hashlib,json,os,subprocess,time
from pathlib import Path
from urllib.parse import quote
from gcp_api import request
R=Path('runs/ownbase-budget50-v1');P=Path('reports/ownbase-budget50-v1');lock=(R/'sft-dispatch.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
c=json.loads((P/'launch-config.json').read_text());packet=json.loads((P/'sft-packet.json').read_text());assert packet['all_packet_files_independent_sha_readback'];prefix=c['run_prefix'];bucket=prefix.split('/')[2];obj='/'.join(prefix.split('/')[3:]);deadline=json.loads((R/'launch-receipt.json').read_text())['external_stop_epoch']-1800
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(name):return request('https://storage.googleapis.com/storage/v1/b/'+bucket+'/o/'+quote(obj+'/'+name,safe='')+'?alt=media',timeout=30)
last=None
while time.time()<deadline:
 try:
  state=read('controller.json');phase=state['phase']
  if phase!=last:print(datetime.datetime.now(datetime.timezone.utc).isoformat(),phase,flush=True);last=phase
  if phase=='final_backup':break
  if phase=='base_complete_awaiting_reviewed_sft_packet':
   step=int(Path(state['parent']).name.split('-')[-1]);assert 11445<step<=19074
   journal=read('base/checkpoints/retention-journal.json');entries=[e for e in journal['entries'] if e['state']=='committed' and e['receipt']['step']==step];assert len(entries)==1
   rec=entries[0]['receipt'];assert rec['remote_prefix'].startswith(prefix+'/base/checkpoints/checkpoint-')
   d=R/'dispatch-parent';d.mkdir(exist_ok=True)
   for name in ['manifest.json','metadata.json','COMMITTED']:subprocess.run(['gcloud','storage','cp',rec['remote_prefix']+'/'+name,str(d/name),'--quiet'],check=True,timeout=60)
   manifest=json.loads((d/'manifest.json').read_text());meta=json.loads((d/'metadata.json').read_text());assert manifest==rec['manifest'];assert meta['step']==step and meta['identity']==c['parent_receipt']['identity'];assert sha(d/'metadata.json')==manifest['files']['metadata.json']['sha256']
   approved={'run_id':c['run_id'],'base_manifest_sha256':sha(d/'manifest.json'),'script_uri':packet['script_uri'],'script_sha256':packet['script_sha256'],'scope':'Previously reviewed bounded2K pilot; no automatic promotion; no4K or extraVM','base_step':step,'checkpoint_remote_prefix':rec['remote_prefix'],'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
   file=R/'approved-next-stage.json';file.write_text(json.dumps(approved,indent=2)+'\n');subprocess.run(['gcloud','storage','cp',str(file),prefix+'/approved-next-stage.json','--quiet'],check=True,timeout=60)
   print('Dispatched exact parent',step,approved['base_manifest_sha256'],flush=True);break
 except Exception as e:print(datetime.datetime.now(datetime.timezone.utc).isoformat(),'retry',type(e).__name__,str(e)[:300],flush=True)
 time.sleep(30)
