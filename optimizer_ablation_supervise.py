"""Sequential, bounded optimizer screen; completion is not a model-quality verdict.

CLI: python optimizer_ablation_supervise.py EXPERIMENT.json STATE_DIRECTORY
Only the parent receipt is substituted into frozen arm templates. No foundation
files are modified. A caller must freeze source/template/protocol hashes first.
"""
import argparse
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

TERMINAL = {'completed', 'failed', 'stopped', 'parent-rejected', 'budget-exhausted',
            'resource-timeout', 'crash-limit', 'diverged'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def atomic(path, value):
    temp = path.with_suffix('.tmp')
    with temp.open('wb') as stream:
        stream.write(canonical(value)); stream.flush(); os.fsync(stream.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def signed_read(path):
    value = json.loads(Path(path).read_bytes())
    signature = value.pop('sha256')
    if signature != hashlib.sha256(canonical(value)).hexdigest():
        raise ValueError(f'checksum mismatch: {path}')
    return value


def signed_write(path, value):
    atomic(path, dict(value, sha256=hashlib.sha256(canonical(value)).hexdigest()))


def validate_spec(spec):
    if spec.get('schema') != 1 or len(spec['arms']) != 3:
        raise ValueError('expected schema 1 and exactly three arms')
    for field, maximum in [('active_seconds', 30*3600), ('calendar_seconds', 7*86400),
                           ('target_tokens', 60_000_000)]:
        value = spec[field]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= maximum:
            raise ValueError(f'invalid aggregate {field}')
    if spec['parent']['required_trained_tokens'] != 99_999_744:
        raise ValueError('parent must reach the complete frozen 100M endpoint')
    if len({a['name'] for a in spec['arms']}) != 3 or len({str(Path(a['run']).resolve()) for a in spec['arms']}) != 3:
        raise ValueError('arm names and runs must be distinct')
    totals = dict(active_seconds=0, target_tokens=0)
    for arm in spec['arms']:
        if digest(arm['template']) != arm['template_sha256']:
            raise ValueError('arm template changed')
        template = json.loads(Path(arm['template']).read_bytes())
        if template.get('parent') not in (None, {}):
            raise ValueError('template must not contain a speculative parent receipt')
        for field, maximum in [('active_seconds', 10*3600), ('target_tokens', 20_000_000),
                               ('lease_seconds', 4*3600), ('calendar_seconds', 7*86400)]:
            value = template[field]
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= maximum:
                raise ValueError(f'invalid arm {field}')
        for field in totals: totals[field] += template[field]
        if Path(arm['run']).resolve().parent != Path(spec['parent']['run']).resolve().parent:
            raise ValueError('all arms must share the foundation GPU lock directory')
        if Path(arm['run']).resolve() == Path(spec['parent']['run']).resolve():
            raise ValueError('arm cannot overwrite foundation')
    if any(totals[key] > spec[key] for key in totals):
        raise ValueError('arm budgets exceed aggregate ceiling')


def verify_frozen(spec):
    if digest(spec['parent']['spec']) != spec['parent']['spec_sha256']:
        raise ValueError('foundation budget changed')
    if digest(spec['protocol_path']) != spec['protocol_sha256']:
        raise ValueError('experiment protocol changed')
    for file, expected in spec['code_sha256'].items():
        if digest(file) != expected:
            raise ValueError(f'frozen implementation changed: {file}')
    for arm in spec['arms']:
        if digest(arm['template']) != arm['template_sha256']:
            raise ValueError('arm template changed')


def parent_record(spec):
    parent = spec['parent']; run = Path(parent['run'])
    record = signed_read(run/'campaign.json')
    original = json.loads(Path(parent['spec']).read_bytes())
    if record['spec']['identity']['protocol'] != original:
        raise ValueError('foundation ledger differs from frozen budget')
    if json.loads((run/'campaign-spec.json').read_bytes()) != record['spec']:
        raise ValueError('foundation immutable specification mismatch')
    for file, expected in original['code_sha256'].items():
        if digest(file) != expected: raise ValueError('foundation source changed')
    return record


def completed_parent(spec, record):
    """Verify durable endpoint and bytes without allocating a model or GPU."""
    run = Path(spec['parent']['run'])
    required = spec['parent']['required_trained_tokens']
    if (record['state'] != 'completed' or record['trained_tokens'] != required
            or record['reserved_tokens'] != required):
        raise ValueError('foundation did not complete the required exact endpoint')
    lock = (run/'.checkpoint.lock').open('a+b')
    try:
        fcntl.flock(lock, fcntl.LOCK_SH)
        if record != parent_record(spec): raise ValueError('foundation ledger changed')
        entry = record['checkpoints'][0]
        name = entry['file']
        if Path(name).name != name or not name.endswith('.pt'):
            raise ValueError('unsafe foundation checkpoint filename')
        if json.loads((run/'latest.json').read_bytes())[0] != entry:
            raise ValueError('foundation checkpoint publication incomplete')
        if name not in json.loads((run/'protected.json').read_bytes()):
            raise ValueError('foundation endpoint is not protected')
        file = run/name
        if file.is_symlink() or file.stat().st_size != entry['bytes'] or digest(file) != entry['sha256']:
            raise ValueError('foundation checkpoint bytes differ')
        return dict(run=str(run.resolve()), checkpoint=name, sha256=entry['sha256'], bytes=entry['bytes'],
                    campaign_spec_sha256=digest(run/'campaign-spec.json'), ledger_sha256=digest(run/'campaign.json'))
    finally: lock.close()


def gpu_available(run):
    with (Path(run).parent/'mps.lock').open('a+b') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: return False
        return True


def foundation_supervisor_record(spec):
    """Read the original supervisor's identity before trusting recovery metadata."""
    run = Path(spec['parent']['run'])
    value = json.loads(run.with_name(run.name+'-supervisor.json').read_bytes())
    original = json.loads(Path(spec['parent']['spec']).read_bytes())
    ident = value['identity']
    expected_trainer = Path(__file__).with_name('base_train.py').resolve()
    if (Path(ident['spec']).resolve() != Path(spec['parent']['spec']).resolve()
            or Path(ident['trainer']).resolve() != expected_trainer
            or ident['spec_sha256'] != spec['parent']['spec_sha256']
            or ident['trainer_sha256'] != original['code_sha256'].get(str(expected_trainer),
                                                       original['code_sha256'].get('base_train.py'))):
        raise ValueError('foundation supervisor identity mismatch')
    return value


def foundation_supervisor_ready(spec, value=None):
    value = foundation_supervisor_record(spec) if value is None else value
    if value['state'] == 'completed': return gpu_available(spec['parent']['run'])
    if value['state'] in ('running','ready','cooldown'): return False
    raise ValueError('foundation supervisor did not complete successfully')


def parent_wait_reason(record, supervisor, status, *, resource_limit=3600., now=None):
    """Admit bounded recovery without mistaking a paused worker for a dead run.

    Running workers update status, not their supervisor's launch timestamp.
    Cooldown/relaunch activity updates the supervisor, not the paused worker.
    Neither a stale worker nor an old 'running' supervisor label is sufficient.
    """
    now = time.time() if now is None else now

    def fresh(timestamp):
        return (type(timestamp) in (int, float) and math.isfinite(timestamp)
                and -60 <= now-timestamp <= 600)

    if record['state'] not in ('running', 'paused-lease', 'paused-resource', 'interrupted'):
        raise ValueError('foundation is '+record['state'])
    state = supervisor.get('state')
    if state not in ('running', 'ready', 'cooldown'):
        raise ValueError('foundation supervisor is '+str(state)+'; recovery is not active')
    if state == 'cooldown':
        since = supervisor.get('resource_since')
        if type(since) not in (int, float) or not math.isfinite(since) or since > now+60:
            raise ValueError('foundation cooldown lacks a valid original start time')
        if now-since >= resource_limit:
            raise TimeoutError('foundation resource recovery exceeded retry window')
        if not fresh(supervisor.get('updated')):
            raise ValueError('foundation cooldown supervisor heartbeat stale')
        return 'foundation resource cooldown active; waiting within original retry window'
    if fresh(status.get('timestamp')):
        return 'foundation worker active or entering bounded recovery'
    if fresh(supervisor.get('updated')):
        return 'foundation supervisor recently launched or prepared recovery'
    raise ValueError('foundation worker and recovery supervisor heartbeats stale; manual review required')


def arm_record(run, template):
    path = Path(run)/'campaign.json'
    if not path.exists(): return None
    value = signed_read(path)
    if value['spec']['identity']['protocol'] != template:
        raise ValueError('arm ledger protocol changed')
    if json.loads((Path(run)/'campaign-spec.json').read_bytes()) != value['spec']:
        raise ValueError('arm immutable specification mismatch')
    return value


def charged_active(record):
    if not record: return 0.
    return (record['lease_active_base'] + record['lease_allowance']
            if record['state'] == 'running' else record['active_seconds'])


def disk_reserve(spec, records, parent_bytes):
    """Additional bytes needed beyond actual existing usage and the 20GiB floor."""
    estimate = (11*parent_bytes + 9)//10 + 16*1024**2
    remaining = estimate + 256*1024**2  # One atomic save plus logs/data.
    for planned, existing in zip(spec['arms'], records):
        if existing and existing['state'] == 'completed':
            continue  # Retained bytes already reduce actual free disk.
        allocated = sum(p.stat().st_size for p in Path(planned['run']).glob('*.pt'))
        # Orphans cannot credit another arm's future rolling pair.
        remaining += max(0, 2*estimate - min(allocated, 2*estimate))
    return remaining


def supervise(spec_path, directory, *, trainer=None, parent_verifier=None, reporter=None,
              poll_seconds=5., cooldown=60., resource_limit=3600., disk_free=None):
    """Injection points are CPU-test-only; CLI uses real guards and trainer."""
    spec_path, directory = Path(spec_path).resolve(), Path(directory).resolve()
    trainer = Path(trainer or Path(__file__).with_name('optimizer_ablation_train.py')).resolve()
    reporter = Path(reporter or Path(__file__).with_name('optimizer_ablation_report.py')).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    lock = (directory/'supervisor.lock').open('a+b')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    state_path = directory/'supervisor.json'
    state = None; worker = None; interrupted = False
    handlers = {}
    def signal_received(_number, _frame):
        nonlocal interrupted
        interrupted = True
    try:
        for number in (signal.SIGINT, signal.SIGTERM):
            handlers[number] = signal.signal(number, signal_received)
        spec = json.loads(spec_path.read_bytes()); validate_spec(spec); verify_frozen(spec)
        identity = dict(spec=str(spec_path), spec_sha256=digest(spec_path), trainer=str(trainer),
                        trainer_sha256=digest(trainer), reporter=str(reporter), reporter_sha256=digest(reporter), python=str(Path(sys.executable).resolve()))
        if state_path.exists():
            state = signed_read(state_path)
            if state['identity'] != identity: raise ValueError('supervisor identity changed')
            if state['state'] in TERMINAL: return state['state']
        else:
            state = dict(schema=1, identity=identity, created=time.time(), state='prepared',
                         reason='', parent=None, arms=[dict(launches=0, crashes=0, resource_since=None,
                         materialized_sha256=None, preflight_resource=False) for _ in spec['arms']])
        def publish(name, reason=''):
            state.update(state=name, reason=reason, updated=time.time())
            signed_write(state_path, state)
        def stop_requested():
            paths = [directory/'STOP', directory.parent/'STOP', Path(spec['parent']['run'])/'STOP',
                     Path(spec['parent']['run']).parent/'STOP']
            paths += [Path(a['run'])/'STOP' for a in spec['arms']]
            return any(p.exists() for p in paths)
        def calendar_exhausted(): return time.time()-state['created'] >= spec['calendar_seconds']
        def wait(seconds):
            deadline = time.monotonic()+seconds
            while time.monotonic() < deadline:
                if stop_requested() or interrupted or calendar_exhausted(): return
                time.sleep(min(poll_seconds, deadline-time.monotonic()))
        def stop_worker():
            if worker is not None and worker.poll() is None:
                worker.send_signal(signal.SIGINT)
                try: worker.wait(timeout=60)
                except subprocess.TimeoutExpired:
                    worker.terminate()
                    try: worker.wait(timeout=10)
                    except subprocess.TimeoutExpired: worker.kill(); worker.wait()
        def check_control():
            if stop_requested(): publish('stopped', 'explicit STOP'); return True
            if interrupted: publish('interrupted', 'supervisor signal'); return True
            if calendar_exhausted(): publish('budget-exhausted', 'aggregate calendar budget exhausted'); return True
            if (digest(spec_path) != identity['spec_sha256'] or digest(trainer) != identity['trainer_sha256']
                    or digest(reporter) != identity['reporter_sha256']):
                raise ValueError('frozen supervisor input changed')
            verify_frozen(spec)
            return False
        publish(state['state'], state['reason'])
        while state['parent'] is None:
            if check_control(): return state['state']
            record = parent_record(spec)
            try: supervision = foundation_supervisor_record(spec)
            except (ValueError, KeyError) as error:
                publish('parent-rejected', str(error)); return state['state']
            # The worker can publish completion between our ledger and supervisor
            # reads. Reconcile that one-way transition before calling it invalid.
            if supervision['state'] == 'completed' and record['state'] != 'completed':
                record = parent_record(spec)
            if record['state'] == 'completed':
                try: ready = foundation_supervisor_ready(spec, supervision)
                except ValueError as error:
                    publish('parent-rejected', str(error)); return state['state']
                if not ready:
                    state['parent_resource_since'] = state.get('parent_resource_since') or time.time()
                    if time.time()-state['parent_resource_since'] >= resource_limit:
                        publish('resource-timeout','foundation finalization/GPU lock wait exceeded retry window'); return state['state']
                    publish('waiting-parent', 'waiting for foundation worker to exit and release GPU lock')
                    wait(min(60., poll_seconds)); continue
                try: state['parent'] = completed_parent(spec, record)
                except ValueError as error: publish('parent-rejected', str(error)); return state['state']
                publish('parent-verified', 'exact protected foundation endpoint verified')
                break
            status = json.loads((Path(spec['parent']['run'])/'status.json').read_bytes())
            try: reason = parent_wait_reason(record, supervision, status, resource_limit=resource_limit)
            except TimeoutError as error:
                publish('resource-timeout', str(error)); return state['state']
            except ValueError as error:
                publish('parent-rejected', str(error)); return state['state']
            publish('waiting-parent', reason+'; no ablation worker launched')
            wait(min(60., poll_seconds))
        materialized = []
        for index, arm in enumerate(spec['arms']):
            template = json.loads(Path(arm['template']).read_bytes()); template['parent'] = state['parent']
            target = directory/f'arm-{index+1}.json'
            expected = hashlib.sha256(canonical(template)).hexdigest()
            saved = state['arms'][index]['materialized_sha256']
            if target.exists():
                if digest(target) != expected or saved not in (None, expected):
                    raise ValueError('materialized arm identity changed')
            else: atomic(target, template)
            state['arms'][index]['materialized_sha256'] = expected
            materialized.append((target, template))
        publish('ready', 'arm specifications bound to verified own parent')
        for index, arm in enumerate(spec['arms']):
            run = Path(arm['run']); record_state = state['arms'][index]
            arm_path, template = materialized[index]
            while True:
                if check_control(): return state['state']
                if digest(Path(spec['parent']['run'])/'campaign.json') != state['parent']['ledger_sha256']:
                    raise ValueError('accepted parent ledger changed')
                records = [arm_record(a['run'], t[1]) for a,t in zip(spec['arms'], materialized)]
                record = records[index]
                active = sum(charged_active(r) for r in records)
                attempted = sum(r['reserved_tokens'] if r else 0 for r in records)
                state.update(arm=index, active_seconds=active, reserved_tokens=attempted)
                if record and record['state'] in ('completed','failed','diverged'):
                    if record['state'] != 'completed':
                        publish(record['state'], f'arm {arm["name"]}: '+record.get('reason','')); return state['state']
                    if (record['reserved_tokens'] != template['target_tokens']
                            or record['trained_tokens'] != template['target_tokens']):
                        publish('budget-exhausted','arm ended below equal comparison target'); return state['state']
                    break
                if active >= spec['active_seconds'] or attempted >= spec['target_tokens']:
                    publish('budget-exhausted','aggregate active/attempted budget exhausted'); return state['state']
                if record and (charged_active(record) >= template['active_seconds']
                        or record['reserved_tokens'] >= template['target_tokens']
                        or time.time()-record['started'] >= template['calendar_seconds']):
                    publish('budget-exhausted', f'arm {arm["name"]} exhausted before endpoint'); return state['state']
                if record and 'explicit STOP' in record.get('reason',''):
                    publish('stopped',record['reason']); return state['state']
                if run.exists() and record is None:
                    raise ValueError('arm directory has no durable campaign receipt')
                remaining = disk_reserve(spec, records, state['parent']['bytes'])
                free = disk_free(directory) if disk_free else shutil.disk_usage(directory).free
                disk_short = free < 20*1024**3+remaining
                gpu_busy = not gpu_available(run)
                prior = record['state'] if record else None
                if disk_short or gpu_busy or prior == 'paused-resource' or record_state['preflight_resource']:
                    record_state['resource_since'] = record_state['resource_since'] or time.time()
                    if time.time()+cooldown > record_state['resource_since']+resource_limit:
                        publish('resource-timeout', 'bounded resource retry window exhausted'); return state['state']
                    publish('cooldown','disk forecast below floor' if disk_short else 'arm resource pause')
                    wait(cooldown)
                    if disk_short or gpu_busy: continue
                elif prior in ('running','interrupted'):
                    if record_state['crashes'] >= 2:
                        publish('crash-limit', f'arm {arm["name"]}: two recoveries attempted'); return state['state']
                    record_state['crashes'] += 1
                else: record_state['resource_since'] = None
                if check_control(): return state['state']
                if parent_verifier is None:
                    from optimizer_ablation_train import verify_parent
                    payload, _receipt = verify_parent(template)
                    del payload
                else: parent_verifier(template)
                if check_control(): return state['state']
                if digest(arm_path) != record_state['materialized_sha256']:
                    raise ValueError('materialized specification changed')
                command = [sys.executable, str(trainer), str(arm_path), str(run)]
                if record: command.append('--resume')
                record_state['launches'] += 1
                log = directory/f'arm-{index+1}-worker-{record_state["launches"]:04}.log'
                state.update(worker_command=command, worker_log=str(log))
                publish('running', f'starting arm {arm["name"]}')
                with log.open('ab') as output:
                    worker = subprocess.Popen(command,cwd=trainer.parent,stdin=subprocess.DEVNULL,
                                              stdout=output,stderr=subprocess.STDOUT,pass_fds=(lock.fileno(),))
                    state['worker_pid'] = worker.pid; publish('running','bounded worker active')
                    watchdog = time.monotonic()+min(template['lease_seconds'],template['active_seconds']-charged_active(record))+120
                    while worker.poll() is None:
                        if stop_requested() or interrupted or calendar_exhausted() or time.monotonic() >= watchdog:
                            stop_worker(); break
                        time.sleep(poll_seconds)
                    state['worker_exit_code'] = worker.wait()
                if check_control(): return state['state']
                after = arm_record(run,template)
                if not after: raise ValueError('worker exited without campaign receipt')
                if after['state'] == 'paused-resource' and (prior != 'paused-resource'
                        or after['reserved_tokens'] > record['reserved_tokens']):
                    record_state['resource_since'] = time.time()
                if state['worker_exit_code'] != 0 and after == record:
                    tail = log.read_bytes()[-16384:].decode(errors='replace')
                    record_state['preflight_resource'] = any(x in tail for x in ('resource threshold:', 'guard unavailable:'))
                    if not record_state['preflight_resource'] and prior not in ('running','interrupted'):
                        publish('failed','worker failed before new lease'); return state['state']
                else: record_state['preflight_resource'] = False
                publish('ready','bounded worker exited')
        if check_control(): return state['state']
        output_path = directory/'comparison.json'
        command = [sys.executable,str(reporter),*[str(a['run']) for a in spec['arms']],
                   '--output',str(output_path)]
        publish('reporting','CPU evaluation of three completed arms')
        with (directory/'comparison.log').open('ab') as output:
            worker = subprocess.Popen(command,cwd=reporter.parent,stdin=subprocess.DEVNULL,
                                      stdout=output,stderr=subprocess.STDOUT,pass_fds=(lock.fileno(),))
            deadline = time.monotonic()+120
            while worker.poll() is None:
                if stop_requested() or interrupted or calendar_exhausted() or time.monotonic() >= deadline:
                    stop_worker(); break
                time.sleep(poll_seconds)
            code = worker.wait()
        if check_control(): return state['state']
        if code != 0 or not output_path.exists():
            raise ValueError('comparison report failed; inspect comparison.log')
        json.loads(output_path.read_bytes())
        state['comparison_sha256'] = digest(output_path)
        publish('completed','three bounded arms evaluated; this is not a conversational-quality pass')
        return state['state']
    except BaseException as error:
        if worker is not None and worker.poll() is None:
            worker.terminate()
            try: worker.wait(timeout=10)
            except subprocess.TimeoutExpired: worker.kill(); worker.wait()
        if state is not None:
            state.update(state='failed',reason=f'{type(error).__name__}: {error}',updated=time.time())
            signed_write(state_path,state)
        raise
    finally:
        for number, handler in handlers.items(): signal.signal(number,handler)
        lock.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('experiment',type=Path); parser.add_argument('directory',type=Path)
    args = parser.parse_args()
    result = supervise(args.experiment,args.directory)
    print(result,flush=True)
    raise SystemExit(0 if result == 'completed' else 2)
