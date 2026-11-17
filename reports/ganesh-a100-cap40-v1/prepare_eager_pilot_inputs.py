import json,shutil,hashlib,ast
from pathlib import Path
P=Path(__file__).resolve().parent;D=P/'pilot-inputs-eager';D.mkdir(exist_ok=True)
for name in ('controller-template.json','price-catalog.json'):shutil.copy(P/'pilot-inputs-v2'/name,D/name)
shutil.copy(P/'prepare_pilot_on_vm.py',D/'prepare_pilot_on_vm.py');ast.parse((D/'prepare_pilot_on_vm.py').read_text())
c=json.loads((P/'pilot-inputs-v2/controls.json').read_text());c['runtime_sha256']='3413ab059fe05ebb301f3021737ad1f960a5e625bc34e6be385013775702b55b';c.pop('qualification_runtime_sha256');c.pop('recovery_gate_sha256')
c['changed_source_hashes']={n:hashlib.sha256(Path(n).read_bytes()).hexdigest() for n in ('cloud_training/nano_recovery_gate.py','cloud_training/nano_recovery_tasks.py','cloud_training/nano_sft.py')}
c['price_checked_utc']=json.loads((P/'attempts/us-central1-c-203102/price_quote-receipt.json').read_text())['checked_utc'];(D/'controls.json').write_text(json.dumps(c,indent=2)+'\n')
b=json.loads((P/'eager-qualification/readback.json').read_text());
for i in b['inputs']:i['independent_readback']=True
(D/'input-backups.json').write_text(json.dumps(b,indent=2)+'\n')
print('Prepared inert pilot input files; actual qualification and fresh inventory still required')
