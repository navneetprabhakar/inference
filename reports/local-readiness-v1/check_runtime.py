import hashlib,json,subprocess,datetime
from pathlib import Path
from cloud_training.nano_package import verify_module_closure,MODULES,REVISION
P=Path('reports/local-readiness-v1')
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
repo=Path('runs/nanochat-source');assert subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()==REVISION
assert not subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip()
lock=json.loads(Path('reports/l4-qualification-v1/kernel-lock.json').read_text());kernel=[]
for name,expected in lock['files'].items():
 p=Path('runs/l4-kernel')/name;assert p.stat().st_size==expected['bytes'] and sha(p)==expected['sha256'];kernel.append(name)
headers=json.loads(Path('reports/l4-qualification-v1/python-headers-lock.json').read_text())
for item in headers['packages']:
 p=Path('runs/l4-debs')/item['file'];assert sha(p)==item['sha256']
files=[Path('cloud_training')/(m+'.py') for m in MODULES]
files += [Path('tools/__init__.py'),Path('runs/ownbase-v2-data/tokenizer/tokenizer.pkl')]
files+=[p for p in Path('runs/l4-wheels').glob('*.whl')]
report={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'dependency_closure':verify_module_closure('.'),'upstream_revision':REVISION,'upstream_clean':True,'kernel_files_verified':len(kernel),'header_packages_verified':len(headers['packages']),'files':{str(p):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in files},'limitations':['Linux CUDA binaries are hash-verified, not executed on macOS.','Torch/CUDA come from the pinned Deep Learning VM image, not these supplementary wheels.','Old startup/allocator scripts are not approved for this run; provider STOP and persistent-disk preservation must replace DELETE behavior before launch.']}
(P/'runtime-inputs.json').write_text(json.dumps(report,indent=2)+'\n');print('Runtime input hashes and dependency closure passed.')
