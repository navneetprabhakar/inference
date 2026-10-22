"""Owner-authorized exact local cleanup. No cloud, trainer, or broad data deletion."""
from pathlib import Path
import json,hashlib,shutil,tarfile,os,datetime
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'restart';HISTORY=ROOT.parent/'inference-history-20261021'
assert (OUT/'data-census.json').is_file(),'Content inspection must finish before paths move'
assert not HISTORY.exists(),'Never overwrite prior history'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
roots=['data','checkpoints','configs','docs','reports']
files=[p for name in roots for p in (ROOT/name).rglob('*') if p.is_file() and not p.is_symlink()]
files.append(ROOT/'README.md');deleted=[];retained=[]
HISTORY.mkdir();inventory=OUT/'cleanup-files.jsonl'
with inventory.open('x') as log:
 for p in sorted(files):
  rel=str(p.relative_to(ROOT));delete=p.suffix=='.safetensors'
  rec={'original_path':rel,'bytes':p.stat().st_size,'sha256':sha(p),'action':'delete_generated_tensor' if delete else 'retain_in_history'}
  log.write(json.dumps(rec)+'\n')
  if delete:deleted.append(rec)
  else:retained.append(rec)
  if len(deleted)+len(retained) in [1000,3000,5000]:print('hashed',len(deleted)+len(retained),flush=True)
# Entire .safetensors set was inspected: model, optimizer, expected-step and context-probe outputs.
for r in deleted:(ROOT/r['original_path']).unlink()
print('deleted',len(deleted),'tensor files',flush=True)
# Remove embedded weights from disposable launch archives while preserving every other regular member.
packages=[]
for p in sorted((ROOT/'data').glob('english-training-cloud-package-*/inputs.tar.gz')):
 dest=HISTORY/'unpacked-launch-packages'/p.parent.name;dest.mkdir(parents=True)
 removed=[];kept=[]
 with tarfile.open(p,'r:gz') as archive:
  for m in archive:
   target=dest/m.name
   if m.isdir():continue
   assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts,(p,m.name)
   if m.name.endswith('.safetensors'):
    removed.append({'member':m.name,'bytes':m.size});continue
   target.parent.mkdir(parents=True,exist_ok=True)
   with archive.extractfile(m) as src,target.open('xb') as out:shutil.copyfileobj(src,out,8*1024*1024)
   kept.append({'member':m.name,'bytes':target.stat().st_size,'sha256':sha(target)})
 record={'original_path':str(p.relative_to(ROOT)),'archive_sha256':sha(p),'archive_bytes':p.stat().st_size,'deleted_embedded_tensors':removed,'preserved_members':kept}
 packages.append(record);p.unlink()
 print('retired launch package',p.parent.name,flush=True)
# Rename on same volume; preserve SQLite databases AND journals, all source payloads and receipts.
for name in roots:os.rename(ROOT/name,HISTORY/name)
os.rename(ROOT/'README.md',HISTORY/'README.previous.md')
# Verify retained content after relocation, excluding archives replaced by expanded non-weight members.
archive_paths={x['original_path'] for x in packages};verified=0
for r in retained:
 if r['original_path'] in archive_paths:continue
 p=HISTORY/('README.previous.md' if r['original_path']=='README.md' else r['original_path'])
 assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],p
 verified+=1
remaining=list(HISTORY.rglob('*.safetensors'))+list((ROOT/'restart').rglob('*.safetensors'))
assert not remaining,remaining
manifest={'date':'2026-10-21','owner':'Navneet Prabhakar','history_root':str(HISTORY),'deleted_tensor_files':len(deleted),'deleted_tensor_bytes':sum(x['bytes'] for x in deleted),'retained_files_hash_verified':verified,'retained_file_bytes_before_archive_expansion':sum(x['bytes'] for x in retained),'retired_launch_archives':packages,'historical_budgets_reset':False,'old_authorizations_reusable':False,'cloud_accessed':False,'training_updates':0,'weights_initialized':False,'remaining_safetensors_in_project_and_history':0,'retention':'All original datasets, raw response caches, derived datasets/indexes of uncertain future value, evaluation materials, tokenizer assets, configs, reports, budget/charge/exposure SQLite databases and journals preserved. Only identified generated tensors and weight-containing launch archive containers removed; all other archive members preserved.'}
(OUT/'cleanup-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');shutil.copy2(inventory,HISTORY/inventory.name)
print(json.dumps({k:v for k,v in manifest.items() if k!='retired_launch_archives'},indent=2),flush=True)
