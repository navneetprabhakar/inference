"""Atomic retained responses and output publications under one intake ledger."""
# Creator: Navneet Prabhakar
import hashlib
import os
from pathlib import Path
from slm.data.schema import digest


class IntakeCache:
    def __init__(self, root, ledger):
        self.root=Path(root)
        if self.root.is_symlink():raise ValueError('Symlink cache directory refused')
        self.root.mkdir(exist_ok=True);self.ledger=ledger
        ledger.db.execute('CREATE TABLE IF NOT EXISTS payloads (key TEXT PRIMARY KEY, size INTEGER, sha256 TEXT)')

    def existing(self,key):
        row=self.ledger.db.execute('SELECT a.state,p.size,p.sha256 FROM attempts a LEFT JOIN payloads p ON a.key=p.key WHERE a.key=?',(key,)).fetchone()
        if row is None:return None
        if row[0]!='complete':raise ValueError('Uncertain operation cannot replay')
        p=self.root/(digest(key)+'.bin')
        if p.is_symlink() or not p.is_file():raise ValueError('Completed cache payload missing')
        if p.stat().st_size!=row[1]:raise ValueError('Completed cache payload changed')
        raw=p.read_bytes()
        if len(raw)!=row[1] or hashlib.sha256(raw).hexdigest()!=row[2]:raise ValueError('Completed cache payload changed')
        self.ledger.check_time();return raw

    def fetch(self,key,length,producer):
        cached=self.existing(key)
        if cached is not None:
            if len(cached)!=length:raise ValueError('Cached response length differs')
            return cached
        self.ledger.reserve(key,requests=1,body_bytes=length+1,output_bytes=length)
        raw=producer()
        if not isinstance(raw,bytes) or len(raw)!=length:raise ValueError('Exact bounded response length required')
        self._write(key,raw);self.ledger.finish(key,raw=raw);return raw

    def publish(self,key,raw,*,rows=0):
        cached=self.existing(key)
        if cached is not None:
            if cached!=raw:raise ValueError('Reconstructed output changed')
            return
        # Body charge is zero: output hashes/counts are retained separately from HTTP.
        self.ledger.reserve(key,rows=rows,output_bytes=len(raw))
        self._write(key,raw)
        self.ledger.finish(key,raw=b'')

    def _write(self,key,raw):
        target=self.root/(digest(key)+'.bin');temp=target.with_suffix('.partial')
        if target.exists() or temp.exists():raise ValueError('Uncertain existing payload refused')
        with temp.open('xb') as out:out.write(raw);out.flush();os.fsync(out.fileno())
        os.rename(temp,target)
        descriptor=os.open(self.root,os.O_RDONLY)
        try:os.fsync(descriptor)
        finally:os.close(descriptor)
        self.ledger.db.execute('INSERT INTO payloads VALUES (?,?,?)',
            (key,len(raw),hashlib.sha256(raw).hexdigest()))
