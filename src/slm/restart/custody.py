"""macOS trainer custody: readable allowlist, confined writes, no network.

This isolates the trusted trainer process from final evaluation/source caches.
It is not a general-purpose sandbox for arbitrary hostile native code.
"""
import json
from pathlib import Path
import sys


def profile(*,read_roots,write_root):
    if sys.platform!='darwin':raise RuntimeError('Custody implementation requires macOS')
    roots=sorted({str(Path(p).resolve(strict=True)) for p in read_roots})
    output=str(Path(write_root).resolve(strict=True))
    if '/' in roots or output=='/':raise ValueError('Unrestricted filesystem root forbidden')
    roots=sorted(set(roots+[output]))
    # Metadata is readable for Python module resolution; contents remain confined.
    exclusions=' '.join('(require-not (subpath '+json.dumps(p)+'))' for p in roots)
    return '\n'.join(['(version 1)','(allow default)','(deny network*)',
        '(deny file-read-data (require-all '+exclusions+'))',
        '(deny file-write* (require-not (subpath '+json.dumps(output)+')))',
        '(allow file-read-data (literal "/") (literal "/dev/null") (literal "/dev/urandom") (literal "/dev/random"))',
        '(allow file-write-data (literal "/dev/null"))'])+'\n'


def runtime_roots(project):
    project=Path(project).resolve()
    return [p for p in [Path('/System'),Path('/usr'),Path('/Library/Apple'),Path(sys.base_prefix),project/'.venv',project/'src'] if p.exists()]


def command(profile_path,argv):
    if not argv or not Path(argv[0]).is_absolute():raise ValueError('Absolute worker executable required')
    return ['/usr/bin/sandbox-exec','-f',str(Path(profile_path).resolve(strict=True)),*argv]
