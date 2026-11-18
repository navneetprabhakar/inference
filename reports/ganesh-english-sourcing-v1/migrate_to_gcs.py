"""Explicit post-auth, hash-verified payload migration. No VM operations.

Default is plan-only. --apply uploads/readbacks; --evict additionally removes ONLY
allowlisted payloads whose local hash still equals the verified GCS object hash.
Writes a durable receipt before unlink. Never deletes model/frozen/report files.
"""
import argparse,hashlib,json,subprocess,time,threading,os,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];R=Path(__file__).resolve().parent
PREFIX='gs://forge-ownbase-a100-20261110/ganesh-english-sourcing-v1'
ALLOWED=[ROOT/'runs/english-source-shortlist-v1/smol.parquet',ROOT/'runs/english-source-shortlist-v1/oasst.gz']
ALLOWED+=list((ROOT/'runs/ganesh-english-sourcing-v1').glob('*.jsonl'))

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def readback(uri,expected_bytes):
 h=hashlib.sha256();size=0
 with subprocess.Popen(['gcloud','storage','cat',uri],stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True) as proc:
  def expire():
   try:os.killpg(proc.pid,signal.SIGKILL)
   except ProcessLookupError:pass
  timer=threading.Timer(600,expire);timer.daemon=True;timer.start()
  try:
   for block in iter(lambda:proc.stdout.read(1024*1024),b''):
    size+=len(block)
    if size>expected_bytes:expire();raise ValueError('Unexpected object length')
    h.update(block)
   err=proc.stderr.read();rc=proc.wait()
   if rc:raise RuntimeError('GCS readback failed: '+err.decode()[-500:])
  finally:
   timer.cancel()
   if proc.poll() is None:expire();proc.wait()
 if size!=expected_bytes:raise ValueError('Truncated object')
 return h.hexdigest()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--apply',action='store_true');ap.add_argument('--evict',action='store_true');a=ap.parse_args()
 if a.evict and not a.apply:ap.error('--evict requires --apply')
 if a.apply:
  policy=json.loads((R/'storage_policy.json').read_text())
  if policy.get('migration_authorized') is not True:ap.error('Migration paused: local storage is active')
  if a.evict and policy.get('local_eviction_authorized') is not True:ap.error('Local eviction is not authorised')
 manifest=R/'migration-receipt.json';receipts=json.loads(manifest.read_text()) if manifest.exists() else []
 plan=[]
 support=[p for p in R.rglob("*") if p.is_file() and p.suffix in (".json",".jsonl",".md",".py",".log") and p.name not in ("migration-plan.json","migration-receipt.json")]
 for p in ALLOWED+support:
  if not p.is_file():continue
  if p.is_symlink():raise ValueError('Refusing symlink payload')
  rel=p.relative_to(ROOT).as_posix(); digest=sha(p); uri=f'{PREFIX}/objects/{digest}/{p.name}'
  item={'local':rel,'bytes':p.stat().st_size,'sha256':digest,'uri':uri,'readback_verified':False,'local_removed':False,'evictable':p in ALLOWED};plan.append(item)
  if not a.apply:continue
  # Generation0 fails closed on object collision; an existing object must still
  # pass independent readback before it can be reused/evicted locally.
  cp=subprocess.run(['gcloud','storage','cp',str(p),uri,'--if-generation-match=0','--quiet'],capture_output=True,text=True,timeout=600)
  if cp.returncode:
   # Never assume a failed copy succeeded. Readback below must prove exact object.
   item['upload_returncode']=cp.returncode
  metadata=json.loads(subprocess.check_output(['gcloud','storage','objects','describe',uri,'--format=json'],text=True,timeout=60))
  versioned_uri=uri+'#'+str(metadata['generation'])
  if readback(versioned_uri,item['bytes'])!=digest:raise ValueError('GCS SHA mismatch')
  item['restore_uri']=versioned_uri
  item.update(readback_verified=True,generation=metadata['generation'],verified_unix=time.time())
  receipts.append(item.copy());tmp=manifest.with_suffix('.tmp');tmp.write_text(json.dumps(receipts,indent=2)+'\n');tmp.replace(manifest)
  if a.evict and item['evictable']:
   if p.is_symlink() or sha(p)!=digest:raise ValueError('Local source changed; refusing eviction')
   p.unlink();receipts[-1]['local_removed']=True;tmp.write_text(json.dumps(receipts,indent=2)+'\n');tmp.replace(manifest)
 (R/'migration-plan.json').write_text(json.dumps({'applied':a.apply,'evict_requested':a.evict,'objects':plan,'bytes':sum(x['bytes'] for x in plan)},indent=2)+'\n')
 print(json.dumps({'objects':len(plan),'bytes':sum(x['bytes'] for x in plan),'applied':a.apply,'evict_requested':a.evict}))
if __name__=='__main__':main()
