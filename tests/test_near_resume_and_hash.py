# Creator: Navneet Prabhakar
import hashlib
from pathlib import Path
import pytest
from slm.data.facet_near import FacetStore
from slm.data.facet_near_resume import resume
from slm.data.stream_hash import sha


def test_stream_hash_reads_only_declared_chunks(tmp_path,monkeypatch):
    p=tmp_path/'large';payload=b'abcdef'*100000;p.write_bytes(payload);original=Path.open;reads=[]
    class Reader:
        def __init__(self,handle):self.handle=handle
        def read(self,n):assert 0<n<=4096;reads.append(n);return self.handle.read(n)
        def __enter__(self):return self
        def __exit__(self,*args):self.handle.close()
    monkeypatch.setattr(Path,'open',lambda self,*a,**k:Reader(original(self,*a,**k)))
    assert sha(p,chunk_bytes=4096)==hashlib.sha256(payload).hexdigest()
    assert len(reads)>100


def test_resume_keeps_committed_features_and_allows_remaining_facets(tmp_path):
    args=dict(max_bytes=16*1024**2,max_facets=100,max_features=10000,max_shingles=1000)
    p=tmp_path/'db';s=FacetStore(p,**args);s.insert_facet(0,'content','A committed original source passage.');s.db.commit();before=s.db.execute('SELECT * FROM features').fetchall();s.db.close()
    r=resume(p,**args);assert r.facets==1 and r.db.execute('SELECT * FROM features').fetchall()==before
    r.insert_facet(1,'content','A different new source passage.');r.db.commit();assert r.facets==2
    r.group(10000);r.db.close()
    with pytest.raises(ValueError):resume(p,**args)


def test_recover_copy_of_interrupted_journal_keeps_original_bytes(tmp_path):
    import os
    import shutil
    import subprocess
    import sys
    original=tmp_path/'original.sqlite'
    code="""
import os,sys
from slm.data.facet_near import FacetStore
s=FacetStore(sys.argv[1],max_bytes=16*1024**2,max_facets=100,max_features=20000,max_shingles=10000)
s.insert_facet(0,'content','A committed original source passage.');s.db.commit()
s.db.execute('PRAGMA cache_size=1')
s.insert_facet(1,'content',' '.join('uncommittedword'+str(i) for i in range(3000)))
os._exit(0)
"""
    environment=dict(os.environ,PYTHONPATH=str(Path.cwd()/'src'))
    subprocess.run([sys.executable,'-c',code,str(original)],check=True,env=environment)
    journal=Path(str(original)+'-journal');assert journal.is_file()
    before=(sha(original),sha(journal));copy=tmp_path/'copy.sqlite'
    shutil.copyfile(original,copy);shutil.copyfile(journal,Path(str(copy)+'-journal'))
    recovered=resume(copy,max_bytes=16*1024**2,max_facets=100,max_features=20000,max_shingles=10000)
    assert recovered.facets==1 and recovered.db.execute('SELECT count(*) FROM facet_sources').fetchone()==(1,)
    recovered.db.close();assert (sha(original),sha(journal))==before
