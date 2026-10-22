"""Bounded synthetic production-schema storage estimate, no retained source read."""
import json
from pathlib import Path
import signal
import sqlite3
import tempfile
import time
import inventory as r
import inventory_core as c


def main():
    def stop(s,f):raise TimeoutError('30sec_synthetic_projection_bound')
    for sig in [signal.SIGALRM,signal.SIGINT,signal.SIGTERM]:signal.signal(sig,stop)
    signal.setitimer(signal.ITIMER_REAL,30)
    started=r.clock();results=[];count=100000
    try:
        assessor=r.load('synthetic_projection_assessor',r.ASSESSOR)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for width in [27,40,56]:
                p=root/f'{width}.sqlite';store=c.Store(p,db_cap=20000000)
                try:
                    for i in range(count):
                        title=('Synthetic title '+str(i).zfill(8)).ljust(width,'x')
                        raw=f'{(i//100)*1000}:{(i*104729)%100000007+1}:{title}\n'.encode()
                        store.emit(raw,assessor.parse(raw,i+1,26668484995))
                    store.end_group(26668484995);store.db.commit()
                finally:store.close()
                if sum(f.stat().st_size for f in root.iterdir())>64000000:raise ValueError('64MB_synthetic_scratch')
                with sqlite3.connect(p) as db:
                    if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise ValueError('projection_integrity')
                size=p.stat().st_size
                results.append({'title_UTF8_bytes':width,'rows':count,'SQLite_bytes':size,
                    'bytes_per_row':size/count,'projected_full_rows_bytes':size/count*25792234,
                    'projected_plus10pct':size/count*25792234*1.1})
        print(json.dumps({'status':'SYNTHETIC_ONLY','cases':results,'elapsed_seconds':r.clock()-started,
            'retained_index_body_reads':0,'capacity_not_completion_guarantee':True},indent=2))
    finally:signal.setitimer(signal.ITIMER_REAL,0)


if __name__=='__main__':main()
