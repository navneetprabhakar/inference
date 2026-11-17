import ast,json,hashlib,tarfile,tempfile
from pathlib import Path
from cloud_training.nano_package import extract_verified
P=Path(__file__).resolve().parent;ROOT=Path.cwd();runtime=ROOT/'runs/ganesh-a100-cap40-v1/runtime-eager-muon.tar.gz'
for p in P.glob('*.py'):ast.parse(p.read_text())
with tempfile.TemporaryDirectory(dir=ROOT/'runs/ganesh-a100-cap40-v1') as d:
 m=extract_verified(runtime,Path(d).resolve()/'runtime')
 for name,v in m['files'].items():
  if name.startswith('cloud_training/') or name=='ganesh_recovery_task.py':assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==v['sha256']
frozen={}
for folder,filename in [('reports/corrective-corpus-v1','freeze.json'),('reports/english-first-v1','packet-freeze.json'),('reports/ganesh-english-curriculum-v2','freeze.json')]:
 j=json.loads((ROOT/folder/filename).read_text())['files'];assert all(hashlib.sha256((ROOT/folder/n).read_bytes()).hexdigest()==h for n,h in j.items());frozen[folder]=len(j)
w=(P/'gpu_qualify.py').read_text();b=(P/'bootstrap.sh').read_text();cfg=json.loads((P/'config.json').read_text())
checks={'same_VM_no_provisioning':'instances create' not in b,'original_workspace_preserved':"Path('/opt/english-eager')" in w and '[ ! -e /opt/english-eager ]' in b,'original_workers_joined':'flock -n 8' in b and 'flock -n /tmp/ganesh-gpu-writer.lock true' in b,'explicit_eager_mode':"'--muon-kernel-mode','eager'" in w,'selected_replays_match_capture':"replay['eager'][r]['calls']" in w and 'matches_captured_output_exact' in w,'capture_gate_after_replay':w.index('Actual optimizer captures differ')>w.index("'replay-comparison.log'"),'no_budget_or_deadline_extension':cfg['deadline_utc']=='2026-11-18T03:05:59Z' and cfg['qualification_deadline_utc']=='2026-11-17T22:31:13Z' and cfg['worker_deadline_utc']=='2026-11-17T22:01:13Z','no_pilot_autodispatch':cfg['qualification_only'] and not cfg['pilot_authorized_by_worker'],'runtime_readback_before_execution':b.index('sha256sum -c -')<b.index('/usr/bin/python3 -u gpu_qualify.py'),'209_local_tests':'Ran 209 tests' in (P.parent/'eager-mode-tests.log').read_text() and '\nOK\n' in (P.parent/'eager-mode-tests.log').read_text(),'frozen52_unchanged':sum(frozen.values())==52}
assert all(checks.values()),checks
(P/'adverse-checks.json').write_text(json.dumps({'checks':checks,'frozen':frozen,'runtime_sha256':hashlib.sha256(runtime.read_bytes()).hexdigest(),'scope':'Corrective execution path only; must pass full GPU recovery before English fit; no acceptance claim'},indent=2)+'\n');print(json.dumps(checks))
