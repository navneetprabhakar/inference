"""GCS checkpoint roundtrip, explicitly invoked by the bounded GPU worker.

No credentials or cloud operations occur on import. Each upload uses a unique,
immutable prefix and publishes COMMITTED only after all component copies finish.
The downloaded bundle is validated independently; the caller must restore it and
prove the next update to establish a training-resume guarantee.
"""
from __future__ import annotations

import argparse
import json
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


def _copy(src, dst, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError('GCS checkpoint transfer deadline expired')
    # gcloud storage cp validates transfer checksums by default. Do not disable
    # this check. Independent SHA256 readback is performed by roundtrip_bundle.
    command = ['gcloud', 'storage', 'cp', str(src), str(dst), '--quiet']
    subprocess.run(command, check=True, timeout=remaining, capture_output=True, text=True)


def upload_bundle(source, *, remote_prefix, timeout=600):
    """Checksummed GCS upload; does not download or claim fresh-machine recovery.

    The returned local SHA manifest plus successful gcloud checksum validation
    establish the upload receipt. Use roundtrip_bundle for independent SHA readback.
    Caller handles retention and billing; every invocation creates a new prefix.
    """
    source = Path(source).resolve()
    original = validate_bundle(source)
    if not 0 < timeout <= 1800:
        raise ValueError('Upload timeout must be positive and <=1800 seconds')
    remote = _remote_prefix(remote_prefix)
    start = time.monotonic()
    deadline = start + timeout
    for name in COMPONENTS:  # COMMITTED must remain last.
        _copy(source / name, remote + '/' + name, deadline)
    metadata = json.loads((source / 'metadata.json').read_text())
    return {'status': 'gcs_bundle_uploaded', 'remote_prefix': remote,
            'seconds': time.monotonic() - start,
            'bytes_one_way': sum((source / name).stat().st_size for name in COMPONENTS),
            'identity': metadata['identity'], 'step': metadata['step'],
            'manifest': original, 'publication_order': list(COMPONENTS),
            'transfer_integrity': 'gcloud storage cp built-in checksum validation',
            'independent_sha256_readback': False,
            'note': 'Upload receipt only; fresh-machine restore and next update not tested.'}


def roundtrip_bundle(source, *, remote_prefix, destination, timeout=600):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    original = validate_bundle(source)
    if not 0 < timeout <= 1800:
        raise ValueError('Roundtrip timeout must be positive and <=1800 seconds')
    if destination.exists():
        raise FileExistsError(destination)
    # Validate path before creating destination or starting uploads.
    _remote_prefix(remote_prefix)
    destination.mkdir(parents=True)
    start = time.monotonic()
    deadline = start + timeout
    receipt = upload_bundle(source, remote_prefix=remote_prefix, timeout=timeout)
    remote = receipt['remote_prefix']
    for name in COMPONENTS:
        _copy(remote + '/' + name, destination / name, deadline)
    downloaded = validate_bundle(destination)
    if downloaded != original:
        raise ValueError('Downloaded manifest differs from original bundle')
    original_meta = json.loads((source / 'metadata.json').read_text())
    downloaded_meta = json.loads((destination / 'metadata.json').read_text())
    if downloaded_meta != original_meta:
        raise ValueError('Downloaded checkpoint metadata differs')
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
