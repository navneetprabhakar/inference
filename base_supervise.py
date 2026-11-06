"""Supervise a frozen base_train campaign without changing its identity or budgets.

Run with the same venv Python as the trainer. A launchd LaunchAgent can use
ProgramArguments [absolute-python, absolute-this-file, absolute-spec, absolute-run],
WorkingDirectory set to the repo, RunAtLoad true and KeepAlive false. Configure
absolute StandardOutPath and StandardErrorPath. Supervisor state survives restarts;
terminal supervisor state requires an explicit human review, not KeepAlive retries.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


TERMINAL = {'completed', 'diverged', 'failed', 'stopped', 'budget-exhausted',
            'resource-timeout', 'crash-limit'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, state):
    temporary = path.with_suffix('.tmp')
    with temporary.open('wb') as stream:
        stream.write(canonical(state)); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def ledger(run, spec):
    path = run/'campaign.json'
    if not path.exists():
        return None
    value = json.loads(path.read_bytes())
    receipt = value.pop('sha256')
    if receipt != hashlib.sha256(canonical(value)).hexdigest():
        raise ValueError('campaign ledger checksum mismatch')
    if value['spec']['identity']['protocol'] != spec:
        raise ValueError('campaign protocol differs from frozen supervisor specification')
    return value


def exhausted(record, spec):
    if not record:
        return None
    if time.time()-record['started'] >= spec['calendar_seconds']:
        return 'calendar budget exhausted'
    active = record['active_seconds']
    if record['state'] == 'running':
        active = record['lease_active_base']+record['lease_allowance']
    if active >= spec['active_seconds']:
        return 'active budget exhausted'
    if record['reserved_tokens'] >= spec['target_tokens']:
        return 'attempted target token budget exhausted'
    return None


def supervise(spec_path, run, *, trainer=None, cooldown=60, resource_limit=3600,
              poll_seconds=5, clock_sleep=time.sleep):
    """Private timing/trainer injection supports CPU tests; CLI uses fixed limits."""
    spec_path, run = Path(spec_path).resolve(), Path(run).resolve()
    trainer = Path(trainer or Path(__file__).with_name('base_train.py')).resolve()
    run.parent.mkdir(parents=True, exist_ok=True)
    state_path = run.with_name(run.name+'-supervisor.json')
    lock_path = run.with_name(run.name+'-supervisor.lock')
    lock = lock_path.open('a+')
    # The worker inherits this descriptor. If this supervisor dies, the lock
    # remains held until its worker exits, preventing overlapping supervisors.
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state = None
    worker = None
    interrupted = False
    def on_signal(_number, _frame):
        nonlocal interrupted
        interrupted = True
    old_handlers = {}
    try:
        for number in (signal.SIGINT, signal.SIGTERM):
            old_handlers[number] = signal.signal(number, on_signal)
        spec = json.loads(spec_path.read_bytes())
        if not 0 < spec['lease_seconds'] <= 4*3600:
            raise ValueError('lease must be at most four hours')
        if not 0 < spec['target_tokens'] <= 100_000_000 or not 0 < spec['active_seconds'] <= 36*3600 or not 0 < spec['calendar_seconds'] <= 7*86400:
            raise ValueError('campaign exceeds original ceilings')
        identity = dict(spec=str(spec_path), spec_sha256=digest(spec_path),
                        trainer=str(trainer), trainer_sha256=digest(trainer),
                        python=str(Path(sys.executable).resolve()))
        if state_path.exists():
            state = json.loads(state_path.read_bytes())
            if state['identity'] != identity:
                raise ValueError('supervisor identity changed')
            if state['state'] in TERMINAL:
                return state['state']
        else:
            state = dict(schema=1, identity=identity, state='ready', launches=0,
                         crash_recoveries=0, resource_since=None, reason='', created=time.time())
        def publish(name, reason=''):
            state.update(state=name, reason=reason, updated=time.time())
            write(state_path,state)
        def stopped():
            return (run/'STOP').exists() or (run.parent/'STOP').exists()
        def wait_until(deadline):
            while time.time() < deadline:
                if stopped() or interrupted:
                    return False
                clock_sleep(min(poll_seconds,max(0,deadline-time.time())))
            return True
        def stop_worker():
            if worker is None or worker.poll() is not None:
                return
            worker.send_signal(signal.SIGINT)
            try: worker.wait(timeout=60)
            except subprocess.TimeoutExpired:
                worker.terminate()
                try: worker.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    worker.kill(); worker.wait()
        while True:
            if stopped():
                publish('stopped','explicit STOP');return state['state']
            if interrupted:
                publish('interrupted','supervisor signal');return state['state']
            if digest(spec_path) != identity['spec_sha256'] or digest(trainer) != identity['trainer_sha256']:
                raise ValueError('frozen spec or trainer changed')
            record = ledger(run,spec)
            if record and record['state'] in ('completed','diverged','failed'):
                publish(record['state'],record.get('reason',''));return state['state']
            reason = exhausted(record,spec)
            if reason:
                publish('budget-exhausted',reason);return state['state']
            if record and 'explicit STOP' in record.get('reason',''):
                publish('stopped',record['reason']);return state['state']
            prior = record['state'] if record else None
            if prior == 'paused-resource' or state.get('preflight_resource_pending', False):
                state['resource_since'] = state['resource_since'] or time.time()
                deadline = state['resource_since']+resource_limit
                if time.time()+cooldown > deadline:
                    publish('resource-timeout','resource pause exceeded retry window');return state['state']
                publish('cooldown',record.get('reason','resource pause'))
                if not wait_until(time.time()+cooldown):
                    continue
            elif prior in ('running','interrupted'):
                if state['crash_recoveries'] >= 2:
                    publish('crash-limit','two crash/interruption recoveries already attempted');return state['state']
                state['crash_recoveries'] += 1
            else:
                state['resource_since'] = None
            if run.exists() and record is None:
                raise ValueError('initialization incomplete: no campaign receipt; refusing an unverified restart')
            if stopped() or interrupted:
                continue
            if digest(spec_path) != identity['spec_sha256'] or digest(trainer) != identity['trainer_sha256']:
                raise ValueError('frozen spec or trainer changed during cooldown')
            command = [sys.executable,str(trainer),str(spec_path),str(run)]
            if record:
                command.append('--resume')
            state['launches'] += 1
            state['worker_command'] = command
            log_path = run.with_name(f'{run.name}-worker-{state["launches"]:04}.log')
            state['worker_log'] = str(log_path)
            publish('running','starting bounded training lease')
            with log_path.open('ab') as output:
                worker = subprocess.Popen(command, cwd=trainer.parent, stdin=subprocess.DEVNULL,
                                          stdout=output, stderr=subprocess.STDOUT,
                                          pass_fds=(lock.fileno(),))
                state['worker_pid'] = worker.pid
                publish('running','worker active')
                # A stuck worker must not outlive the lease indefinitely.
                watchdog = time.monotonic()+min(spec['lease_seconds'],spec['active_seconds'])+120
                while worker.poll() is None:
                    if stopped() or interrupted or time.monotonic() >= watchdog:
                        stop_worker()
                        break
                    clock_sleep(poll_seconds)
                state['worker_exit_code'] = worker.wait()
            if stopped() or interrupted:
                publish('stopped' if stopped() else 'interrupted', 'explicit STOP' if stopped() else 'supervisor signal')
                return state['state']
            after = ledger(run,spec)
            if not after:
                raise ValueError('worker exited without a campaign receipt; inspect its log')
            if after['state'] == 'paused-resource' and (prior != 'paused-resource'
                    or after['reserved_tokens'] > record['reserved_tokens']):
                state['resource_since'] = time.time()
            # If preflight fails before a new lease begins, the previous ledger
            # stays intact. Only resource preflight errors qualify for cooldown.
            if state['worker_exit_code'] != 0 and after == record:
                tail = log_path.read_bytes()[-16384:].decode(errors='replace')
                resource_error = any(x in tail for x in ('resource threshold:', 'guard unavailable:'))
                if resource_error:
                    state['preflight_resource_pending'] = True
                    state['resource_since'] = state['resource_since'] or time.time()
                else:
                    state['preflight_resource_pending'] = False
                    if prior not in ('running', 'interrupted'):
                        publish('failed','worker failed before starting a new lease; inspect log');return state['state']
            else:
                state['preflight_resource_pending'] = False
            publish('ready','worker lease ended')
    except BaseException as error:
        if worker is not None and worker.poll() is None:
            worker.terminate()
            try: worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill();worker.wait()
        if state is not None:
            state.update(state='failed',reason=f'{type(error).__name__}: {error}',updated=time.time())
            write(state_path,state)
        raise
    finally:
        for number,handler in old_handlers.items():signal.signal(number,handler)
        lock.close()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec',type=Path)
    parser.add_argument('run',type=Path)
    args=parser.parse_args()
    state=supervise(args.spec,args.run)
    print(state,flush=True)
    raise SystemExit(0 if state=='completed' else 2)
