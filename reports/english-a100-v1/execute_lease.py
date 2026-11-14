"""Execute only the reviewed, prepaid-reservation qualification request once."""
import json, hashlib, subprocess, datetime as dt, fcntl

def require(condition, message):
    if not condition:
        raise ValueError(message)
from pathlib import Path
P = Path(__file__).parent
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
with (P / 'launch.lock').open('a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    request = json.loads((P / 'launch-request.json').read_text())
    ledger = json.loads((P / 'spend-ledger.json').read_text())
    if (P / 'launch-response.json').exists():
        raise ValueError('Single attempt already recorded; reconcile before any retry')
    require(ledger['operational_cap_usd'] == 10 and ledger['reserve_usd'] == 3.5, "Lease guard failed: ledger['operational_cap_usd'] == 10 and ledger['reserve_usd'] == 3.5")
    require(len(ledger['allocations']) == 2, "Lease guard failed: len(ledger['allocations']) == 2")
    allocation = ledger['allocations'][-1]
    require(allocation['name'] == request['run_id'] and allocation['state'] == 'reserved_before_provisioning', "Lease guard failed: allocation['name'] == request['run_id'] and allocation['state'] == 'reserved_before_provisioning'")
    require(allocation['request_sha256'] == sha(P / 'launch-request.json'), "Lease guard failed: allocation['request_sha256'] == sha(P / 'launch-request.json')")
    require(sum(a['reserved_compute_usd'] for a in ledger['allocations']) + ledger['reserve_usd'] <= ledger['operational_cap_usd'], "Lease guard failed: sum(a['reserved_compute_usd'] for a in ledger['allocations']) + ledger['reserve_usd'] <= ledger['operational_cap_usd']")
    require(sha(P / 'bootstrap.sh') == request['bootstrap_sha256'], "Lease guard failed: sha(P / 'bootstrap.sh') == request['bootstrap_sha256']")
    proof = json.loads((P / 'input-backup-receipt.json').read_text())
    require(proof['all_verified'], "Lease guard failed: proof['all_verified']")
    require([{k: x[k] for k in ('path', 'uri', 'sha256')} for x in proof['files']] == [{k: x[k] for k in ('path', 'uri', 'sha256')} for x in request['inputs']], "Lease guard failed: [{k: x[k] for k in ('path', 'uri', 'sha256')} for x in proof['files']] == [{k: x[k] for k in ('path', 'uri', 'sha256')} for x in request['inputs']]")
    for item in proof['files']:
        require(item['independent_readback'] and sha(Path(item['path'])) == item['sha256'], "Lease guard failed: item['independent_readback'] and sha(Path(item['path'])) == item['sha256']")
    instances = json.loads(subprocess.check_output(['gcloud', 'compute', 'instances', 'list', '--project=executespecv1', '--format=json(name,status)'], text=True, timeout=60))
    require(all((i['status'] == 'TERMINATED' for i in instances)), "Lease guard failed: all((i['status'] == 'TERMINATED' for i in instances))")
    deadline = dt.datetime.fromisoformat(request['latest_local_stop_utc'].replace('Z', '+00:00'))
    require((deadline - dt.datetime.now(dt.timezone.utc)).total_seconds() > 2400, 'Lease guard failed: (deadline - dt.datetime.now(dt.timezone.utc)).total_seconds() > 2400')
    argv = request['create_argv']
    zone = next((a.split('=', 1)[1] for a in argv if a.startswith('--zone=')))
    machine = json.loads(subprocess.check_output(['gcloud', 'compute', 'machine-types', 'describe', 'a2-highgpu-1g', '--project=executespecv1', '--zone=' + zone, '--format=json'], text=True, timeout=60))
    require(machine['guestCpus'] == 12 and machine['memoryMb'] == 87040, "Lease guard failed: machine['guestCpus'] == 12 and machine['memoryMb'] == 87040")
    subnet = json.loads(subprocess.check_output(['gcloud', 'compute', 'networks', 'subnets', 'describe', 'default', '--project=executespecv1', '--region=' + zone.rsplit('-', 1)[0], '--format=json'], text=True, timeout=60))
    require(subnet.get('privateIpGoogleAccess') is True, "Lease guard failed: subnet.get('privateIpGoogleAccess') is True")
    require('--instance-termination-action=STOP' in argv and '--no-boot-disk-auto-delete' in argv, "Lease guard failed: '--instance-termination-action=STOP' in argv and '--no-boot-disk-auto-delete' in argv")
    require('--machine-type=a2-highgpu-1g' in argv and '--provisioning-model=STANDARD' in argv, "Lease guard failed: '--machine-type=a2-highgpu-1g' in argv and '--provisioning-model=STANDARD' in argv")
    require('--termination-time=' + request['latest_local_stop_utc'] in argv, "Lease guard failed: '--termination-time=' + request['latest_local_stop_utc'] in argv")
    allocation['state'] = 'create_requested'
    (P / 'spend-ledger.json').write_text(json.dumps(ledger, indent=2) + '\n')
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, timeout=120)
        response = {'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'returncode': completed.returncode, 'stdout': completed.stdout, 'stderr': completed.stderr}
    except BaseException as e:
        response = {'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'returncode': None, 'error': repr(e), 'state': 'reconcile_cloud_before_retry'}
    (P / 'launch-response.json').write_text(json.dumps(response, indent=2) + '\n')
    print(json.dumps(response))
    raise SystemExit(0 if response['returncode'] == 0 else 2)
