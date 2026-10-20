"""Read-only complete prefix queries against an existing fixed-order near index."""
# Creator: Navneet Prabhakar
import sqlite3
from pathlib import Path
import numpy as np
from slm.data.curation import shingles
from slm.data.schema import digest
from slm.data.prefix_near import prefix_length
from slm.data.prose_screen import word_key


def facets(messages):
    texts={str(i):m['content'] for i,m in enumerate(messages) if m['role']!='system'}
    texts['dialogue']='\n'.join(m['content'] for m in messages)
    return {k:v for k,v in texts.items() if len(word_key(v))>=16 and len(word_key(v).split())>=4}


class Query:
    def __init__(self, root, order, maximum_pairs=5000000):
        self.root=Path(root);self.order=order;self.pairs=0;self.maximum_pairs=maximum_pairs
        self.db=sqlite3.connect('file:'+str((self.root/'near.sqlite').resolve())+'?mode=ro',uri=True)
        self.db.executescript('PRAGMA temp_store=MEMORY; PRAGMA cache_size=-262144; CREATE TEMP TABLE incoming(feat BLOB PRIMARY KEY) WITHOUT ROWID; CREATE TEMP TABLE candidates(sid INTEGER PRIMARY KEY);')
        self.full=(self.root/'full-shingles.bin').open('rb')
    def matches(self,text):
        values=shingles(text);n=len(values)
        if not n:return []
        hashes=sorted({bytes.fromhex(digest(v)) for v in values})
        if len(hashes)!=n:raise ValueError('Shingle hash collision')
        prefix=sorted(hashes,key=lambda h:(self.order.get(h,0),h))[:prefix_length(n)]
        self.db.execute('DELETE FROM incoming');self.db.execute('DELETE FROM candidates')
        self.db.executemany('INSERT INTO incoming VALUES(?)',((h,) for h in prefix))
        self.db.execute('''INSERT OR IGNORE INTO candidates SELECT p.sid FROM incoming i CROSS JOIN prefixes p ON p.feat=i.feat CROSS JOIN records r ON r.sid=p.sid WHERE 20*r.n>=17*? AND 17*r.n<=20*?''',(n,n))
        count=self.db.execute('SELECT count(*) FROM candidates').fetchone()[0]
        if self.pairs+count>self.maximum_pairs:raise ValueError('Finite query-pair cap; no partial acceptance')
        new=np.frombuffer(b''.join(hashes),dtype='S32');found=[]
        for sid,other_n,offset,other_text in self.db.execute('SELECT r.sid,r.n,r.offset,r.data FROM candidates c CROSS JOIN records r ON r.sid=c.sid ORDER BY c.sid'):
            self.pairs+=1;self.full.seek(offset);buf=self.full.read(other_n*32)
            if len(buf)!=other_n*32:raise ValueError('Incomplete immutable full shingle stream')
            overlap=int(np.intersect1d(new,np.frombuffer(buf,dtype='S32'),assume_unique=True).size)
            if 20*overlap>=17*(n+other_n-overlap):
                other=shingles(other_text)
                if 20*len(values&other)>=17*len(values|other):found.append(sid)
        return found
    def close(self):self.full.close();self.db.close()
