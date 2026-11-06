"""Manually retire one redundant optimizer rolling checkpoint after comparison.

Dry-run is the default. This does not run a model, change protected artifacts, or
schedule itself. Historical ledger bytes remain archived; their old artifact
mentions are audit evidence, not live restore pointers. The reference scan is
limited to named operational metadata, not arbitrary notes or sealed examples.
The explicit comparison hash binds the reporter's earlier payload-identity
verification; this utility verifies unchanged artifact bytes without loading
model tensors. Applying requires a shared, nonblocking GPU-run lock as well as
exclusive checkpoint locks for all three completed arms.
"""
import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import time

ROOT = Path(__file__).resolve().parent
BRANCHES = ('preserve-095', 'reset-095', 'reset-scaled')
TARGET = 19_996_672
NAME = re.compile(r'step-(\d+)-([0-9a-f]{64})\.pt')
COMMON_KEYS = ('parent', 'source_offset', 'target_tokens', 'length', 'microbatch', 'targets_per_update',
               'seed', 'bf16', 'corpus', 'manifest_sha256', 'validation_blocks_sha256',
               'diagnostics_sha256', 'scheduler', 'protocol_sha256', 'code_sha256')
ARCHIVE = 'rolling-retirement'
LINEAGE = '120cc3af4b7ffb566bd7fdc5104783a9886ef2c7414b0611303acb4b653e74b8'
TOKENIZER = {'encoder.json': '196139668be63f3b5d6574427317ae82f612a97c5d1cdaf36ed2256dbf636783',
             'vocab.bpe': '1ce1664773c50f3e0cc8842619a93edc4624525b728b188a9e0be33b7726adc5'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('expected regular nonsymlink file: '+str(path))
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def byte_sha(value):
    return hashlib.sha256(value).hexdigest()


def signed(value):
    return dict(value, sha256=byte_sha(canonical(value)))


def read_signed(path):
    digest(path)
    value = json.loads(Path(path).read_bytes())
    signature = value.pop('sha256')
    if signature != byte_sha(canonical(value)):
        raise ValueError('metadata checksum mismatch: '+str(path))
    return value


def sync(directory):
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def immutable(path, data):
    """Never overwrite audit evidence, including after an interrupted preparation."""
    if path.exists():
        if path.is_symlink() or path.read_bytes() != data:
            raise ValueError('existing audit artifact differs: '+str(path))
        return
    # Publish a complete file without replacing an existing audit artifact.
    # A killed process may leave its uniquely named temporary; recovery never
    # deletes such unknown leftovers or mistakes them for published evidence.
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.retirement-', suffix='.tmp', delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(data); stream.flush(); os.fsync(stream.fileno()); stream.close()
            try:
                os.link(temp, path)
            except FileExistsError:
                if path.is_symlink() or path.read_bytes() != data:
                    raise ValueError('existing audit artifact differs: '+str(path))
            sync(path.parent)
        finally:
            temp.unlink(missing_ok=True)


def replace(path, data):
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.retirement-', suffix='.tmp', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(data); stream.flush(); os.fsync(stream.fileno()); stream.close()
            os.replace(temporary, path)
            sync(path.parent)
        finally:
            temporary.unlink(missing_ok=True)


def allowed_run(run):
    supplied = Path(run)
    resolved = supplied.resolve()
    if (ROOT/'runs').is_symlink():
        raise ValueError('run root cannot be a symlink')
    names = {str(ROOT/'runs'/('optimizer-ablation-v1-'+b)): b for b in BRANCHES}
    if supplied.is_symlink() or str(resolved) not in names:
        raise ValueError('only the three completed optimizer ablation runs are eligible')
    return resolved, names[str(resolved)]


def entry_valid(entry):
    match = NAME.fullmatch(entry.get('file', ''))
    if (set(entry) != {'file', 'sha256', 'bytes'} or not match or match[2] != entry['sha256']
            or type(entry['bytes']) is not int or not 0 < entry['bytes'] <= 4*1024**3):
        raise ValueError('invalid checkpoint receipt')
    return int(match[1])


def artifact(run, entry):
    entry_valid(entry)
    path = run/entry['file']
    if path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
        raise ValueError('checkpoint bytes differ from receipt: '+entry['file'])


def snapshots(run, endpoint):
    old_ledger = (run/'campaign.json').read_bytes()
    old_latest = (run/'latest.json').read_bytes()
    ledger = read_signed(run/'campaign.json')
    latest = json.loads(old_latest)
    if ledger['checkpoints'] != latest or not 1 <= len(latest) <= 2 or latest[0] != endpoint:
        raise ValueError('rolling pointers are inconsistent')
    new_ledger = dict(ledger, checkpoints=[endpoint])
    return {'original-campaign.json': old_ledger, 'original-latest.json': old_latest,
            'new-campaign.json': canonical(signed(new_ledger)), 'new-latest.json': canonical([endpoint]),
            'campaign-spec.json': (run/'campaign-spec.json').read_bytes(),
            'protected.json': (run/'protected.json').read_bytes()}


def find_plan(run):
    directory = run/ARCHIVE
    if directory.is_symlink():
        raise ValueError('retirement archive cannot be a symlink')
    if not directory.exists():
        return None
    plans = list(directory.glob('*/plan.json'))
    if len(plans) > 1:
        raise ValueError('ambiguous retirement transactions')
    if not plans:
        return None
    path = plans[0]
    if path.parent.is_symlink():
        raise ValueError('retirement transaction cannot be a symlink')
    digest(path)
    plan = read_signed(path)
    if plan['schema'] != 1 or plan['run'] != str(run):
        raise ValueError('retirement plan belongs to another run')
    data = {}
    for name, expected in plan['snapshots'].items():
        if name not in {'original-campaign.json', 'original-latest.json', 'new-campaign.json',
                        'new-latest.json', 'campaign-spec.json', 'protected.json', 'comparison.json'}:
            raise ValueError('unknown retirement snapshot')
        if digest(path.parent/name) != expected:
            raise ValueError('archived metadata changed')
        data[name] = (path.parent/name).read_bytes()
    required = {'original-campaign.json', 'original-latest.json', 'new-campaign.json',
                'new-latest.json', 'campaign-spec.json', 'protected.json', 'comparison.json'}
    if set(data) != required:
        raise ValueError('incomplete retirement archive')
    old = read_signed(path.parent/'original-campaign.json')
    new = read_signed(path.parent/'new-campaign.json')
    expected_new = dict(old, checkpoints=[plan['endpoint']])
    if (new != expected_new or json.loads(data['original-latest.json']) != old['checkpoints']
            or json.loads(data['new-latest.json']) != [plan['endpoint']]
            or old['checkpoints'] != [plan['endpoint'], plan['candidate']]):
        raise ValueError('retirement changes more than the redundant live pointer')
    return path.parent, plan, data


def validate_arm(run, branch, report, comparison_sha):
    for name in ('campaign.json', 'campaign-spec.json', 'latest.json', 'protected.json'):
        digest(run/name)
    receipt = report['receipts'][branch]
    if Path(receipt['run']).resolve() != run:
        raise ValueError('comparison receipt identifies a different arm')
    endpoint = receipt['checkpoint']
    if entry_valid(endpoint) != TARGET//8192:
        raise ValueError('comparison endpoint step differs')
    # A prior retirement keeps the original report's old ledger receipt verifiable.
    transaction = find_plan(run)
    if transaction:
        directory, plan, data = transaction
        if (plan['comparison_sha256'] != comparison_sha or plan['endpoint'] != endpoint
                or byte_sha(data['original-campaign.json']) != receipt['ledger_sha256']):
            raise ValueError('retirement archive does not preserve the comparison receipt')
        old_hash = plan['snapshots']['original-campaign.json']
        new_hash = plan['snapshots']['new-campaign.json']
        old_latest = plan['snapshots']['original-latest.json']
        new_latest = plan['snapshots']['new-latest.json']
        actual = digest(run/'campaign.json'), digest(run/'latest.json')
        if actual not in {(old_hash, old_latest), (old_hash, new_latest), (new_hash, new_latest)}:
            raise ValueError('unrecognized retirement publication state')
        if (digest(run/'campaign-spec.json') != plan['snapshots']['campaign-spec.json']
                or digest(run/'protected.json') != plan['snapshots']['protected.json']):
            raise ValueError('immutable specification or protection inventory changed')
    elif digest(run/'campaign.json') != receipt['ledger_sha256']:
        raise ValueError('comparison ledger hash mismatch')
    ledger = read_signed(run/'campaign.json')
    frozen = json.loads((run/'campaign-spec.json').read_bytes())
    spec = frozen['identity']['protocol']
    if (ledger['state'] != 'completed' or ledger['trained_tokens'] != TARGET
            or ledger['reserved_tokens'] != TARGET or ledger['step'] != TARGET//8192
            or ledger['spec'] != frozen or frozen['token_limit'] != TARGET
            or spec['branch'] != branch or {k: spec[k] for k in COMMON_KEYS} != report['common']):
        raise ValueError('arm is incomplete or differs from the comparison identity')
    if frozen['identity']['model'] != dict(vocabulary=50257, context=1024, width=768, heads=12, depth=12):
        raise ValueError('unexpected model configuration')
    identity = frozen['identity']
    parent = spec['parent']
    if (Path(parent['run']).resolve() != ROOT/'runs/own-base-foundation-01'
            or identity['initialization'] != dict(mode='own_pretraining',
                path=str(Path(parent['run'])/parent['checkpoint']), sha256=parent['sha256'], random_lineage_root=LINEAGE)
            or identity['tokenizer'] != TOKENIZER or identity['scheduler'] != spec['scheduler']
            or identity['code'] != spec['code_sha256'] or identity['seed'] != spec['seed']
            or identity['corpus'] != dict(directory=spec['corpus'], manifest=spec['manifest_sha256'],
                validation=spec['validation_blocks_sha256'], source_offset=spec['source_offset'])
            or (spec['source_offset'], spec['target_tokens'], spec['length'], spec['microbatch'],
                spec['targets_per_update'], spec['seed'], spec['bf16']) != (99999744, TARGET, 512, 2, 8192, 20261106, True)):
        raise ValueError('own-base architecture/data/optimizer protocol ancestry mismatch')
    protected = json.loads((run/'protected.json').read_bytes())
    if not isinstance(protected, list) or endpoint['file'] not in protected:
        raise ValueError('endpoint is not protected')
    latest = json.loads((run/'latest.json').read_bytes())
    if not latest or latest[0] != endpoint or not ledger['checkpoints'] or ledger['checkpoints'][0] != endpoint:
        raise ValueError('protected endpoint is not the sole retained primary restore target')
    artifact(run, endpoint)
    if digest(Path(spec['protocol_path'])) != spec['protocol_sha256']:
        raise ValueError('frozen experiment protocol changed')
    return transaction


def reference_scan(run, candidate, report):
    """Conservative exact-reference check over known operational metadata only."""
    needles = {candidate['file'], candidate['sha256'], str(run/candidate['file'])}

    def mentions(value):
        if isinstance(value, str):
            return value in needles or value.endswith('/'+candidate['file'])
        if isinstance(value, dict):
            return any(mentions(x) for x in value.values())
        if isinstance(value, list):
            return any(mentions(x) for x in value)
        return False

    if mentions(report):
        raise ValueError('comparison report references the proposed redundant artifact')
    paths = set()
    for name in ('campaign.json', 'campaign-spec.json', 'config.json', 'latest.json', 'protected.json'):
        paths.update((ROOT/'runs').glob('*/'+name))
    paths.update((ROOT/'runs').glob('*/arm-*.json'))
    for pattern in ('**/budget.json', '**/experiment*.json', '**/*template*.json'):
        paths.update((ROOT/'reports').glob(pattern))
    inventory = {}
    for path in sorted(paths):
        if path in (run/'campaign.json', run/'latest.json'):
            continue  # Only these two explicit references may be detached.
        if path.is_symlink():
            raise ValueError('symlink in operational reference inventory: '+str(path))
        content = path.read_bytes()
        if mentions(json.loads(content)):
            raise ValueError('artifact remains referenced by '+str(path))
        inventory[str(path)] = byte_sha(content)
    return inventory


def event(directory, filename, kind, plan_sha, **extra):
    path = directory/filename
    if path.exists():
        value = read_signed(path)
        if value.get('kind') != kind or value.get('plan_sha256') != plan_sha:
            raise ValueError('retirement event belongs to a different transition')
        if 'artifact' in extra and value.get('artifact') != extra['artifact']:
            raise ValueError('retirement event identifies a different artifact')
        return value
    value = dict(kind=kind, plan_sha256=plan_sha, timestamp=time.time(), **extra)
    immutable(path, canonical(signed(value)))
    return value


def retire(run, expected_endpoint_sha, comparison_path, comparison_sha, *, apply=False, _fault=None):
    run, branch = allowed_run(run)
    comparison_path = Path(comparison_path).resolve()
    if digest(comparison_path) != comparison_sha:
        raise ValueError('comparison report checksum mismatch')
    report = json.loads(comparison_path.read_bytes())
    if (report['state'] != 'screen-completed' or set(report['receipts']) != set(BRANCHES)
            or report.get('usable_assistant') is not False):
        raise ValueError('all-three-arm comparison completion is required')
    if digest(ROOT/'optimizer_ablation_report.py') != report['report_code_sha256']:
        raise ValueError('comparison reporter implementation changed')
    for name, expected in report['common']['code_sha256'].items():
        source = (ROOT/name).resolve()
        if source.parent != ROOT or digest(source) != expected:
            raise ValueError('frozen runtime identity changed: '+name)
    arms = {b: ROOT/'runs'/('optimizer-ablation-v1-'+b) for b in BRANCHES}
    with ExitStack() as locks:
        if apply:
            gpu_path = ROOT/'runs/mps.lock'
            if gpu_path.is_symlink():
                raise ValueError('GPU-run lock cannot be a symlink')
            gpu = locks.enter_context(gpu_path.open('rb'))
            try:
                fcntl.flock(gpu, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('an active GPU worker prevents retirement') from error
        for path in sorted(arms.values()):
            if path.is_symlink() or (path/'.checkpoint.lock').is_symlink():
                raise ValueError('checkpoint lock/run cannot be a symlink')
            stream = locks.enter_context((path/'.checkpoint.lock').open('rb'))
            try:
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ValueError('checkpoint publication/retirement active') from error
        transactions = {b: validate_arm(p, b, report, comparison_sha) for b, p in arms.items()}
        endpoint = report['receipts'][branch]['checkpoint']
        if endpoint['sha256'] != expected_endpoint_sha:
            raise ValueError('explicit endpoint SHA does not match protected comparison artifact')
        transaction = transactions[branch]
        if transaction:
            directory, plan, data = transaction
            if plan['comparison_path'] != str(comparison_path):
                raise ValueError('recovery requires the original comparison path')
            candidate = plan['candidate']
        else:
            data = snapshots(run, endpoint)
            entries = json.loads(data['original-latest.json'])
            if len(entries) == 1:
                return dict(state='nothing-to-retire', run=str(run), endpoint=endpoint, applied=False)
            candidate = entries[1]
            step = entry_valid(candidate)
            if candidate == endpoint or candidate['file'] == endpoint['file'] or step >= TARGET//8192:
                raise ValueError('candidate is not an older redundant rolling artifact')
            data['comparison.json'] = comparison_path.read_bytes()
            transaction_id = byte_sha(canonical(dict(endpoint=endpoint['sha256'], candidate=candidate['sha256'], comparison=comparison_sha)))
            directory = run/ARCHIVE/transaction_id
            if directory.is_symlink():
                raise ValueError('retirement directory cannot be a symlink')
            plan = dict(schema=1, run=str(run), branch=branch, endpoint=endpoint, candidate=candidate,
                        comparison_path=str(comparison_path), comparison_sha256=comparison_sha,
                        snapshots={name: byte_sha(content) for name, content in data.items()})
        if entry_valid(candidate) >= entry_valid(endpoint):
            raise ValueError('candidate must precede the protected endpoint optimizer step')
        protected = json.loads((run/'protected.json').read_bytes())
        if candidate['file'] in protected:
            raise ValueError('cannot retire a protected artifact')
        inventory = reference_scan(run, candidate, report)
        candidate_path = run/candidate['file']
        if candidate_path.is_symlink():
            raise ValueError('candidate artifact cannot be a symlink')
        if candidate_path.exists():
            artifact(run, candidate)
        elif not transaction or not (directory/'03-deletion-authorized.json').exists():
            raise ValueError('candidate disappeared before durable deletion authorization')
        else:
            authorization = read_signed(directory/'03-deletion-authorized.json')
            if (authorization.get('kind') != 'deletion-authorized' or authorization.get('artifact') != candidate
                    or authorization.get('plan_sha256') != digest(directory/'plan.json')):
                raise ValueError('missing artifact is not covered by the durable deletion intent')
        result = dict(state='ready-to-retire' if not transaction else 'recoverable-retirement',
                      run=str(run), endpoint=endpoint, candidate=candidate, applied=False,
                      bytes_reclaimable=candidate['bytes'] if candidate_path.exists() else 0,
                      reference_scope='Named operational metadata only; arbitrary notes and sealed examples are not scanned.',
                      reference_files_checked=len(inventory), audit_directory=str(directory))
        if not apply:
            return result
        if not directory.exists():
            directory.mkdir(parents=True)
            sync(directory.parent); sync(directory.parent.parent)
        for name, content in data.items():
            immutable(directory/name, content)
        if _fault: _fault('archives')
        immutable(directory/'plan.json', canonical(signed(plan)))
        plan_sha = digest(directory/'plan.json')
        event(directory, '00-prepared.json', 'prepared', plan_sha)
        if _fault: _fault('prepared')
        # Recovery admits only the old/new hashes validated above. Publication
        # order is fixed; a crash may leave latest detached before the ledger.
        if digest(run/'latest.json') != plan['snapshots']['new-latest.json']:
            replace(run/'latest.json', data['new-latest.json'])
        if _fault: _fault('latest-published')
        event(directory, '01-latest-detached.json', 'latest-detached', plan_sha)
        if digest(run/'campaign.json') != plan['snapshots']['new-campaign.json']:
            replace(run/'campaign.json', data['new-campaign.json'])
        if _fault: _fault('ledger-published')
        event(directory, '02-ledger-detached.json', 'ledger-detached', plan_sha)
        if (json.loads((run/'latest.json').read_bytes()) != [endpoint]
                or read_signed(run/'campaign.json')['checkpoints'] != [endpoint]):
            raise ValueError('live references were not completely detached')
        artifact(run, endpoint)
        if candidate['file'] in json.loads((run/'protected.json').read_bytes()):
            raise ValueError('candidate became protected')
        inventory = reference_scan(run, candidate, report)
        event(directory, '03-deletion-authorized.json', 'deletion-authorized', plan_sha,
              artifact=candidate, reference_inventory=inventory)
        if _fault: _fault('deletion-authorized')
        if candidate_path.exists():
            artifact(run, candidate)  # Last checksum verification before unlink.
            reference_scan(run, candidate, report)
            candidate_path.unlink(); sync(run)
        if _fault: _fault('unlinked')
        event(directory, '04-deleted.json', 'deleted-or-recovered-after-authorization', plan_sha, artifact=candidate)
        receipt = dict(schema=1, state='retired', run=str(run), branch=branch,
                       plan_sha256=plan_sha, comparison_sha256=comparison_sha,
                       endpoint=endpoint, retired_artifact=candidate,
                       original_ledger_sha256=plan['snapshots']['original-campaign.json'],
                       current_ledger_sha256=plan['snapshots']['new-campaign.json'],
                       original_latest_sha256=plan['snapshots']['original-latest.json'],
                       current_latest_sha256=plan['snapshots']['new-latest.json'])
        immutable(directory/'receipt.json', canonical(signed(receipt)))
        if _fault: _fault('receipt')
        return dict(receipt, applied=True, audit_directory=str(directory))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--expected-endpoint-sha', required=True)
    parser.add_argument('--comparison', required=True, type=Path)
    parser.add_argument('--comparison-sha', required=True)
    parser.add_argument('--apply', action='store_true', help='Explicitly detach and delete this verified redundant copy')
    args = parser.parse_args()
    print(json.dumps(retire(args.run, args.expected_endpoint_sha, args.comparison, args.comparison_sha, apply=args.apply), indent=2))
