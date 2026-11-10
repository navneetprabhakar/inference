"""Build a pinned offline qualification bundle; no provisioning side effects."""
from pathlib import Path
import hashlib,json,subprocess,tarfile

ROOT=Path(__file__).resolve().parents[1]
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    upstream=ROOT/'runs/nanochat-source'
    revision=subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True).strip()
    assert revision=='92d63d4e8bb4df75c3b71618f31ddde2378b2bcd'
    assert not subprocess.check_output(['git','-C',str(upstream),'status','--porcelain'],text=True).strip()
    mapping={}
    for folder,name in [(upstream,'nanochat-source'),(ROOT/'runs/l4-wheels','wheels'),(ROOT/'runs/l4-kernel','kernel'),(ROOT/'runs/l4-debs','debs'),(ROOT/'runs/l4-data-prep/benchmark-long/train','benchmark-data/train')]:
        for p in sorted(folder.rglob('*')):
            if p.is_file() and '__pycache__' not in p.parts:
                mapping[name+'/'+str(p.relative_to(folder))]=p
    for name in ['nano_benchmark.py','nano_checkpoint.py','nano_data.py','l4_recovery_check.py']:
        p=ROOT/'cloud_training'/name
        if p.exists():mapping['cloud_training/'+name]=p
    for name in ['verify_nano_checkpoint.py','verify_nano_benchmark.py','verify_nano_data.py']:
        mapping[name]=ROOT/name
    mapping['python-headers-lock.json']=ROOT/'reports/l4-qualification-v1/python-headers-lock.json'
    mapping['kernel-lock.json']=ROOT/'reports/l4-qualification-v1/kernel-lock.json'
    receipt={'revision':revision,'files':{n:{'sha256':sha(p),'bytes':p.stat().st_size} for n,p in mapping.items()}}
    target=ROOT/'runs/l4-qualification-bundle.tar.gz'
    with tarfile.open(target,'w:gz',compresslevel=1) as tar:
        for name,p in mapping.items():tar.add(p,arcname=name)
    receipt['bundle_sha256']=sha(target);receipt['bundle_bytes']=target.stat().st_size
    old=ROOT/'reports/l4-qualification-v1/bundle-receipt.json'
    if old.exists():
        import shutil
        prior=json.loads(old.read_text())
        shutil.copyfile(old,ROOT/'reports/l4-qualification-v1'/('bundle-'+prior['bundle_sha256'][:12]+'.json'))
    (ROOT/'reports/l4-qualification-v1/bundle-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'path':str(target),'sha256':receipt['bundle_sha256'],'bytes':receipt['bundle_bytes']}))
if __name__=='__main__':main()
