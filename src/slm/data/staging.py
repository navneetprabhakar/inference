"""Disk-backed sample-only JSONL staging with exact similarity grouping."""
# Creator: Navneet Prabhakar
from dataclasses import asdict
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from slm.data.schema import Source,Example,digest
from slm.data.build import read_source,verify
from slm.data.adapters import rows
from slm.data.curation import clean,key_text,exact_key,shingles
from slm.data.holdout import check_training_context
from slm.data.tokenized import sha,stamp

PRIORITY={None:0,'train':0,'validation':1,'test':2}
CANDIDATES='''INSERT INTO candidates SELECT DISTINCT p.sid FROM prefixes mine
 CROSS JOIN prefixes p ON p.kind=mine.kind AND p.fid=mine.fid
 CROSS JOIN records r ON r.sid=p.sid CROSS JOIN counts c ON c.sid=p.sid AND c.kind=p.kind
 WHERE mine.sid=? AND mine.kind=? AND r.eid<? AND 20*c.n>=17*? AND 17*c.n<=20*?'''
LIMITS={'max_input_bytes','max_records','max_record_bytes','max_shingles','max_pair_checks','max_db_bytes'}


def parse(text):
    def pairs(values):
        out={}
        for k,v in values:
            if k in out:raise ValueError('Duplicate JSON field')
            out[k]=v
        return out
    def reject(v):raise ValueError('Nonfinite JSON number')
    return json.loads(text,object_pairs_hook=pairs,parse_constant=reject)


def metadata(path):
    with Path(path).open('rb') as f:value=f.read(16*1024*1024+1)
    if len(value)>16*1024*1024:raise ValueError('Bounded source/frozen metadata required')
    return parse(value)


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)


class Store:
    def __init__(self,path,max_bytes):
        self.db=sqlite3.connect(path);self.peak=0;self.scratch_peak=0;self.pairs=0
        self.db.executescript('''PRAGMA page_size=4096; PRAGMA journal_mode=DELETE; PRAGMA synchronous=FULL;
 PRAGMA cache_size=-8192; PRAGMA temp_store=FILE;
 CREATE TABLE records(sid INTEGER PRIMARY KEY,eid TEXT UNIQUE NOT NULL,data TEXT NOT NULL,family TEXT NOT NULL,
 exact TEXT NOT NULL,prompt TEXT,fixed INTEGER NOT NULL,frozen INTEGER NOT NULL,official INTEGER NOT NULL,parent INTEGER,rank INTEGER DEFAULT 0,
 root INTEGER,group_id TEXT,split TEXT);
 CREATE INDEX families ON records(family); CREATE INDEX exacts ON records(exact); CREATE INDEX prompts ON records(prompt);
 CREATE TABLE seen(eid TEXT PRIMARY KEY); CREATE TABLE incoming(eid TEXT PRIMARY KEY);
 CREATE TABLE dictionary(fid INTEGER PRIMARY KEY,feat BLOB NOT NULL UNIQUE,n_full INTEGER NOT NULL,n_prompt INTEGER NOT NULL);
 CREATE TABLE features(kind INTEGER,fid INTEGER,sid INTEGER,PRIMARY KEY(kind,fid,sid)) WITHOUT ROWID;
 CREATE INDEX by_record ON features(sid,kind,fid);
 CREATE TABLE counts(sid INTEGER,kind INTEGER,n INTEGER,PRIMARY KEY(sid,kind)) WITHOUT ROWID;
 CREATE TEMP TABLE incoming_features(feat BLOB PRIMARY KEY) WITHOUT ROWID; PRAGMA temp.cache_size=-2048;
 CREATE TABLE candidates(sid INTEGER PRIMARY KEY);
 CREATE TABLE near_pairs(a INTEGER,b INTEGER,PRIMARY KEY(a,b)) WITHOUT ROWID;
 CREATE TABLE groups(root INTEGER PRIMARY KEY,group_id TEXT,split TEXT);
 CREATE TABLE winners(exact TEXT PRIMARY KEY,eid TEXT);
 CREATE TABLE heldout(family TEXT PRIMARY KEY,split TEXT);
 ''')
        self.db.execute('PRAGMA max_page_count='+str(max_bytes//4096))
    def usage(self):
        value=self.db.execute('PRAGMA page_count').fetchone()[0]*4096;self.peak=max(self.peak,value)
        scratch=self.db.execute('PRAGMA temp.page_count').fetchone()[0]*self.db.execute('PRAGMA temp.page_size').fetchone()[0]
        self.scratch_peak=max(self.scratch_peak,scratch);return value
    def find(self,sid):
        path=[]
        while True:
            parent=self.db.execute('SELECT parent FROM records WHERE sid=?',(sid,)).fetchone()[0]
            if parent==sid:break
            path.append(sid);sid=parent
        self.db.executemany('UPDATE records SET parent=? WHERE sid=?',((sid,p) for p in path));return sid
    def union(self,a,b):
        a,b=self.find(a),self.find(b)
        if a==b:return
        ar=self.db.execute('SELECT rank FROM records WHERE sid=?',(a,)).fetchone()[0]
        br=self.db.execute('SELECT rank FROM records WHERE sid=?',(b,)).fetchone()[0]
        if ar<br or (ar==br and a>b):a,b=b,a;ar,br=br,ar
        self.db.execute('UPDATE records SET parent=? WHERE sid=?',(a,b))
        if ar==br:self.db.execute('UPDATE records SET rank=rank+1 WHERE sid=?',(a,))
    def insert(self,item,fixed,frozen,max_shingles):
        text=key_text(item);prompt=next((m['content'] for m in item.messages if m['role']=='user'),None)
        fingerprint=exact_key(item);pkey=digest(' '.join(prompt.casefold().split())) if prompt is not None else None
        cur=self.db.execute('INSERT INTO records(eid,data,family,exact,prompt,fixed,frozen,official) VALUES(?,?,?,?,?,?,?,?)',
            (item.example_id,canonical(item.to_dict()),item.parent_group_id,fingerprint,pkey,fixed,int(frozen),{None:-1,'train':0,'validation':1,'test':2}[item.official_split]))
        sid=cur.lastrowid;self.db.execute('UPDATE records SET parent=? WHERE sid=?',(sid,sid))
        for kind,content in [(0,text),(1,prompt)]:
            if content is None:continue
            values=shingles(content)
            if len(values)>max_shingles:raise ValueError('Per-record feature budget exceeded; no truncation')
            self.db.execute('INSERT INTO counts VALUES(?,?,?)',(sid,kind,len(values)))
            self.db.execute('DELETE FROM incoming_features')
            self.db.executemany('INSERT INTO incoming_features VALUES(?)',((bytes.fromhex(digest(v)),) for v in sorted(values)))
            self.db.execute('''INSERT INTO dictionary(feat,n_full,n_prompt) SELECT feat,?,? FROM incoming_features WHERE true
 ON CONFLICT(feat) DO UPDATE SET n_full=n_full+excluded.n_full,n_prompt=n_prompt+excluded.n_prompt''',(int(kind==0),int(kind==1)))
            self.db.execute('''INSERT INTO features SELECT ?,d.fid,? FROM incoming_features i
 CROSS JOIN dictionary d ON d.feat=i.feat''',(kind,sid))
        if sid%256==0:self.db.commit()
        self.usage();return sid
    def group(self,max_checks):
        # Stable global frequency order; prefix length n-ceil(.85*n)+1.
        # Every candidate is still verified against its full shingle sets.
        self.db.executescript('''CREATE TABLE prefixes(kind INTEGER,fid INTEGER,sid INTEGER,PRIMARY KEY(kind,fid,sid)) WITHOUT ROWID;
 INSERT INTO prefixes SELECT kind,fid,sid FROM (
 SELECT f.kind,f.fid,f.sid,c.n,row_number() OVER(PARTITION BY c.sid,c.kind ORDER BY CASE c.kind WHEN 0 THEN q.n_full ELSE q.n_prompt END,q.feat) AS position
 FROM counts c CROSS JOIN features f ON f.sid=c.sid AND f.kind=c.kind CROSS JOIN dictionary q ON q.fid=f.fid)
 WHERE position<=n-(17*n+19)/20+1;
 CREATE INDEX prefix_record ON prefixes(sid,kind,fid);''')
        for sid,eid,family,exact,prompt in self.db.execute('SELECT sid,eid,family,exact,prompt FROM records ORDER BY eid'):
            for field,value in [('family',family),('exact',exact),('prompt',prompt)]:
                if value is None:continue
                previous=self.db.execute('SELECT sid FROM records WHERE '+field+'=? AND eid<? ORDER BY eid LIMIT 1',(value,eid)).fetchone()
                if previous:self.union(sid,previous[0])
            for kind,n in self.db.execute('SELECT kind,n FROM counts WHERE sid=?',(sid,)):
                self.db.execute('DELETE FROM candidates')
                self.db.execute(CANDIDATES,(sid,kind,eid,n,n))
                for other,m in self.db.execute('SELECT c.sid,n.n FROM candidates c JOIN counts n ON n.sid=c.sid AND n.kind=? ORDER BY c.sid',(kind,)):
                    self.pairs+=1
                    if self.pairs>max_checks:raise ValueError('Exact candidate comparison budget exceeded; no partial grouping')
                    overlap=self.db.execute('SELECT count(*) FROM features a CROSS JOIN features b ON a.kind=b.kind AND a.fid=b.fid WHERE a.sid=? AND b.sid=? AND a.kind=?',(sid,other,kind)).fetchone()[0]
                    if 20*overlap>=17*(n+m-overlap):
                        self.union(sid,other);self.db.execute('INSERT OR IGNORE INTO near_pairs VALUES(?,?)',(min(sid,other),max(sid,other)))
            if sid%256==0:self.db.commit()
            self.usage()
        for sid, in self.db.execute('SELECT sid FROM records'):self.db.execute('UPDATE records SET root=? WHERE sid=?',(self.find(sid),sid))
        self.db.execute('CREATE INDEX component ON records(root,eid)');self.db.commit()
    def splits(self,seed):
        for root, in self.db.execute('SELECT DISTINCT root FROM records ORDER BY root'):
            h=hashlib.sha256();h.update(b'[');first=True;fixed=0
            for eid,priority in self.db.execute('SELECT eid,fixed FROM records WHERE root=? ORDER BY eid',(root,)):
                if not first:h.update(b',')
                h.update(canonical(eid).encode());first=False;fixed=max(fixed,priority)
            h.update(b']');group=h.hexdigest();bucket=int(hashlib.sha256((seed+group).encode()).hexdigest()[:16],16)%100
            split=('validation' if fixed==1 else 'test') if fixed else 'test' if bucket<5 else 'validation' if bucket<10 else 'train'
            self.db.execute('INSERT INTO groups VALUES(?,?,?)',(root,group,split))
            self.db.execute('UPDATE records SET group_id=?,split=? WHERE root=?',(group,split,root))
        # One exact representative; group-level strongest partition already includes every copy.
        for exact,eid in self.db.execute('SELECT exact,eid FROM records ORDER BY frozen DESC,official DESC,eid'):
            self.db.execute('INSERT OR IGNORE INTO winners VALUES(?,?)',(exact,eid))
        self.db.commit();self.usage()


def stage(specs,output,*,limits,seed='slm-splits-v1',shard_size=1000,frozen_dataset=None):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    if set(limits)!=LIMITS or any(type(v) is not int or v<1 for v in limits.values()) or limits['max_db_bytes']<1024*1024:
        raise ValueError('Complete positive staging limits required; database minimum 1 MiB')
    if type(shard_size) is not int or shard_size<1 or not isinstance(seed,str) or not seed:raise ValueError('Explicit valid shard size/seed required')
    if not isinstance(specs,list) or not 1<=len(specs)<=1024:raise ValueError('One to 1024 pinned local inputs required')
    prepared=[];sources={};evidence={};stamps={};input_hashes={};total=0
    for code in (Path(__file__),Path(__file__).with_name('curation.py')):stamps[code.resolve()]=stamp(code)
    for spec in specs:
        if set(spec)-{'path','sha256','source_record','adapter','official_split','partition_map','partition_map_sha256'} or not {'path','sha256','source_record','adapter'}<=set(spec):raise ValueError('Pinned staging input fields required')
        path=Path(spec['path']);source_path=Path(spec['source_record']);meta=metadata(source_path)
        for name in ('card','license'):
            p=source_path.parent/meta['evidence_files'][name]
            if p.stat().st_size>2*1024*1024:raise ValueError('Source evidence byte limit exceeded')
            stamps[p.resolve()]=stamp(p)
        source=read_source(source_path);stamps[source_path.resolve()]=stamp(source_path)
        if source.source_id in sources and sources[source.source_id]!=source:raise ValueError('Conflicting pinned source')
        sources[source.source_id]=source;evidence[source.source_id]=(source_path.parent/meta['evidence_files']['card'],source_path.parent/meta['evidence_files']['license'])
        total+=path.stat().st_size
        if total>limits['max_input_bytes']:raise ValueError('Total input byte budget exceeded')
        stamps[path.resolve()]=stamp(path)
        if sha(path)!=spec['sha256']:raise ValueError('Pinned input checksum differs')
        mapping=None;mapping_hash=None
        if spec.get('partition_map') is not None:
            p=Path(spec['partition_map']);metadata(p);stamps[p.resolve()]=stamp(p)
            from slm.data.partitions import load_mapping
            mapping,mapping_hash=load_mapping(p,spec.get('partition_map_sha256'),source,spec['sha256'])
        elif spec.get('partition_map_sha256') is not None:raise ValueError('Partition digest requires projection')
        if spec['adapter']=='oasst' and mapping is None:raise ValueError('OASST staging requires verified per-tree official projection')
        prepared.append((spec,path,source,mapping,mapping_hash));input_hashes[str(path)]=spec['sha256']
    frozen_sources={};frozen_groups={};frozen_manifest=None
    if frozen_dataset is not None:
        root=Path(frozen_dataset);metadata(root/'manifest.json');verify(root);frozen_manifest=sha(root/'manifest.json')
        frozen_sources={k:Source(**v) for k,v in metadata(root/'sources.json').items()}
        frozen_groups=metadata(root/'heldout-groups.json')
        if any(v not in ('validation','test') for v in frozen_groups.values()):raise ValueError('Frozen groups must be held out')
        for name,source in frozen_sources.items():
            if name not in sources or source!=sources[name]:raise ValueError('Explicit matching source evidence required for every frozen source')
        for p in root.iterdir():
            if p.is_file():stamps[p.resolve()]=stamp(p)
    def unchanged():
        for path,before in stamps.items():
            if stamp(path)!=before:raise ValueError('Staging input/evidence changed')
    unchanged();output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.corpus-stage-',dir=output.parent))
    store=None;rejected=Counter();ingested=0
    try:
        store=Store(temp/'work.sqlite',limits['max_db_bytes']);db=store.db
        def add(item,frozen=False):
            nonlocal ingested
            ingested+=1
            if ingested>limits['max_records']:raise ValueError('Record budget exceeded')
            if any(not isinstance(v,str) or not v or len(v.encode())>4096 for v in (item.example_id,item.parent_group_id)):
                raise ValueError('Bounded canonical identities required')
            source=sources.get(item.source)
            if source is None or item.source_revision!=source.revision or item.license_record!=digest(asdict(source)):raise ValueError('Record/source provenance differs')
            if not frozen:
                try:db.execute('INSERT INTO incoming VALUES(?)',(item.example_id,))
                except sqlite3.IntegrityError as exc:raise ValueError('Duplicate input example identity') from exc
            protected=db.execute('SELECT 1 FROM records WHERE eid=? AND frozen=1',(item.example_id,)).fetchone()
            try:item=clean(item)
            except ValueError as exc:
                if frozen or protected:raise ValueError('Frozen held-out record cannot be dropped') from exc
                rejected[str(exc)]+=1;return
            existing=db.execute('SELECT data,frozen FROM records WHERE eid=?',(item.example_id,)).fetchone()
            if existing and existing[1] and not frozen:
                prior=parse(existing[0]);current=item.to_dict()
                for key in ('messages','source','source_revision','license_record','parent_group_id','task','style','content_category','language','lineage','upstream_references','official_split'):
                    if prior[key]!=current[key]:raise ValueError('Frozen example changed')
                return
            try:db.execute('INSERT INTO seen VALUES(?)',(item.example_id,))
            except sqlite3.IntegrityError as exc:raise ValueError('Duplicate input example identity') from exc
            if source.review_status=='excluded':rejected['excluded_source']+=1;return
            if item.language not in ('en','unknown'):rejected['declared_non_english']+=1;return
            if item.official_split not in PRIORITY or item.split not in PRIORITY:raise ValueError('Unknown partition')
            if item.source=='OpenAssistant/oasst2':
                from slm.data.review import oasst_mapping
                oasst_mapping(item.to_dict())
            if 'teacher_bridge' in item.validation_results:
                from slm.teacher.bridge import review_requirements
                review_requirements(item.to_dict())
            fixed=max(PRIORITY[item.official_split],PRIORITY[item.split] if frozen or item.split in ('validation','test') else 0,PRIORITY[frozen_groups.get(item.parent_group_id)])
            try:check_training_context(item.messages,(item.example_id,item.parent_group_id))
            except ValueError:fixed=2
            store.insert(item,fixed,frozen,limits['max_shingles'])
        def lines(path):
            with path.open('rb') as f:
                while True:
                    line=f.readline(limits['max_record_bytes']+1)
                    if not line:break
                    if len(line)>limits['max_record_bytes']:raise ValueError('Record byte budget exceeded; no truncation')
                    if line.strip():yield parse(line)
        if frozen_dataset is not None:
            for split in ('validation','test'):
                for path in sorted(Path(frozen_dataset).glob(split+'-*.jsonl')):
                    for row in lines(path):add(Example(**row),True)
        for spec,path,source,mapping,mapping_hash in prepared:
            used=set()
            for row in lines(path):
                if spec['adapter']=='canonical':
                    item=Example(**row)
                    if item.source!=source.source_id:raise ValueError('Canonical input source differs')
                    adapted=[item]
                else:
                    projection=None
                    if mapping is not None:
                        id=row['message_tree_id']
                        if id in used or id not in mapping:raise ValueError('Official projection membership differs')
                        used.add(id);projection={id:mapping[id]}
                    adapted=rows(source,[row],spec['adapter'],spec.get('official_split'),projection,mapping_hash)
                for item in adapted:add(item)
            if mapping is not None and used!=set(mapping):raise ValueError('Official projection coverage differs')
        unchanged();store.group(limits['max_pair_checks']);store.splits(seed)
        counts=Counter();source_counts=Counter();language=Counter();categories=Counter();exposure_max=0;handles={};outrows=Counter()
        # Exposure counts stay on disk, not a corpus-sized Python dictionary.
        db.execute('CREATE TABLE exposures(source TEXT,node TEXT,n INTEGER,PRIMARY KEY(source,node)) WITHOUT ROWID')
        try:
            for data,group,split,family in db.execute('SELECT r.data,r.group_id,r.split,r.family FROM records r JOIN winners w ON w.eid=r.eid ORDER BY r.split,r.eid'):
                row=parse(data);row['split']=split;row['validation_results']['split_group']=group
                index=outrows[split]//shard_size
                if index>=10000:raise ValueError('Per-split shard metadata budget exceeded')
                category=row['content_category']
                if not isinstance(category,str) or len(category.encode())>128:raise ValueError('Bounded content label required')
                if category not in categories and len(categories)>=1024:raise ValueError('Content label cardinality budget exceeded')
                if split not in handles or outrows[split]%shard_size==0:
                    if split in handles:handles[split].close()
                    handle=(temp/f'{split}-{index:06d}.jsonl').open('w');handles[split]=handle
                handles[split].write(canonical(row)+'\n');outrows[split]+=1;counts[split]+=1
                source_counts[row['source']]+=1;language[row['language']]+=1;categories[row['content_category']]+=1
                for node in row['lineage']:
                    db.execute('INSERT INTO exposures VALUES(?,?,1) ON CONFLICT(source,node) DO UPDATE SET n=n+1',(row['source'],node))
            for family,priority in db.execute('SELECT family,max(CASE split WHEN "test" THEN 2 WHEN "validation" THEN 1 ELSE 0 END) FROM records GROUP BY family'):
                if priority:db.execute('INSERT OR REPLACE INTO heldout VALUES(?,?)',(family,'test' if priority==2 else 'validation'))
            for family,split in frozen_groups.items():
                db.execute('INSERT INTO heldout VALUES(?,?) ON CONFLICT(family) DO UPDATE SET split=CASE WHEN heldout.split="test" OR excluded.split="test" THEN "test" ELSE "validation" END',(family,split))
            exposure_max=db.execute('SELECT coalesce(max(n),0) FROM exposures').fetchone()[0]
            db.commit();store.usage()
        finally:
            for value in handles.values():value.close()
        with (temp/'heldout-groups.json').open('w') as f:
            f.write('{');first=True
            for family,split in db.execute('SELECT family,split FROM heldout ORDER BY family'):
                f.write(('' if first else ',')+canonical(family)+':'+canonical(split));first=False
            f.write('}\n')
        report={'version':1,'release':'sample_only','staging':'sqlite-exact-prefix-jaccard-v1','feature_storage':'interned-sha256-postings-v1','input_examples':ingested,
            'retained_examples':sum(counts.values()),'splits':dict(counts),'sources':dict(source_counts),'language_labels':dict(language),
            'content_categories':dict(categories),'rejections':dict(rejected),'limits':limits,'input_bytes':total,
            'exact_duplicates_removed':db.execute('SELECT count(*) FROM records').fetchone()[0]-sum(counts.values()),
            'candidate_lookup_plan':db.execute('EXPLAIN QUERY PLAN '+CANDIDATES,(-1,0,'',0,0)).fetchall(),
            'near_pairs_grouped':db.execute('SELECT count(*) FROM near_pairs').fetchone()[0],'candidate_comparisons':store.pairs,
            'peak_record_scratch_database_bytes':store.scratch_peak,
            'unique_shingle_hashes':db.execute('SELECT count(*) FROM dictionary').fetchone()[0],
            'signature_memberships':db.execute('SELECT count(*) FROM features').fetchone()[0],
            'peak_database_allocated_bytes':store.peak,'max_shared_message_exposure':exposure_max,'split_seed':seed,
            'source_rights_approved':False,'training_eligible':False,'frozen_dataset_manifest_sha256':frozen_manifest,
            'scope':'Local JSONL staging only; exact hash-shingle Jaccard groups, bounded metadata, no semantic/English/rights clearance or corpus admission.'}
        store.db.close();store=None;(temp/'work.sqlite').unlink()
        for name,value in [('sources.json',{k:asdict(v) for k,v in sorted(sources.items())}),('report.json',report)]:
            (temp/name).write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
        evidence_index={}
        for i,(name,paths) in enumerate(sorted(evidence.items())):
            evidence_index[name]={}
            for kind,path in zip(('card','license'),paths):
                filename=f'evidence-{i:03d}-{kind}.txt';shutil.copyfile(path,temp/filename);evidence_index[name][kind]=filename
                expected=sources[name].card_sha256 if kind=='card' else sources[name].license_text_sha256
                if sha(temp/filename)!=expected:raise ValueError('Source evidence changed during staging')
        (temp/'evidence.json').write_text(canonical(evidence_index)+'\n')
        unchanged()
        manifest={'version':1,'release':'sample_only','kind':'disk-backed-corpus-stage-v1','inputs':input_hashes,
            'implementation_sha256':sha(__file__),'reference_cleaner_sha256':sha(Path(__file__).with_name('curation.py')),
            'files':{p.name:sha(p) for p in sorted(temp.iterdir()) if p.is_file()}}
        (temp/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n');metadata(temp/'manifest.json');verify(temp);os.rename(temp,output)
        return report
    except BaseException:
        if store is not None:store.db.close()
        shutil.rmtree(temp,ignore_errors=True);raise


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();spec=metadata(a.spec)
    if set(spec)-{'inputs','limits','seed','shard_size','frozen_dataset'}:raise ValueError('Unknown staging settings')
    base=Path(a.spec).resolve().parent
    for item in spec['inputs']:
        for key in ('path','source_record','partition_map'):
            if item.get(key) is not None:item[key]=str(base/item[key])
    if spec.get('frozen_dataset') is not None:spec['frozen_dataset']=str(base/spec['frozen_dataset'])
    r=stage(spec.pop('inputs'),a.output,**spec);print(json.dumps({k:r[k] for k in ('release','input_examples','retained_examples','training_eligible')},sort_keys=True))


if __name__=='__main__':main()
