"""Verify the local evidence readback and retained remote checkpoint metadata."""
import json,hashlib,tarfile,subprocess,datetime
from pathlib import Path
P=Path('reports/ganesh-l4-cap20-v1');A=P/'attempts/us-west1-a-185831';R=Path('runs/ganesh-l4-cap20-v1');archive=R/'qualification-evidence.tar.gz'
close=json.loads((A/'closeout-readback.json').read_text());assert close['all_required_checkpoint_readbacks'] and close['evidence_readback']
with archive.open('rb') as f:hash_=hashlib.file_digest(f,'sha256').hexdigest()
assert hash_==close['evidence_sha256']
with tarfile.open(archive) as t:
 for m in t.getmembers():assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
 def read(name):return t.extractfile(name).read()
 q=json.loads(read('results/qualification.json'));assert q['backup_verified'] and not q['pilot_started']
 comparison=json.loads(read('results/normal-comparison-supplemental.json'));assert comparison['status']=='pass'
 capture=json.loads(read('results/capture-comparison.json'));assert capture['input_values_layout_equal'] and capture['output_values_layout_equal']
 for branch in ('uninterrupted','split_resume'):
  prefix='results/'+branch+'/optimizer-capture/step-00000001/'
  manifest_bytes=read(prefix+'manifest.json');m=json.loads(manifest_bytes)
  assert hashlib.sha256(manifest_bytes).hexdigest()==capture['reference_manifest_sha256']
  for name,meta in m['files'].items():
   with t.extractfile(prefix+name) as f:assert hashlib.file_digest(f,'sha256').hexdigest()==meta['sha256']
  context=json.loads(read(prefix+'context.json'));assert context['environment']['cublas_workspace']==':4096:8'
 for name in ('qualification.json','normal-comparison-supplemental.json','capture-comparison.json','replay-eager-1.log'):(A/name).write_bytes(read('results/'+name))
remote=[]
for index,entry in enumerate(q['bundle_readbacks']):
 assert entry['readback']
 dst=R/('retained-manifest-'+str(index)+'.json')
 subprocess.run(['gcloud','storage','cp',entry['remote_prefix']+'/manifest.json',str(dst),'--quiet'],check=True,capture_output=True,timeout=90)
 assert hashlib.sha256(dst.read_bytes()).hexdigest()==entry['manifest_sha256']
 manifest=json.loads(dst.read_text());payload=json.loads(subprocess.check_output(['gcloud','storage','objects','describe',entry['remote_prefix']+'/payload.pt','--format=json'],text=True,timeout=90))
 assert int(payload['size'])==manifest['files']['payload.pt']['bytes']
 remote.append({'remote_prefix':entry['remote_prefix'],'manifest_sha256':entry['manifest_sha256'],'payload_generation':payload['generation'],'payload_bytes':int(payload['size']),'worker_full_payload_readback':True,'local_manifest_readback':True})
instance=json.loads((A/'instance-final.json').read_text());assert instance['status']=='TERMINATED'
receipt={'status':'required_backups_verified_before_disposable_disk_cleanup','archive_sha256':hash_,'archive_bytes':archive.stat().st_size,'local_archive_and_both_capture_payloads_verified':True,'retained_checkpoints':remote,'vm_status':'TERMINATED','local_default_weights_changed':False,'checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
(A/'retention-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
