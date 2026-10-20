"""One bounded serial local handoff after the existing full grouping succeeds."""
# Creator: Navneet Prabhakar
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import time
from slm.data.stream_hash import sha

OUT = Path('data/english-local-continuation-v1')
GROUP = Path('data/global-prefix-grouping-v2')
STEPS = [
    ('components', ['scripts/finalize-prefix-components.py'], 600),
    ('corpus', ['scripts/prepare-english-corpus.py'], 1800),
    ('freeze', ['scripts/freeze-english-experiment.py'], 600),
    ('baseline', ['scripts/run-english-learning.py', 'baseline'], 1800),
    ('common', ['scripts/run-english-learning.py', 'common'], 4500),
    ('mlx', ['scripts/run-english-learning.py', 'mlx'], 4500),
    ('package', ['scripts/package-english-cloud.py'], 1800),
]


def save(path, value):
    path = Path(path); temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def check_inputs(plan):
    for name, expected in plan['inputs'].items():
        if sha(name) != expected:
            raise ValueError('Frozen local handoff input differs: ' + name)


def ready(terminal, report):
    return (terminal == dict(complete=True, returncode=0)
            and report.get('complete') is True
            and report.get('full_population') is True
            and report.get('source_records') == 235779)


def run_step(name, args, seconds, plan):
    check_inputs(plan)
    if shutil.disk_usage(OUT).free < 40*1024**3:
        raise ValueError('Local handoff free-disk reserve')
    deadline = min(plan['deadline_unix'], time.time() + seconds)
    if time.time() >= deadline:
        raise TimeoutError('Finite local handoff deadline')
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(Path('src').resolve())
    with (OUT / (name + '.log')).open('xb') as output:
        child = subprocess.Popen([sys.executable, *args], stdout=output, stderr=subprocess.STDOUT,
                                 env=environment, start_new_session=True)
        save(OUT/'progress.json', dict(phase=name, child=child.pid, deadline_unix=deadline))
        try:
            while child.poll() is None:
                if time.time() >= deadline:
                    raise TimeoutError('Local phase deadline: ' + name)
                if shutil.disk_usage(OUT).free < 40*1024**3:
                    raise ValueError('Local free-disk reserve during ' + name)
                time.sleep(2)
            if child.returncode:
                raise RuntimeError('Local phase failed: ' + name)
        finally:
            if child.poll() is None:
                os.killpg(child.pid, signal.SIGKILL); child.wait()
            save(OUT/(name+'-terminal.json'), dict(complete=child.returncode == 0,
                                                  returncode=child.returncode))


def main():
    plan = json.loads(Path('configs/english-local-continuation-v1.json').read_text())
    if plan['steps'] != [[name, args, seconds] for name, args, seconds in STEPS]:
        raise ValueError('Reviewed serial local steps differ')
    check_inputs(plan)
    if OUT.exists():
        raise FileExistsError('Retain original local handoff; no automatic retry')
    for forbidden in ['data/english-global-components-v1', 'data/english-recovery-corpus-v1',
                      'data/english-recovery-experiment-v1', 'data/english-training-cloud-package-v1']:
        if Path(forbidden).exists():
            raise FileExistsError('A downstream phase already exists: ' + forbidden)
    OUT.mkdir()
    shutil.copyfile(__file__, OUT/'executed-controller.py')
    shutil.copyfile('configs/english-local-continuation-v1.json', OUT/'plan.json')
    save(OUT/'process.json', dict(parent=os.getpid(), deadline_unix=plan['deadline_unix']))
    try:
        save(OUT/'progress.json', dict(phase='waiting-for-existing-grouping', owns_grouping=False))
        while not (GROUP/'supervisor-terminal.json').exists():
            if time.time() >= plan['grouping_deadline_unix'] + 15:
                raise TimeoutError('Existing full join terminal evidence absent by its deadline')
            time.sleep(2)
        terminal = json.loads((GROUP/'supervisor-terminal.json').read_text())
        report = json.loads((GROUP/'report.json').read_text()) if (GROUP/'report.json').exists() else {}
        if not ready(terminal, report):
            raise ValueError('Complete authoritative full grouping failed; no preparation or gradients')
        for name, args, seconds in STEPS:
            run_step(name, args, seconds, plan)
        save(OUT/'supervisor-terminal.json', dict(complete=True, returncode=0,
                                                cloud_resources_created=0, teacher_calls=0,
                                                scope='Local handoff only; actual CUDA/main training/100-conversation assessment remain'))
    except BaseException as error:
        save(OUT/'supervisor-terminal.json', dict(complete=False, error_type=type(error).__name__,
                                                message=str(error)[:1000], no_automatic_retry=True))
        raise


if __name__ == '__main__':
    main()
