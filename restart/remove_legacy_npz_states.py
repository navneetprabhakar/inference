"""Remove confirmed legacy NPZ weight/Adam states by inspecting archive names only."""
from pathlib import Path
import zipfile,json,hashlib,shutil
root=Path(__file__).resolve().parents[1];history=root.parent/'inference-history-20261021';removed=[]
for p in history.rglob('*.npz'):
 with zipfile.ZipFile(p) as z:names=z.namelist()
 if any(n.startswith(('weight:','m:','v:')) for n in names):
  assert all(n.startswith(('weight:','m:','v:')) for n in names),p
  removed.append({'original_path':str(p.relative_to(history)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'action':'delete_generated_npz_weight_and_adam_state','members':names})
for r in removed:(history/r['original_path']).unlink()
assert len(removed)==54,len(removed)
(root/'restart/npz-state-deletion.json').write_text(json.dumps(removed,indent=2)+'\n')
p=root/'restart/cleanup-manifest.json';j=json.loads(p.read_text());j['deleted_npz_state_files']=len(removed);j['deleted_npz_state_bytes']=sum(r['bytes'] for r in removed);j['currently_retained_original_files']=j['retained_files_hash_verified']-len(removed);j['remaining_generated_weight_optimizer_npz_states']=0;p.write_text(json.dumps(j,indent=2)+'\n')
# Preserve the original pre-move receipt; append the later disposition as a separate audit event.
shutil.copy2(root/'restart/npz-state-deletion.json',history/'npz-state-deletion.json')
print('Removed',len(removed),'legacy NPZ state files,',j['deleted_npz_state_bytes'],'bytes')
