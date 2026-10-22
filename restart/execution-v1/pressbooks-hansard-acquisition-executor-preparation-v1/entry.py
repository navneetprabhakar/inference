"""Minimal early-clock launcher; no own acquisition imports before pin checks."""
import time
BOOT_START=time.clock_gettime(time.CLOCK_MONOTONIC)
import signal
import sys


def timeout(signum,frame):raise TimeoutError('shared_deadline_or_signal')


def value(flag,default=None):
    return sys.argv[sys.argv.index(flag)+1] if flag in sys.argv else default


for signum in (signal.SIGALRM,signal.SIGTERM,signal.SIGINT):signal.signal(signum,timeout)
source=value('--source')
if source not in ('pressbooks','uk_hansard'):raise SystemExit('source_required')
worker='--worker' in sys.argv
start=float(value('--start',str(BOOT_START))) if worker else BOOT_START
limit=(1190 if source=='pressbooks' else 7190) if worker else (1200 if source=='pressbooks' else 7200)
if not worker and '--execute' not in sys.argv:limit=120
# Supervisor leaves five seconds inside the unchanged external cap for kill/reap/settlement.
cleanup_reserve=5 if not worker and '--execute' in sys.argv else 0
remaining=limit-cleanup_reserve-(time.clock_gettime(time.CLOCK_MONOTONIC)-start)
if not 0<remaining<=limit:raise SystemExit('invalid_or_expired_shared_start')
signal.setitimer(signal.ITIMER_REAL,remaining)
try:
    import hashlib
    import json
    from pathlib import Path
    here=Path(__file__).resolve().parent
    def sha(path):
        with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    code=value('--code-pins-sha256');profile=value('--profiles-sha256')
    if sha(here/'code-pins.json')!=code or sha(here/'profiles.json')!=profile:raise ValueError('external_pin_mismatch')
    frozen=json.loads((here/'profiles.json').read_text());pins=json.loads((here/'code-pins.json').read_text())['SHA256']
    if set(pins)!=set(frozen['required_inventory']):raise ValueError('exact_inventory_required')
    for path,digest in pins.items():
        p=Path(path)
        if p.is_symlink() or not p.is_file() or sha(p)!=digest:raise ValueError('pinned_input_changed')
    import acquire
    result=acquire.main(start,BOOT_START)
except BaseException as error:
    # No external exception strings/tracebacks can expose signed query URLs.
    print('TERMINAL_LAUNCHER_'+type(error).__name__)
    result=1
finally:signal.setitimer(signal.ITIMER_REAL,0)
raise SystemExit(result)
