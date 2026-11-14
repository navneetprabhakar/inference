"""Offline production bundle builder. Never uploads, reserves money, or starts a VM."""
from pathlib import Path, PurePosixPath
import argparse, ast, gzip, hashlib, io, json, subprocess, tarfile

REVISION = '92d63d4e8bb4df75c3b71618f31ddde2378b2bcd'
TOKENIZER_SHA = 'ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'
MODULES = ('nano_train', 'nano_benchmark', 'nano_checkpoint', 'nano_data', 'nano_eval', 'nano_probes',
           'nano_retention', 'l4_recovery_check', 'nano_launch', 'nano_package',
           'campaign_budget', 'runtime', 'nano_campaign', 'nano_sft',
           'nano_serve', 'nano_chat_format', 'nano_quality', 'nano_context',
           'nano_quality_gate', 'nano_fit_contract', 'nano_qualification_schedule', 'nano_corpus_guard', 'nano_restart_compare')

def verify_module_closure(root, modules=MODULES):
    """Fail locally if a packaged adapter imports an omitted project module."""
    required=set(modules);missing=set()
    for module in modules:
        path=Path(root)/'cloud_training'/(module+'.py')
        tree=ast.parse(path.read_text(),filename=str(path))
        for node in ast.walk(tree):
            names=[]
            if isinstance(node,ast.ImportFrom) and node.module:
                if node.module.startswith('cloud_training.'):
                    names=[node.module.split('.')[1]]
                elif node.module=='cloud_training':names=[a.name for a in node.names]
            elif isinstance(node,ast.Import):
                names=[a.name.split('.')[1] for a in node.names if a.name.startswith('cloud_training.')]
            missing.update(name for name in names if name not in required)
    if missing:raise ValueError('Package omits project dependencies: '+', '.join(sorted(missing)))
    return {'modules':len(required),'missing':[]}

def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def relative(name):
    p = PurePosixPath(name)
    if not isinstance(name, str) or not name or p.is_absolute() or '..' in p.parts or str(p) != name or '\\' in name:
        raise ValueError('Canonical relative file path required')
    return p

def extract_verified(archive, destination):
    """Reject links/devices/traversal before extracting a trusted hash-checked bundle."""
    destination = Path(destination)
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers(); names = set()
        for m in members:
            relative(m.name)
            if not m.isfile() or m.name in names: raise ValueError('Only unique regular bundle files allowed')
            names.add(m.name)
            target = destination / m.name
            if any(p.is_symlink() for p in [target, *target.parents]): raise ValueError('Symlink extraction destination')
        tar.extractall(destination, members=members, filter='data')
    manifest = json.loads((destination/'package-manifest.json').read_text())
    if manifest['revision'] != REVISION or manifest['tokenizer_sha256'] != TOKENIZER_SHA:
        raise ValueError('Package identity mismatch')
    if names != set(manifest['files']) | {'package-manifest.json'}: raise ValueError('Unexpected bundle contents')
    for name, meta in manifest['files'].items():
        path = destination/name
        if path.stat().st_size != meta['bytes'] or sha(path) != meta['sha256']: raise ValueError('Package file integrity mismatch: '+name)
    return manifest

def build(root, target):
    root, target = Path(root), Path(target)
    verify_module_closure(root)
    repo = root/'runs/nanochat-source'
    if subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()!=REVISION:
        raise ValueError('Wrong upstream revision')
    if subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip(): raise ValueError('Dirty upstream source')
    if sha(root/'runs/ownbase-v2-data/tokenizer/tokenizer.pkl') != TOKENIZER_SHA: raise ValueError('Wrong final tokenizer')
    files = {}
    for folder, name in [(repo,'nanochat-source'),(root/'runs/l4-wheels','wheels'),
                         (root/'runs/l4-kernel','kernel'),(root/'runs/l4-debs','debs'),
                         (root/'runs/ownbase-v2-data/tokenizer','tokenizer')]:
        if not folder.is_dir(): raise FileNotFoundError(folder)
        for p in sorted(folder.rglob('*')):
            if p.is_symlink(): raise ValueError('No package symlinks')
            if p.is_file() and '__pycache__' not in p.parts: files[name+'/'+p.relative_to(folder).as_posix()] = p
    for name in MODULES: files['cloud_training/'+name+'.py'] = root/'cloud_training'/ (name+'.py')
    files['tools/__init__.py']=root/'tools/__init__.py'
    files['cloud_training/evaluation/conversation-tools-dev.json']=root/'cloud_training/evaluation/conversation-tools-dev.json'
    files['cloud_training/nano_server.sh'] = root/'cloud_training/nano_server.sh'
    for name in ('kernel-lock.json','python-headers-lock.json'): files[name] = root/'reports/l4-qualification-v1'/name
    manifest = {'schema':1,'revision':REVISION,'tokenizer_sha256':TOKENIZER_SHA,
                'files':{n:{'sha256':sha(p),'bytes':p.stat().st_size} for n,p in files.items()}}
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists(): raise FileExistsError('Refuse to overwrite immutable package')
    with target.open('xb') as raw, gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=1) as gz, tarfile.open(fileobj=gz,mode='w') as tar:
        for name,p in sorted(files.items()):
            info=tar.gettarinfo(str(p),arcname=name); info.uid=info.gid=info.mtime=0; info.uname=info.gname=''
            with p.open('rb') as f: tar.addfile(info,f)
        data=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode(); info=tarfile.TarInfo('package-manifest.json'); info.size=len(data); tar.addfile(info,io.BytesIO(data))
    receipt={**manifest,'bundle_sha256':sha(target),'bundle_bytes':target.stat().st_size}
    target.with_suffix(target.suffix+'.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--root',default=str(Path(__file__).resolve().parents[1])); p.add_argument('--output',required=True)
    a=p.parse_args(); r=build(a.root,a.output); print(json.dumps({k:r[k] for k in ('bundle_sha256','bundle_bytes')}))
