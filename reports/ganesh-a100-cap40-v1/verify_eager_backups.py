"""Download/verify required evidence and independently check surviving GCS manifests."""
import datetime as dt,hashlib,json,subprocess,tarfile
from pathlib import Path
P=Path(__file__).resolve().parent
state=json.loads((P/'zone-sweep.json').read_text());a=next(a for a in state['attempts'] if a['status']=='allocated_monitor_qualification');A=P/'eager-qualification';cfg=json.loads((A/'config.json').read_text());R=Path('runs/ganesh-a100-cap40-v1')/a['name']/'eager-r2';R.mkdir(parents=True,exist_ok=True)
def run(argv):return subprocess.run(argv,check=True,text=True,capture_output=True,timeout=3600)
def cp(remote,dest):run(['gcloud','storage','cp',remote,str(dest),'--quiet'])
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
cp(cfg['backup_prefix']+'/closeout.json',A/'closeout-readback.json');close=json.loads((A/'closeout-readback.json').read_text());assert close['all_required_checkpoint_readbacks'] and close['evidence_readback']
archive=R/'qualification-evidence.tar.gz';cp(cfg['backup_prefix']+'/evidence.tar.gz',archive);assert sha(archive)==close['evidence_sha256']
with tarfile.open(archive) as t:
 for m in t.getmembers():assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
 def read(n):return t.extractfile(n).read()
 q=json.loads(read('results/qualification.json'));assert q['backup_verified'] and not q['pilot_started']
 for m in t.getmembers():
  if m.name.endswith('optimizer-capture/step-00000001/manifest.json'):
   manifest=json.loads(read(m.name));prefix=m.name.rsplit('/',1)[0]+'/'
   for n,info in manifest['files'].items():
    with t.extractfile(prefix+n) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==info['sha256']
 for m in t.getmembers():
  if m.name.startswith('results/') and m.name.count('/')==1 and m.name.endswith('.json'):(A/Path(m.name).name).write_bytes(read(m.name))
proofs=[]
for i,entry in enumerate(q['bundle_readbacks']):
 assert entry['readback'];dest=R/f'retained-manifest-{i}.json';cp(entry['remote_prefix']+'/manifest.json',dest);assert sha(dest)==entry['manifest_sha256']
 manifest=json.loads(dest.read_text());payload=json.loads(run(['gcloud','storage','objects','describe',entry['remote_prefix']+'/payload.pt','--format=json']).stdout)
 assert int(payload['size'])==manifest['files']['payload.pt']['bytes']
 proofs.append({**entry,'local_manifest_readback':True,'worker_full_payload_readback':True,'generation':payload['generation']})
receipt={'status':'required_backups_verified','checked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'local_archive_readback_verified':True,'archive_sha256':sha(archive),'archive_path':str(archive),'all_required_checkpoint_readbacks':True,'retained_checkpoints':proofs,'qualification_status':q['status'],'local_default_weights_changed':False}
(A/'backup-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
