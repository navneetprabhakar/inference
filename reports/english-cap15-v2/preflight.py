"""Local review and hash checks only; no cloud mutations."""
import ast,hashlib,json,sys,tempfile
from pathlib import Path
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from cloud_training.nano_checkpoint import validate_bundle
from cloud_training.nano_package import extract_verified
P=ROOT/'reports/english-cap15-v2';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
checks={}
for folder,file in [('english-first-v1','packet-freeze.json'),('corrective-corpus-v1','freeze.json')]:
 base=ROOT/'reports'/folder
 for name,h in json.loads((base/file).read_text())['files'].items():assert sha(base/name)==h,name
 checks[folder]='hashes unchanged'
archive=ROOT/'runs/english-local-readiness-v1/runtime-final.tar.gz'
assert sha(archive)=='02ab26a6a7adf03ffba047834f8f40b2b6242f8ef3939c61b79c9e73eae5625e'
with tempfile.TemporaryDirectory() as t:
 m=extract_verified(archive,Path(t).resolve()/'runtime')
 for n,v in m['files'].items():
  if n.startswith('cloud_training/'):assert sha(ROOT/n)==v['sha256'],n
checks['runtime_members_verified']=len(m['files'])
for p in ['runs/local-readiness-v1/base10b','runs/english-a100-v1/local-diagnostic-step2','runs/ownbase-budget50-v1/local-candidates/new-base-2k-8epochs']:
 validate_bundle(ROOT/p);checks[p]='full bundle verified'
# Capture actual worker argv without importing/executing its GPU top level.
worker=(P/'gpu_qualify.py').read_text();tree=ast.parse(worker);fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='sft')
from cloud_training.nano_qualification_schedule import restart_branches
captured=[]
scope={'sys':sys,'os':__import__('os'),'ROOT':Path('/opt/english'),'OUT':Path('/opt/english/results'),'BASE':Path('/opt/english/base'),'PACKET':Path('/opt/english/packet'),'REMOTE':'gs://test/qualification','config':{'base_manifest_sha256':'a'*64,'tokenizer_sha256':'b'*64,'worker_deadline_utc':'2099-01-01T00:00:00Z'},'restart_branches':restart_branches,'run':lambda a,*args:captured.append(a)}
exec(compile(ast.Module(body=[fn],type_ignores=[]),'worker-argv-review','exec'),scope)
for branch in ['uninterrupted','split_first','split_resume','signal','signal_resume']:
 scope['sft'](branch,resume='/verified' if branch in ['split_resume','signal_resume'] else None,signal_test=branch=='signal')
 a=captured[-1]
 for k,v in [('--max-updates','2' if branch=='uninterrupted' else '1'),('--eval-every-updates','1'),('--packing-buffer-size','1'),('--trace-updates','2'),('--seed','103')]:assert a[a.index(k)+1]==v
 assert '--fit-diagnostic' in a and '--deterministic' in a
checks['worker_actual_argv']=captured
checks['limits']='Qualification only, matching cadence1, no fit launch. Signal branch real injector. No threshold relaxation.'
checks['second_pass_findings']=['Old launchers are tied to closed leases and stale runtime: not reused.','Use separate salvage namespace instead of stale branch journals for backup verification.','No automatic fit launch: upload/provider fault gates remain separate.']
checks['bound_files']={str(p.relative_to(ROOT)):sha(p) for p in [P/'gpu_qualify.py',P/'signal_inject.py',P/'bootstrap.sh',P/'PLAN.md']}
(P/'local-preflight.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS frozen41/runtime148/local3bundles/5worker branches')
