"""Verify and extract the exact private offline input package before any execution."""
# Creator: Navneet Prabhakar
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import sys


def checksum(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            h.update(chunk)
    return h.hexdigest()


def unpack(archive, expected_hash, output):
    archive, output = Path(archive), Path(output)
    if output.exists():
        raise FileExistsError('Preserve existing cloud extraction')
    if archive.stat().st_size > 8*1024**3 or checksum(archive) != expected_hash:
        raise ValueError('Exact bounded offline archive required')
    with tarfile.open(archive, 'r:gz') as source:
        members = source.getmembers(); names = [m.name for m in members]
        if len(names) != len(set(names)) or any(not m.isfile() for m in members):
            raise ValueError('Only unique regular archive files allowed')
        metadata = source.getmember('manifest.json')
        if metadata.size > 4*1024**2:
            raise ValueError('Bounded input manifest required')
        manifest = json.load(source.extractfile(metadata))
        expected = {'manifest.json': None}
        for name, value in manifest['files'].items():
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] not in ('src', 'scripts', 'configs', 'data'):
                raise ValueError('Noncanonical project archive path')
            expected['project/'+name] = value
        for name, value in manifest['wheels'].items():
            if PurePosixPath(name).name != name or not name.endswith('.whl'):
                raise ValueError('Canonical offline wheel filename required')
            expected['wheels/'+name] = value
        if set(names) != set(expected) or sum(m.size for m in members) > 13*1024**3:
            raise ValueError('Exact bounded manifest file membership required')
        output.mkdir()
        for member in members:
            target = output/member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            with source.extractfile(member) as stream, target.open('xb') as destination:
                shutil.copyfileobj(stream, destination, 1024*1024)
            if expected[member.name] is not None and checksum(target) != expected[member.name]:
                raise ValueError('Transferred package payload hash differs')
        result = dict(creator='Navneet Prabhakar', complete=True, archive_sha256=expected_hash,
                      plan_sha256=manifest['plan_sha256'], project_files=len(manifest['files']),
                      wheel_files=len(manifest['wheels']), extracted_bytes=sum(m.size for m in members))
        (output/'extraction-receipt.json').write_text(json.dumps(result, indent=2)+'\n')
        return result


if __name__ == '__main__':
    print(json.dumps(unpack(*sys.argv[1:]), indent=2))
