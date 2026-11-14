"""Reconcile stale per-process journals using current GCS authority, after writers exit."""
import fcntl,hashlib,json,os,subprocess,tarfile,tempfile,time
from pathlib import Path
from cloud_training.nano_checkpoint import validate_bundle
ROOT=Path('/opt/english-repair');OUT=ROOT/'results';config=json.loads((ROOT/'config.json').read_text());REMOTE=config['backup_prefix']
def require(ok,msg):
 if not ok:raise ValueError(msg)
def cp(src,dst):subprocess.run(['gcloud','storage','cp',str(src),str(dst),'--quiet'],check=True,timeout=120)
with Path('/opt/english/worker.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 for name,step in [('uninterrupted',2),('split_first',1),('split_resume',2)]:
  r=json.loads((OUT/name/'result.json').read_text());require(r['step']==step and r['reason']=='pilot_update_limit','Training branch not cleanly complete')
 result=json.loads((OUT/'qualification.json').read_text());require(result['comparison']['status']=='pass','Restart comparison failed')
 journals={};proofs=[];stale=[]
 for path in OUT.glob('*/retention-journal.json'):
  local=json.loads(path.read_text());prefix=local['campaign_prefix'];require(prefix in [REMOTE+'/uninterrupted/checkpoints',REMOTE+'/split/checkpoints'],'Unexpected namespace')
  journals.setdefault(prefix,[]).append(local)
 for index,(prefix,locals_) in enumerate(sorted(journals.items())):
  dst=ROOT/('authoritative-journal-'+str(index)+'.json');cp(prefix+'/retention-journal.json',dst);journal=json.loads(dst.read_text())
  require(journal['lease_phase']=='ready' and journal['campaign_prefix']==prefix,'Unfinished authoritative operation')
  require(all(journal['identity']==x['identity'] for x in locals_),'Journal identity drift')
  require(all(e['state'] in ('committed','deleted') for e in journal['entries']),'Ambiguous retention state')
  current={e['receipt']['remote_prefix'] for e in journal['entries'] if e['state']=='committed'}
  for old in locals_:
   stale.extend(e['receipt']['remote_prefix'] for e in old['entries'] if e['state']=='committed' and e['receipt']['remote_prefix'] not in current)
  for entry in journal['entries']:
   if entry['state']!='committed':continue
   receipt=entry['receipt'];uri=receipt['remote_prefix']
   with tempfile.TemporaryDirectory(prefix='reconcile-',dir=ROOT) as d:
    target=Path(d)
    for n in ('payload.pt','metadata.json','manifest.json','COMMITTED'):cp(uri+'/'+n,target/n)
    require(validate_bundle(target)==receipt['manifest'],'Required bundle differs')
   proofs.append({'uri':uri,'manifest':receipt['manifest'],'independent_readback':True})
 require(len(journals)==2 and len(proofs)>=4,'Missing required branches')
 reconciliation={'status':'pass','basis':'Current remote journals, deduplicated by campaign; stale local snapshots are not authority','stale_local_references':sorted(set(stale)),'required_bundle_readbacks':proofs,'original_failure_preserved':'results/qualification.json','no_active_writer':True}
 (OUT/'backup-reconciliation.json').write_text(json.dumps(reconciliation,indent=2)+'\n')
 archive=ROOT/'evidence-reconciled.tar.gz'
 with tarfile.open(archive,'w:gz') as tar:
  for p in OUT.rglob('*'):
   if p.is_file() and p.name!='payload.pt':tar.add(p,arcname='results/'+str(p.relative_to(OUT)))
  for n in ('config.json','bootstrap.log'):tar.add(ROOT/n,arcname=n)
  for p in ROOT.glob('authoritative-journal-*.json'):tar.add(p,arcname=p.name)
 cp(archive,REMOTE+'/evidence-reconciled.tar.gz');readback=ROOT/'reconciled-readback.tar.gz';cp(REMOTE+'/evidence-reconciled.tar.gz',readback)
 sha=hashlib.sha256(archive.read_bytes()).hexdigest();require(hashlib.sha256(readback.read_bytes()).hexdigest()==sha,'Evidence mismatch')
 closeout=ROOT/'closeout-reconciled.json';closeout.write_text(json.dumps({'evidence_sha256':sha,'evidence_object':'evidence-reconciled.tar.gz','all_required_checkpoint_readbacks':True,'evidence_readback':True,'backup_reconciliation':'pass','original_backup_failure_preserved':True},indent=2)+'\n')
 cp(closeout,REMOTE+'/closeout.json');cp(REMOTE+'/closeout.json',ROOT/'closeout-reconciled-readback.json');require(closeout.read_bytes()==(ROOT/'closeout-reconciled-readback.json').read_bytes(),'Closeout mismatch')
 (ROOT/'reconciliation-stop-ready').write_text('Current authoritative GCS journals and every required bundle verified\n')
 (ROOT/'normal-stop-ready').write_text('Backup failure reconciled; see closeout-reconciled.json; old failure retained\n')
 print(json.dumps({'backup_reconciliation':'pass','required_bundles':len(proofs),'stale_references':len(set(stale))}),flush=True)
 subprocess.run(['shutdown','-h','now'],check=True)
