"""Extend the sealed proof package with explicit uniform-main policy/code/data."""
# Creator: Navneet Prabhakar
import json,tarfile
from pathlib import Path
from slm.data.stream_hash import sha
from slm.data.english_corpus import save


def main():
    old=Path('data/english-training-cloud-package-v2');out=Path('data/english-training-cloud-package-v3')
    if out.exists():raise FileExistsError('Preserve prior combined package')
    m=json.loads((old/'manifest.json').read_text());files={Path(p) for p in m['files']}
    for p,h in m['files'].items():
        if sha(p)!=h:raise ValueError('Sealed proof package input changed: '+p)
    additions=['configs/english-uniform-main-policy-v3.json','src/slm/english_budget_v3.py',
               'src/slm/english_main_v3.py','scripts/freeze-uniform-main-v3.py','scripts/run-uniform-main-v3.py',
               'scripts/english-cloud-proof-v3.sh','scripts/english-cloud-pipeline-v3.sh',
               'scripts/prepare-uniform-english-main-v3.py','reports/english-uniform-main-budget-tests-v3.xml']
    files.update(Path(p) for p in additions)
    files.update(p for p in Path('data/english-uniform-language-v3').rglob('*') if p.is_file())
    for p in files:
        if p.is_absolute() or p.is_symlink() or not p.is_file():raise ValueError('Regular relative explicit package inputs required')
    total=sum(p.stat().st_size for p in files)
    if total>12*1024**3:raise ValueError('Combined project byte cap')
    m.update(files={str(p):sha(p) for p in sorted(files)},total_project_bytes=total,
             uniform_main_policy_sha256=sha('configs/english-uniform-main-policy-v3.json'),
             scope='Sealed corrected proof inputs plus explicit uniform main policy/runtime and metadata; no new raw source/auth/teacher/API/Git data')
    out.mkdir();save(out/'manifest.json',m)
    with tarfile.open(out/'inputs.tar.gz','w:gz',compresslevel=1) as tar:
        for p in sorted(files):tar.add(p,arcname='project/'+str(p),recursive=False)
        for name,h in m['wheels'].items():
            p=Path('data/english-training-cloud-preflight-v1/wheels')/name
            if sha(p)!=h:raise ValueError('Pinned offline wheel differs')
            tar.add(p,arcname='wheels/'+name,recursive=False)
        tar.add(out/'manifest.json',arcname='manifest.json',recursive=False)
    if (out/'inputs.tar.gz').stat().st_size>8*1024**3:raise ValueError('Combined archive byte cap')
    save(out/'receipt.json',dict(creator='Navneet Prabhakar',complete=True,plan_sha256=m['plan_sha256'],
         uniform_main_policy_sha256=m['uniform_main_policy_sha256'],archive_sha256=sha(out/'inputs.tar.gz'),
         archive_bytes=(out/'inputs.tar.gz').stat().st_size,project_files=len(files),wheel_files=len(m['wheels']),
         cloud_resources_created=0))
    print((out/'receipt.json').read_text())


if __name__=='__main__':main()
