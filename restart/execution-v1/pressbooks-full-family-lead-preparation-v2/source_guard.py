"""Bounded immutable metadata reads only; actual frame custody is in overlay."""
from pathlib import Path
import stat

def ident(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
def small(path,cap=8000000):
 p=Path(path)
 if p.is_symlink() or not p.is_file() or p.stat().st_size>cap:raise ValueError('metadata_regular_bound')
 raw=p.read_bytes()
 if len(raw)>cap:raise ValueError('metadata_read_cap')
 return raw
