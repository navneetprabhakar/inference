"""Exact text/family components with immutable witness labels; no admission."""
# Creator: Navneet Prabhakar
import json
from pathlib import Path
import sqlite3
from slm.data.prose_screen import word_key
from slm.data.schema import digest


class ExactFamilies:
    def __init__(self,path,*,max_records,max_bytes):
        self.path=Path(path)
        if self.path.exists():raise FileExistsError('Existing grouping database refused')
        self.max_records=max_records;self.parent=[];self.edges=0
        self.db=sqlite3.connect(self.path)
        self.db.executescript('''PRAGMA synchronous=FULL; PRAGMA journal_mode=DELETE;
CREATE TABLE records(sid INTEGER PRIMARY KEY,eid TEXT UNIQUE,data TEXT,ingredient TEXT,candidate INTEGER,fixed INTEGER,blocked INTEGER,root INTEGER);
CREATE TABLE anchors(kind TEXT,key TEXT,sid INTEGER,PRIMARY KEY(kind,key)) WITHOUT ROWID;
CREATE TABLE edges(a INTEGER,b INTEGER,kind TEXT,key TEXT);
CREATE TABLE components(root INTEGER PRIMARY KEY,group_id TEXT,heldout_priority INTEGER,blocked INTEGER,members INTEGER);
CREATE TABLE status(complete INTEGER);INSERT INTO status VALUES(0);''')
        self.db.execute('PRAGMA max_page_count='+str(max_bytes//4096))

    def find(self,sid):
        while self.parent[sid]!=sid:
            self.parent[sid]=self.parent[self.parent[sid]];sid=self.parent[sid]
        return sid

    def union(self,a,b,kind,key):
        aroot,broot=self.find(a),self.find(b)
        if aroot!=broot:self.parent[max(aroot,broot)]=min(aroot,broot)
        self.db.execute('INSERT INTO edges VALUES(?,?,?,?)',(a,b,kind,key));self.edges+=1

    def add(self,record):
        if len(self.parent)>=self.max_records:raise ValueError('Global record cap reached')
        if (record['fixed_partition'] not in (None,'validation','test') or type(record['candidate']) is not bool or type(record['blocked']) is not bool):raise ValueError('Explicit witness labels required')
        sid=len(self.parent);priority={None:0,'validation':1,'test':2}[record['fixed_partition']]
        self.db.execute('INSERT INTO records VALUES(?,?,?,?,?,?,?,NULL)',(sid,record['id'],json.dumps(record,sort_keys=True,ensure_ascii=False),record['ingredient'],int(record['candidate']),priority,int(record['blocked'])))
        self.parent.append(sid)
        anchors=[('family',f) for f in record['families']]
        for text in record['texts'].values():
            key=word_key(text)
            if len(key)>=16 and len(key.split())>=4:anchors.append(('text',digest(key)))
        for kind,key in sorted(set(anchors)):
            prior=self.db.execute('SELECT sid FROM anchors WHERE kind=? AND key=?',(kind,key)).fetchone()
            if prior:self.union(sid,prior[0],kind,key)
            else:self.db.execute('INSERT INTO anchors VALUES(?,?,?)',(kind,key,sid))
        if sid%512==0:self.db.commit()
        return sid

    def finish(self):
        self.db.executemany('UPDATE records SET root=? WHERE sid=?',((self.find(sid),sid) for sid in range(len(self.parent))))
        self.db.execute('CREATE INDEX record_component ON records(root,eid)')
        for root,fixed,blocked,n in self.db.execute('SELECT root,max(fixed),max(blocked),count(*) FROM records GROUP BY root'):
            names=[r[0] for r in self.db.execute('SELECT eid FROM records WHERE root=? ORDER BY eid',(root,))]
            self.db.execute('INSERT INTO components VALUES(?,?,?,?,?)',(root,digest(names),fixed,blocked,n))
        self.db.execute('UPDATE status SET complete=1');self.db.commit()
        return dict(records=len(self.parent),edges=self.edges,components=self.db.execute('SELECT count(*) FROM components').fetchone()[0],
            candidate_records=self.db.execute('SELECT count(*) FROM records WHERE candidate=1').fetchone()[0],
            candidates_with_heldout_family=self.db.execute('SELECT count(*) FROM records r JOIN components c USING(root) WHERE r.candidate=1 AND c.heldout_priority>0').fetchone()[0],
            candidates_with_blocked_family=self.db.execute('SELECT count(*) FROM records r JOIN components c USING(root) WHERE r.candidate=1 AND c.blocked=1').fetchone()[0])

    def close(self):self.db.close()
