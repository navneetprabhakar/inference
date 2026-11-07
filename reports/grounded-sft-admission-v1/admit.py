"""Root admission of three independently verified grounded sources; no GPU."""
import hashlib
import json
from pathlib import Path
import shutil
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ('grounded-chat-aligned-v1', 'grounded-tool-aligned-v2', 'grounded-session-aligned-v2')

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def read(p):
    return json.loads(Path(p).read_bytes())

def require(ok, why):
    if not ok:
        raise ValueError(why)

def main():
    start = time.monotonic()
    prepared = []
    totals = {'train': 0, 'exposed-development': 0}
    def check(d):
        require(time.monotonic()-start < 300, 'admission wall ceiling')
        require(not (ROOT/'runs/STOP').exists() and not (d/'STOP').exists(), 'STOP')
        require(shutil.disk_usage(ROOT).free >= 20*1024**3, 'disk floor')
    for name in SOURCES:
        d = ROOT/'data'/name
        check(d)
        require(not (d/'diagnostic-admission.json').exists(), 'preserve completed admission')
        receipt, freeze = read(d/'receipt.json'), read(d/'freeze.json')
        verification = read(d/'independent-verification.json')
        identity = sha(d/'receipt.json')
        require(verification['state'] == 'PASS' and verification['failures'] == []
                and verification['dataset_sha256'] == identity, 'complete matching independent verification')
        require(receipt['training_admitted'] is False and receipt['counts'] == verification['counts'], 'prepared source counts')
        require(receipt['freeze_sha256'] == sha(d/'freeze.json'), 'frozen identity')
        require(receipt['exclusion_union_count'] == verification['exclusion_union_count'], 'custody union accounting')
        for relative, pin in freeze['pins'].items():
            check(d)
            path = ROOT/relative
            require(path.resolve().is_relative_to(ROOT) and not path.is_symlink(), 'unsafe frozen artifact')
            require(sha(path) == pin, 'frozen preparation artifact changed')
        for absolute, pin in verification['pins'].items():
            check(d)
            path = Path(absolute)
            require(path.resolve().is_relative_to(ROOT) and not path.is_symlink(), 'unsafe verified artifact')
            require(sha(path) == pin, 'independently verified artifact changed')
        for filename, pin in receipt['outputs'].items():
            check(d)
            path = d/filename
            require(path.parent == d and not path.is_symlink(), 'unsafe packed output')
            require(path.stat().st_size == pin['bytes'] and sha(path) == pin['sha256'], 'packed output changed')
        for split in totals:
            totals[split] += receipt['counts'][split]['targets']
        admission = dict(training_admitted=True, scope='bounded_own_base_diagnostic_and_hardware_preflight_only',
            dataset_sha256=identity, source=name, quality_certified=False, launch_authorized=False,
            verification_receipt='independent-verification.json',
            verification_sha256=sha(d/'independent-verification.json'),
            decision_sha256=sha(Path(__file__).with_name('DECISION.md')), code_sha256=sha(__file__),
            source_passes='One pass; fixed activation and fresh hardware preflight required')
        prepared.append((d, admission))
    require(0 < totals['train'] <= 900000 and 0 < totals['exposed-development'] <= 100000, 'combined grounded target ceilings')
    for d, admission in prepared:
        check(d)
        with (d/'diagnostic-admission.json').open('x') as f:
            json.dump(admission, f, indent=2)
            f.write('\n')
    print(json.dumps(dict(state='diagnostic_data_admitted_no_job_launched', sources=list(SOURCES), targets=totals)))

if __name__ == '__main__':
    main()
