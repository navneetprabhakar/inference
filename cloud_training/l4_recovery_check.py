"""GCS checkpoint roundtrip, explicitly invoked by the bounded GPU worker.

No credentials or cloud operations occur on import. Each upload uses a unique,
immutable prefix and publishes COMMITTED only after all component copies finish.
The downloaded bundle is validated independently; the caller must restore it and
prove the next update to establish a training-resume guarantee.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
import subprocess
import time
import uuid

from cloud_training.nano_checkpoint import validate_bundle

COMPONENTS = ('payload.pt', 'metadata.json', 'manifest.json', 'COMMITTED')


def _remote_prefix(remote_prefix):
    if not re.fullmatch(r'gs://[a-z0-9][a-z0-9._-]+/[A-Za-z0-9_./-]+', remote_prefix):
        raise ValueError('Use an explicit GCS bucket/object prefix without wildcards')
    return remote_prefix.rstrip('/') + '/checkpoint-' + uuid.uuid4().hex


def _budget(timeout):
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 1800:
        raise ValueError('Transfer timeout must be finite, positive and <=1800 seconds')
    start = time.monotonic()
    return start, start + timeout


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('GCS checkpoint transfer deadline expired')
    return remaining


def _copy(src, dst, deadline):
    # Keep checksum validation enabled. All validation, upload and readback work
    # shares the caller's one deadline; no fresh allowance after local hashing.
    command = ['gcloud', 'storage', 'cp', str(src), str(dst), '--quiet']
    subprocess.run(command, check=True, timeout=_remaining(deadline), capture_output=True, text=True)


def _publish(source, original, remote, start, deadline):
    for name in COMPONENTS:  # COMMITTED must remain last.
        _copy(source / name, remote + '/' + name, deadline)
    metadata = json.loads((source / 'metadata.json').read_text())
    _remaining(deadline)
    return {'status': 'gcs_bundle_uploaded', 'remote_prefix': remote,
            'seconds': time.monotonic() - start,
            'bytes_one_way': sum((source / name).stat().st_size for name in COMPONENTS),
            'identity': metadata['identity'], 'step': metadata['step'],
            'manifest': original, 'publication_order': list(COMPONENTS),
            'transfer_integrity': 'gcloud storage cp built-in checksum validation',
            'independent_sha256_readback': False,
            'note': 'Upload receipt only; fresh-machine restore and next update not tested.'}


def upload_bundle(source, *, remote_prefix, timeout=600):
    """Checksummed upload within one deadline including local validation.

    Local validation cannot be preempted here; if it exhausts the allowance, no
    upload begins. This receipt never claims independent SHA readback or restart.
    """
    start, deadline = _budget(timeout)
    remote = _remote_prefix(remote_prefix)
    source = Path(source).resolve()
    original = validate_bundle(source)
    _remaining(deadline)
    return _publish(source, original, remote, start, deadline)


def roundtrip_bundle(source, *, remote_prefix, destination, timeout=600):
    """One shared deadline covers validation, upload and independent readback."""
    start, deadline = _budget(timeout)
    remote = _remote_prefix(remote_prefix)
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    original = validate_bundle(source)
    _remaining(deadline)
    destination.mkdir(parents=True)
    receipt = _publish(source, original, remote, start, deadline)
    for name in COMPONENTS:
        _copy(remote + '/' + name, destination / name, deadline)
    downloaded = validate_bundle(destination)
    if downloaded != original:
        raise ValueError('Downloaded manifest differs from original bundle')
    original_meta = json.loads((source / 'metadata.json').read_text())
    downloaded_meta = json.loads((destination / 'metadata.json').read_text())
    if downloaded_meta != original_meta:
        raise ValueError('Downloaded checkpoint metadata differs')
    _remaining(deadline)
    return {**receipt, 'status': 'gcs_bundle_integrity_passed',
            'download_directory': str(destination), 'seconds': time.monotonic() - start,
            'independent_sha256_readback': True,
            'note': 'Fresh directory download verified; caller must restore and compare next update. Not a fresh-VM restart test.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--remote-prefix', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--timeout', type=float, default=600)
    parser.add_argument('--receipt', required=True)
    args = parser.parse_args()
    receipt = roundtrip_bundle(args.source, remote_prefix=args.remote_prefix,
                               destination=args.destination, timeout=args.timeout)
    Path(args.receipt).write_text(json.dumps(receipt, indent=2) + '\n')


if __name__ == '__main__':
    main()
