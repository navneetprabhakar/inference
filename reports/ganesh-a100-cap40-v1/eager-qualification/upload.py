import json,subprocess,hashlib,datetime as dt
from pathlib import Path
P=Path(__file__).resolve().parent;R=Path('runs/ganesh-a100-cap40-v1');cfg=json.loads((P/'config.json').read_text());prefix=cfg['backup_prefix']+'/inputs';proof=[]
for path,name in [(R/'runtime-eager-muon.tar.gz','runtime.tar.gz'),(R/'eager-qualification-packet.tar.gz','packet.tar.gz'),(P/'bootstrap.sh','bootstrap.sh')]:
 with path.open('rb') as f:sha=hashlib.file_digest(f,'sha256').hexdigest()
 uri=prefix+'/'+name;subprocess.run(['gcloud','storage','cp',str(path),uri,'--if-generation-match=0','--quiet'],check=True,timeout=600)
 metadata=json.loads(subprocess.check_output(['gcloud','storage','objects','describe',uri,'--format=json'],text=True,timeout=90));local=json.loads(subprocess.check_output(['gcloud','storage','hash',str(path),'--format=json'],text=True,timeout=90))[0]
 assert metadata['crc32c_hash']==local['crc32c_hash'] and int(metadata['size'])==path.stat().st_size
 proof.append({'path':str(path),'uri':uri,'sha256':sha,'bytes':path.stat().st_size,'generation':metadata['generation'],'crc32c_verified':True,'worker_full_readback_required':True})
(P/'uploads.json').write_text(json.dumps({'checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'inputs':proof},indent=2)+'\n');print('Corrective runtime, packet and bootstrap uploaded; VM must verify full SHA before work')
