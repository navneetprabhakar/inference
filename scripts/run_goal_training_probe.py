"""One-shot, sequential, read-only probes after the existing V19 stage exits."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
GOAL = ROOT / 'runs/eight-hour-improvement-v1'
CONTROL = ROOT / 'runs/eight-hour-improvement-v19'
RUN = ROOT / 'runs/eight-hour-training-probe-v1'
DEADLINE = 1793672065
PYTHON = str(ROOT.parent / 'inference-archive-20261029/.venv/bin/python')


def alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def save(state, **extra):
    value = {'state': state, 'pid': os.getpid(), 'run_dir': str(RUN),
             'deadline_unix': DEADLINE, 'updated_unix': time.time(), **extra}
    tmp = RUN / 'status.tmp'
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(RUN / 'status.json')
    if state != 'waiting_for_V19':
        tmp = GOAL / 'root-active-run.tmp'
        tmp.write_text(json.dumps(value, indent=2) + '\n')
        tmp.replace(GOAL / 'root-active-run.json')


def stopped():
    return (time.time() >= DEADLINE - 1500
            or (GOAL / 'confirmation-started.json').exists()
            or any((p / 'STOP').exists() for p in [GOAL, CONTROL, CONTROL / 'training', RUN]))


def main():
    RUN.mkdir(exist_ok=True)
    with (RUN / '.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (RUN / 'status.json').exists():
            raise RuntimeError('One-shot probe already started; inspect before any recovery')
        save('waiting_for_V19')
        while True:
            if stopped():
                # Do not overwrite the active trainer lease while merely waiting.
                (RUN / 'closed-without-probe.json').write_text(json.dumps({'reason': 'deadline, confirmation or STOP', 'unix': time.time()}))
                return
            state = json.loads((CONTROL / 'stage-status.json').read_text())
            if state['state'] == 'development_decode_ready_for_semantic_review' and not alive(state.get('driver_pid')) and not alive(81671):
                break
            if state['state'] in ['development_decode_failed', 'training_stopped_needs_review']:
                (RUN / 'closed-without-probe.json').write_text(json.dumps({'reason': state['state'], 'unix': time.time()}))
                return
            time.sleep(5)
        lease = json.loads((GOAL / 'root-active-run.json').read_text())
        assert Path(lease['run_dir']).resolve() == CONTROL.resolve()
        for version in [11, 18, 19]:
            if stopped():
                save('probe_stopped_by_guard')
                return
            source = ROOT / f'runs/eight-hour-improvement-v{version}/training'
            if version == 11:
                source = ROOT / json.loads((GOAL / 'best-development-candidate.json').read_text())['checkpoint']
                assert 'eight-hour-improvement-v11/' in str(source)
            output = ROOT / f'runs/eight-hour-improvement-v{version}/evaluation-training-probe'
            cmd = [PYTHON, 'scripts/evaluate_eight_hour_v3.py', '--checkpoint', str(source),
                   '--split', 'development', '--evaluation-root', 'data/eight-hour-training-probe-v1', '--output', str(output)]
            with (RUN / f'v{version}-console.log').open('a') as log:
                child = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
                save('evaluating_SEEN_training_examples_NOT_heldout', candidate=f'V{version}', child_pid=child.pid)
                code = child.wait()
            if code:
                save('probe_failed_needs_review', candidate=f'V{version}', exit_code=code)
                return
        save('training_probe_outputs_ready_for_semantic_review', candidates=['V11', 'V18', 'V19'], limitation='Seen data; not held-out accuracy or selection metric')


if __name__ == '__main__':
    main()
