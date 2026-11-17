import ast,hashlib,json,tempfile
from pathlib import Path
from cloud_training.nano_package import extract_verified
P=Path('reports/ganesh-a100-cap40-v1');R=Path('runs/ganesh-a100-cap40-v1');ROOT=Path.cwd()
for p in P.glob('*.py'):ast.parse(p.read_text())
with tempfile.TemporaryDirectory(dir=R) as d:
 manifest=extract_verified(R/'runtime.tar.gz',Path(d).resolve()/'runtime')
 for name,entry in manifest['files'].items():
  if name.startswith('cloud_training/') or name=='ganesh_recovery_task.py':
   assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==entry['sha256'],name
frozen={}
for folder,filename in [('reports/corrective-corpus-v1','freeze.json'),('reports/english-first-v1','packet-freeze.json'),('reports/ganesh-english-curriculum-v2','freeze.json')]:
 files=json.loads((ROOT/folder/filename).read_text())['files'];assert all(hashlib.sha256((ROOT/folder/n).read_bytes()).hexdigest()==h for n,h in files.items());frozen[folder]=len(files)
s=(P/'prepare_launch.py').read_text();w=(P/'gpu_qualify.py').read_text();b=(P/'bootstrap.sh').read_text()
checks={'A10040_only':"'--machine-type=a2-highgpu-1g'" in s and "'A100' in torch.cuda.get_device_name(0)" in w and '39*1024**3' in w,'finite_cap40_with_prior_costs':"'cap_usd':40" in s and 'full=hours*(vm+disk)*1.25+8' in s,'bounded_qualification':"config['qualification_deadline_utc']" in w and 'qualification_stop=now+dt.timedelta(hours=2)' in s,'same_vm_retained': 'shutdown -h now' not in b,'fixed_provider_stop': '--instance-termination-action=STOP' in s and '--no-boot-disk-auto-delete' in s,'no_pilot_before_gates': 'qualification_only=True' in s and "sft('fit" not in w,'compiled_exact_and_repeatability': 'matches_captured_output_exact' in w and 'fresh_process_equal' in w,'all_frozen_inputs_unchanged':bool(frozen),'runtime_extracted_current_source_verified':True,'reboot_replay_barrier': b.index('shutdown -h "+$MINUTES"')<b.index('qualification-started'),'backup_readback_before_ready':w.index("assert closeout.read_bytes()==closeout_copy.read_bytes()")<w.index("(ROOT/'normal-stop-ready').write_text")}
assert all(checks.values()),checks
(P/'adverse-checks.json').write_text(json.dumps({'checks':checks,'frozen':frozen,'scope':'local checks only; no live GPU or conversation acceptance'},indent=2)+'\n');print(json.dumps(checks))
