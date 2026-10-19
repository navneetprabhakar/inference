"""Complete17/20Jaccard join with a fixed-order prefix index and streamed full sets."""
# Creator: Navneet Prabhakar
import os
from pathlib import Path
import sqlite3
import numpy as np
from slm.data.curation import shingles
from slm.data.schema import digest


def prefix_length(n):return n-(17*n+19)//20+1


class PrefixStore:
    def __init__(self,root,order_counts,*,max_facets=400000,max_features=200000000,
                 max_shingles=1000000,max_pairs=50000000,max_db_bytes=48*1024**3,cache_kib=1048576):
        self.root=Path(root)
        if self.root.exists():raise FileExistsError('Retain existing attempt')
        self.root.mkdir();self.order_counts=dict(order_counts)
        self.facets=self.features=self.pairs=self.postings=0
        self.max_facets,self.max_features,self.max_shingles,self.max_pairs=max_facets,max_features,max_shingles,max_pairs
        self.db=sqlite3.connect(self.root/'near.sqlite')
        self.db.executescript('''PRAGMA journal_mode=DELETE;PRAGMA synchronous=FULL;PRAGMA temp_store=MEMORY;
CREATE TABLE records(sid INTEGER PRIMARY KEY,data TEXT NOT NULL,exact TEXT NOT NULL UNIQUE,n INTEGER NOT NULL,offset INTEGER NOT NULL,prefix_length INTEGER NOT NULL);
CREATE TABLE prefixes(feat BLOB,sid INTEGER,PRIMARY KEY(feat,sid)) WITHOUT ROWID;
CREATE TABLE facet_sources(sid INTEGER,source_sid INTEGER,facet TEXT,PRIMARY KEY(source_sid,facet)) WITHOUT ROWID;
CREATE INDEX by_facet ON facet_sources(sid,source_sid,facet);
CREATE TABLE near_pairs(a INTEGER,b INTEGER,PRIMARY KEY(a,b)) WITHOUT ROWID;
CREATE TEMP TABLE incoming(feat BLOB PRIMARY KEY) WITHOUT ROWID;
CREATE TEMP TABLE candidates(sid INTEGER PRIMARY KEY);
CREATE TABLE status(complete INTEGER);INSERT INTO status VALUES(0);''')
        self.db.execute('PRAGMA cache_size=-'+str(cache_kib))
        self.db.execute('PRAGMA max_page_count='+str(max_db_bytes//4096))
        self.file=(self.root/'full-shingles.bin').open('w+b')

    def insert_facet(self,source_sid,facet,text):
        fingerprint=digest(text)
        prior=self.db.execute('SELECT sid,data FROM records WHERE exact=?',(fingerprint,)).fetchone()
        if prior:
            if prior[1]!=text:raise ValueError('Raw facet hash collision')
            sid=prior[0]
        else:
            values=shingles(text);n=len(values)
            if not 1<=n<=self.max_shingles or self.facets>=self.max_facets or self.features+n>self.max_features:
                raise ValueError('Complete full-feature cap reached; no truncation')
            hashes=sorted({bytes.fromhex(digest(v)) for v in values})
            if len(hashes)!=n:raise ValueError('Within-facet shingle hash collision')
            prefix=sorted(hashes,key=lambda h:(self.order_counts.get(h,0),h))[:prefix_length(n)]
            self.db.execute('DELETE FROM incoming');self.db.execute('DELETE FROM candidates')
            self.db.executemany('INSERT INTO incoming VALUES(?)',((h,) for h in prefix))
            self.db.execute('''INSERT OR IGNORE INTO candidates
SELECT p.sid FROM incoming i CROSS JOIN prefixes p ON p.feat=i.feat
CROSS JOIN records r ON r.sid=p.sid WHERE 20*r.n>=17*? AND 17*r.n<=20*?''',(n,n))
            count=self.db.execute('SELECT count(*) FROM candidates').fetchone()[0]
            if self.pairs+count>self.max_pairs:raise ValueError('Candidate-pair cap reached; no incomplete acceptance')
            new=np.frombuffer(b''.join(hashes),dtype='S32');links=[]
            for a,other_n,offset,other_text in self.db.execute('''SELECT r.sid,r.n,r.offset,r.data FROM candidates c
JOIN records r ON r.sid=c.sid ORDER BY r.sid'''):
                self.pairs+=1;self.file.seek(offset);buf=self.file.read(other_n*32)
                if len(buf)!=other_n*32:raise ValueError('Incomplete full-shingle stream')
                overlap=int(np.intersect1d(new,np.frombuffer(buf,dtype='S32'),assume_unique=True).size)
                if 20*overlap>=17*(n+other_n-overlap):
                    other=shingles(other_text)
                    if 20*len(values&other)>=17*len(values|other):links.append(a)
            self.file.seek(0,2);offset=self.file.tell();self.file.write(b''.join(hashes));self.file.flush()
            sid=self.db.execute('INSERT INTO records(data,exact,n,offset,prefix_length) VALUES(?,?,?,?,?)',
                                (text,fingerprint,n,offset,len(prefix))).lastrowid
            self.db.executemany('INSERT INTO prefixes VALUES(?,?)',((h,sid) for h in prefix))
            self.db.executemany('INSERT INTO near_pairs VALUES(?,?)',((a,sid) for a in links))
            self.facets+=1;self.features+=n;self.postings+=len(prefix)
        self.db.execute('INSERT INTO facet_sources VALUES(?,?,?)',(sid,source_sid,facet))
        if not prior and self.facets%256==0:self.commit()
        return sid

    def commit(self):
        self.file.flush();os.fsync(self.file.fileno());self.db.commit()

    def close(self):
        self.commit();self.file.close();self.db.close()
