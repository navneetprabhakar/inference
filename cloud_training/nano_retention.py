"""Receipt-scoped checkpoint retention. Dry-run by default; no bucket listings.

Only immutable UUID bundles journaled after successful upload are eligible. Keep
latest two plus explicit pins. Before deletion verify kept and candidate bundles,
then remove four exact object generations, COMMITTED first. A failed deletion is
journaled and fails closed; inspect/reconcile it explicitly rather than guessing.
No original data, bucket, prefix, wildcard, version history or local file is deleted.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

FILES = ('payload.pt', 'metadata.json', 'manifest.json', 'COMMITTED')
DELETE_ORDER = ('COMMITTED', 'payload.pt', 'metadata.json', 'manifest.json')


def _prefix(value):
    if not isinstance(value, str) or not re.fullmatch(r'gs://[a-z0-9][a-z0-9._-]+/(?:[A-Za-z0-9_-]+/)+checkpoints', value):
        raise ValueError('Explicit campaign prefix ending /checkpoints required')
    parts = value[5:].split('/')[1:]
    if any(p.lower() in {'input', 'inputs', 'source', 'original', 'originals', 'backup', 'backups'} for p in parts):
        raise ValueError('Protected input/source prefix')
    return value


def _bundle(value, campaign):
    if not isinstance(value, str) or not re.fullmatch(re.escape(campaign) + r'/checkpoint-[0-9a-f]{32}', value):
        raise ValueError('Receipt bundle is outside explicit campaign or lacks generated UUID')
    return value


def _manifest_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def _validate_receipt(receipt, campaign):
    if receipt.get('status') not in {'gcs_bundle_uploaded', 'gcs_bundle_integrity_passed'}:
        raise ValueError('Successful committed upload receipt required')
    _bundle(receipt.get('remote_prefix'), campaign)
    if receipt.get('publication_order') != list(FILES):
        raise ValueError('Commit-last publication receipt required')
    step = receipt.get('step')
    manifest = receipt.get('manifest', {})
    if type(step) is not int or step < 0 or manifest.get('version') != 1 or manifest.get('step') != step:
        raise ValueError('Invalid receipt step/version')
    if set(manifest.get('files', {})) != {'payload.pt', 'metadata.json'}:
        raise ValueError('Unexpected checkpoint files')
    for item in manifest['files'].values():
        if type(item.get('bytes')) is not int or item['bytes'] <= 0 or not re.fullmatch('[0-9a-f]{64}', item.get('sha256', '')):
            raise ValueError('Invalid component integrity receipt')
    if not isinstance(receipt.get('identity'), dict) or not receipt['identity']:
        raise ValueError('Receipt identity required')


def _atomic(path, value):
    tmp = path.with_suffix(path.suffix + '.partial')
    with tmp.open('w') as f:
        json.dump(value, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def _read(path, campaign):
    value = json.loads(path.read_text()) if path.exists() else {
        'schema': 1, 'campaign_prefix': campaign, 'entries': []}
    if value.get('schema') != 1 or value.get('campaign_prefix') != campaign:
        raise ValueError('Retention journal campaign mismatch')
    seen = set()
    for entry in value['entries']:
        _validate_receipt(entry['receipt'], campaign)
        uri = entry['receipt']['remote_prefix']
        if uri in seen: raise ValueError('Duplicate journal bundle')
        seen.add(uri)
        if entry.get('state') not in {'committed', 'deleting', 'deleted'}:
            raise ValueError('Unknown journal entry state')
        if not isinstance(entry.get('pins'), list) or any(not isinstance(v, str) or not v for v in entry['pins']):
            raise ValueError('Invalid checkpoint pins')
    return value


def record_upload(journal_path, receipt, *, campaign_prefix, pins=()):
    """Atomically journal a successful upload; pinning is additive/idempotent."""
    campaign = _prefix(campaign_prefix)
    _validate_receipt(receipt, campaign)
    if any(not isinstance(v, str) or not v for v in pins): raise ValueError('Invalid pins')
    path = Path(journal_path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix('.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        journal = _read(path, campaign)
        if journal['entries'] and any(e['receipt']['identity'] != receipt['identity'] for e in journal['entries']):
            raise ValueError('Receipt identity differs from this campaign')
        for entry in journal['entries']:
            if entry['receipt']['remote_prefix'] == receipt['remote_prefix']:
                if entry['receipt'] != receipt or entry['state'] != 'committed':
                    raise ValueError('Existing bundle receipt/state differs')
                entry['pins'] = sorted(set(entry['pins']) | set(pins))
                _atomic(path, journal)
                return journal
        journal['entries'].append({'receipt': receipt, 'pins': sorted(set(pins)), 'state': 'committed'})
        _atomic(path, journal)
        return journal


def _run(arguments, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0: raise TimeoutError('Retention operation deadline expired')
    result = subprocess.run(['gcloud', 'storage', *arguments, '--quiet'], check=True,
                            capture_output=True, text=True, timeout=remaining)
    return result.stdout


def _verify_remote(receipt, deadline):
    uri = receipt['remote_prefix']
    expected = receipt['manifest']
    generations = {}
    for name in FILES:
        info = json.loads(_run(['objects', 'describe', uri + '/' + name, '--format=json'], deadline))
        generation = str(info.get('generation', ''))
        if not re.fullmatch('[0-9]+', generation): raise ValueError('Missing remote object generation')
        if name in expected['files'] and int(info.get('size', -1)) != expected['files'][name]['bytes']:
            raise ValueError('Remote checkpoint size differs from receipt')
        generations[name] = generation
    marker = json.loads(_run(['cat', uri + '/COMMITTED'], deadline))
    raw_manifest = _run(['cat', uri + '/manifest.json'], deadline)
    digest = hashlib.sha256(raw_manifest.encode()).hexdigest()
    if marker.get('version') != 1 or marker.get('manifest_sha256') != digest:
        raise ValueError('Remote checkpoint is incomplete or corrupt')
    if json.loads(raw_manifest) != expected or digest != hashlib.sha256(_manifest_bytes(expected)).hexdigest():
        raise ValueError('Remote manifest differs from trusted upload receipt')
    return generations


def apply_retention(journal_path, *, campaign_prefix, execute=False, timeout=300):
    """Keep latest two successful journal entries plus pinned entries.

    Dry-run computes exact candidates locally and performs no cloud calls.
    Execution validates all kept/candidate objects before any deletion, then uses
    per-object generation preconditions. No automatic retry of partial deletions.
    """
    campaign = _prefix(campaign_prefix)
    if type(execute) is not bool or not 0 < timeout <= 1800:
        raise ValueError('Explicit boolean execute and bounded timeout required')
    path = Path(journal_path)
    if not path.exists(): raise FileNotFoundError(path)
    with path.with_suffix('.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        journal = _read(path, campaign)
        if any(e['state'] == 'deleting' for e in journal['entries']):
            raise ValueError('Interrupted deletion requires explicit journal/object reconciliation')
        live = [e for e in journal['entries'] if e['state'] == 'committed']
        # Highest completed steps remain protected even if an older receipt is
        # journaled late. Stable sort prefers the latest receipt on equal steps.
        latest = {e['receipt']['remote_prefix'] for e in sorted(live, key=lambda e: e['receipt']['step'])[-2:]}
        kept = [e for e in live if e['receipt']['remote_prefix'] in latest or e['pins']]
        candidates = [e for e in live if e not in kept]
        report = {'status': 'dry_run' if not execute else 'executed', 'campaign_prefix': campaign,
                  'kept': [e['receipt']['remote_prefix'] for e in kept],
                  'candidates': [e['receipt']['remote_prefix'] for e in candidates],
                  'deleted': [], 'protected_latest_count': min(2, len(live)),
                  'limitations': 'Pins are caller-supplied. Validates commitment/manifests/object sizes; not a fresh-VM restore. Soft-delete/version retention may delay storage savings.'}
        if not execute or not candidates: return report
        if len(kept) < 2: raise ValueError('At least two committed recovery bundles must remain')
        deadline = time.monotonic() + timeout
        validated = {e['receipt']['remote_prefix']: _verify_remote(e['receipt'], deadline) for e in kept + candidates}
        for entry in candidates:
            uri = entry['receipt']['remote_prefix']
            entry['state'] = 'deleting'
            entry['delete_generations'] = validated[uri]
            entry['deleted_objects'] = []
            _atomic(path, journal)
            for name in DELETE_ORDER:
                _run(['rm', uri + '/' + name, '--if-generation-match=' + validated[uri][name]], deadline)
                entry['deleted_objects'].append(name)
                _atomic(path, journal)
            entry['state'] = 'deleted'
            _atomic(path, journal)
            report['deleted'].append(uri)
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', required=True)
    parser.add_argument('--campaign-prefix', required=True)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    print(json.dumps(apply_retention(args.journal, campaign_prefix=args.campaign_prefix,
                                    execute=args.execute, timeout=args.timeout), indent=2))


if __name__ == '__main__':
    main()
