"""Full reference-shingle facets using the existing complete prefix join."""
# Creator: Navneet Prabhakar
from pathlib import Path
from slm.data.curation import shingles
from slm.data.schema import digest
from slm.data.staging import Store


class FacetStore(Store):
    def __init__(self,path,*,max_bytes,max_facets,max_features,max_shingles):
        if Path(path).exists():raise FileExistsError('Existing facet database refused')
        super().__init__(path,max_bytes)
        self.max_facets=max_facets;self.max_features=max_features;self.max_shingles=max_shingles
        self.facets=0;self.features=0
        self.db.executescript('''CREATE TABLE facet_sources(sid INTEGER,source_sid INTEGER,facet TEXT,PRIMARY KEY(source_sid,facet)) WITHOUT ROWID;
CREATE INDEX source_by_facet ON facet_sources(sid,source_sid,facet);
CREATE TABLE status(complete INTEGER);INSERT INTO status VALUES(0);''')

    def insert_facet(self,source_sid,facet,text):
        fingerprint=digest(text)
        prior=self.db.execute('SELECT sid,data FROM records WHERE exact=?',(fingerprint,)).fetchone()
        if prior:
            if prior[1]!=text:raise ValueError('Facet digest collision')
            sid=prior[0]
        else:
            values=shingles(text)
            if not values or len(values)>self.max_shingles:raise ValueError('Full facet shingles exceed declared scope')
            if self.facets>=self.max_facets or self.features+len(values)>self.max_features:raise ValueError('Global full-feature budget exceeded')
            eid=str(source_sid).zfill(9)+':'+facet
            cur=self.db.execute('INSERT INTO records(eid,data,family,exact,prompt,fixed,frozen,official) VALUES(?,?,?,?,NULL,0,0,-1)',(eid,text,'facet:'+eid,fingerprint))
            sid=cur.lastrowid;self.db.execute('UPDATE records SET parent=? WHERE sid=?',(sid,sid))
            self.db.execute('INSERT INTO counts VALUES(?,0,?)',(sid,len(values)))
            self.db.execute('DELETE FROM incoming_features')
            self.db.executemany('INSERT INTO incoming_features VALUES(?)',((bytes.fromhex(digest(v)),) for v in sorted(values)))
            self.db.execute('''INSERT INTO dictionary(feat,n_full,n_prompt) SELECT feat,1,0 FROM incoming_features WHERE true
ON CONFLICT(feat) DO UPDATE SET n_full=n_full+1''')
            self.db.execute('''INSERT INTO features SELECT 0,d.fid,? FROM incoming_features i CROSS JOIN dictionary d ON d.feat=i.feat''',(sid,))
            self.facets+=1;self.features+=len(values)
        self.db.execute('INSERT INTO facet_sources VALUES(?,?,?)',(sid,source_sid,facet))
        if self.facets%256==0:self.db.commit()
        self.usage();return sid
