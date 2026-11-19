"""Replay archived timings offline. Prints a sizing receipt, never runs a trainer."""
import hashlib
import itertools
import json
import math
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
pilot = ROOT / 'reports/ganesh-conversation-pilot-v1'
close = json.loads((HERE / 'closeout.json').read_text())
archive = ROOT / 'runs/ganesh-english-a100-30/closeout-evidence.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == close['independent_backup_readbacks']['evidence']['sha256']
recipe = json.loads((pilot/'pilot-spec.json').read_text())['recipe']
assert recipe['updates_per_arm'] == 40 and recipe['assistant_targets_per_arm'] == 9144
for name, expected in json.loads((pilot/'freeze.json').read_text())['files'].items():
    assert hashlib.sha256((pilot/name).read_bytes()).hexdigest() == expected
with tarfile.open(archive) as tar:
    prefix = 'qualification-v3/continuous/'
    trace = [json.loads(line) for line in tar.extractfile(prefix+'stage-timings.jsonl')]
    journal = json.load(tar.extractfile(prefix+'retention-journal.json'))
assert trace == close['timings']
sec = {(r['stage'],r['step']):r['seconds'] for r in trace}
assert len(sec) == len(trace) and all(v > 0 and math.isfinite(v) for v in sec.values())
checkpoints = {}
for e in journal['entries']:
    r = e['receipt']
    assert e['state'] == 'committed'
    whole = sec['checkpoint',r['step']]
    checkpoints[r['step']] = dict(total=whole, upload_path=r['seconds'], other=whole-r['seconds'])
assert set(checkpoints) == {0,2}
start, cold, warm = sec['startup',0], sec['update',1], sec['update',2]
initial, later = sec['evaluation',0], max(sec['evaluation',1],sec['evaluation',2])
first_save, later_save = sec['checkpoint',0], sec['checkpoint',2]

def replay(best_steps):
    # Timed saves reset the clock at completion. Same-step save requests coalesce.
    elapsed = start + initial + first_save
    last_save = elapsed
    saves = [0]
    for step in range(1,41):
        elapsed += cold if step == 1 else warm
        if step % 5 == 0:
            elapsed += later
        if step in (20,40) or step in best_steps or elapsed-last_save >= 900:
            saves.append(step)
            elapsed += later_save
            last_save = elapsed
    return dict(seconds=elapsed, saves=saves)

optional = (5,10,15,25,30,35)
cases = [replay(set(choice)) for count in range(7) for choice in itertools.combinations(optional,count)]
assert len(cases)==64 and all(set(c['saves']) <= set(range(0,41,5)) for c in cases)
# Retain the operating policy: one additional periodic save, 1.5x on work
# before final save, 600s for final save, 5s deadline offset plus rounding.
before_final = start + cold + 39*warm + 9*max(initial,later) + 9*max(first_save,later_save)
arm_seconds = math.ceil(1.5*before_final + max(600,1.5*later_save)) + 6
old = math.ceil(1.5*(start+40*cold+9*initial+9*first_save)+600)+6
assert old == 5654
minutes = dict(boot=20, qualification=60, broad=math.ceil(arm_seconds/60),
               control=math.ceil(arm_seconds/60), decode=90, backup=35, contingency=20)
lease = sum(minutes.values())
usage = (lease+1)/60*(3.673385+200*0.000136986)
budget = usage*1.25+8
print(json.dumps(dict(old_hold_seconds=old, startup=start, cold_first=cold, warm=warm,
                      checkpoint_seconds=checkpoints, eval_seconds=[initial,later],
                      full_arm_cases=64, fewest=min(cases,key=lambda x:x['seconds']),
                      most=max(cases,key=lambda x:x['seconds']), arm_guard_seconds=arm_seconds,
                      stage_minutes=minutes, provider_minutes=lease, compute_disk_usd=usage,
                      with_reserves_usd=budget, minimum_integer_cap_usd=math.ceil(budget)),indent=2))
