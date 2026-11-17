import hashlib,json,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent;R=Path('runs/ganesh-a100-cap40-v1');s=json.loads((P/'zone-sweep.json').read_text());a=next(a for a in s['attempts'] if a['status']=='allocated_monitor_qualification');cfg=json.loads((Path(a['directory'])/'config.json').read_text());path=R/'runtime-retain-vm.tar.gz';uri=cfg['backup_prefix']+'/inputs/pilot-runtime-retain-vm.tar.gz'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
assert sha(path)=='7d24bf103e02aad1a9d01288622654f7c7169f706d0a3d4258be2e52ee9ed416'
subprocess.run(['gcloud','storage','cp',str(path),uri,'--if-generation-match=0','--quiet'],check=True,timeout=600)
readback=R/'pilot-runtime.readback';subprocess.run(['gcloud','storage','cp',uri,str(readback),'--quiet'],check=True,timeout=600);assert sha(readback)==sha(path);readback.unlink()
(P/'pilot-runtime-backup.json').write_text(json.dumps({'uri':uri,'sha256':sha(path),'bytes':path.stat().st_size,'independent_readback':True},indent=2)+'\n');print('Pilot runtime GCS readback verified')
