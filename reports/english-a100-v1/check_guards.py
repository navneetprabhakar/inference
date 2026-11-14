"""Execute launcher guards against tampered copies; never calls cloud tools."""
import json,runpy,shutil,tempfile
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).parent
checks=[]
for case in ('closed','over_cap','wrong_request','unverified_inputs'):
 with tempfile.TemporaryDirectory() as d:
  t=Path(d)
  for n in ('execute_lease.py','launch-request.json','spend-ledger.json','bootstrap.sh','input-backup-receipt.json'):shutil.copy(P/n,t/n)
  ledger=json.loads((t/'spend-ledger.json').read_text())
  if case=='closed':ledger['allocations'][-1]['state']='closed'
  if case=='over_cap':ledger['allocations'][-1]['reserved_compute_usd']=7
  if case=='wrong_request':ledger['allocations'][-1]['request_sha256']='bad'
  if case=='unverified_inputs':
   proof=json.loads((t/'input-backup-receipt.json').read_text());proof['all_verified']=False;(t/'input-backup-receipt.json').write_text(json.dumps(proof))
  (t/'spend-ledger.json').write_text(json.dumps(ledger))
  with patch('subprocess.check_output',side_effect=RuntimeError('Unexpected cloud call')),patch('subprocess.run',side_effect=RuntimeError('Unexpected create')):
   try:runpy.run_path(str(t/'execute_lease.py'));raise RuntimeError('Guard failed open')
   except ValueError as e:checks.append({'case':case,'blocked':True,'reason':str(e)})
r=json.loads((P/'launch-request.json').read_text());a=r['create_argv']
assert r['compute_envelope_usd']+3.5<=10 and r['max_runtime_seconds']==4500
assert '--instance-termination-action=STOP' in a and '--no-boot-disk-auto-delete' in a and '--machine-type=a2-highgpu-1g' in a
assert '--termination-time='+r['latest_local_stop_utc'] in a
(P/'guard-checks.json').write_text(json.dumps(checks,indent=2)+'\n');print('4 fail-closed checks and bounded request checks passed')
