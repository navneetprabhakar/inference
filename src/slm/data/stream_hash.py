"""Bounded-memory SHA256 for large immutable data artifacts."""
# Creator: Navneet Prabhakar
import hashlib
from pathlib import Path


def sha(path,*,chunk_bytes=1024*1024):
    if type(chunk_bytes) is not int or chunk_bytes<1:raise ValueError('Positive streaming chunk required')
    h=hashlib.sha256()
    with Path(path).open('rb') as inp:
        while block:=inp.read(chunk_bytes):h.update(block)
    return h.hexdigest()
