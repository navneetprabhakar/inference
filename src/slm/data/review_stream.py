"""Disk-backed explicit-row review releases; never infer corpus approval."""
# Creator: Navneet Prabhakar
from collections.abc import Mapping
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sqlite3
import tempfile
from slm.data.build import verify
from slm.data.review import check_source_reviews,check_entry,PRIORITY
from slm.data.schema import digest
from slm.data.staging import canonical,metadata,parse
from slm.data.tokenized import sha,stamp

DEFAULT_LIMITS=dict(max_input_bytes=256*1024*1024,max_records=100000,max_record_bytes=1024*1024,max_db_bytes=1024*1024*1024)
HEADER={'version','scope','dataset_manifest_sha256','reviewer','human_attestation','source_reviews','decisions_sha256','legacy_packet_sha256'}


def limits_checked(value):
    value=dict(value)
    if set(value)!=set(DEFAULT_LIMITS) or any(type(v) is not int or v<1 for v in value.values()) or value['max_db_bytes']<1024*1024:
        raise ValueError('Complete positive review limits required; database minimum 1 MiB')
    return value


def lines(path,limits):
    count=0
    with Path(path).open('rb') as f:
        while True:
            line=f.readline(limits['max_record_bytes']+1)
            if not line:break
            if len(line)>limits['max_record_bytes']:raise ValueError('Review row byte limit exceeded')
            if line.strip():
                count+=1
                if count>limits['max_records']:raise ValueError('Review record limit exceeded')
                yield parse(line)


def guarded(roots,limits):
    paths={}
    for root in roots:
        for path in Path(root).iterdir():
            if not path.is_file() or path.is_symlink():raise ValueError('Flat regular review artifacts required')
            paths[path.resolve()]=stamp(path)
    if sum(v[0] for v in paths.values())>limits['max_input_bytes']:raise ValueError('Review input byte limit exceeded')
    for name in ('review_stream.py','review.py','research_admission.py','context.py','quality_audit.py','build.py','staging.py','holdout.py'):
        path=Path(__file__).with_name(name);paths[path.resolve()]=stamp(path)
    def check():
        for path,before in paths.items():
            if stamp(path)!=before:raise ValueError('Review inputs or implementation changed')
    return check


def header_checked(header,sources,ledger):
    expected=HEADER|({'review_mode','review_authorization'} if header.get('review_mode')=='delegated_expert' else set())
    if set(header)!=expected or type(header['version']) is not int or header['version']!=2 or header['scope']!='explicit_rows_only':
        raise ValueError('Explicit-row review v2 required; corpus inference refused')
    if sha(ledger)!=header['decisions_sha256']:raise ValueError('Review ledger checksum differs')
    check_source_reviews({**header,'version':1},sources)
    return digest(header)


def export_packet(packet_file,output):
    """Bounded legacy conversion only. Pending/rejected decisions stay unchanged."""
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    packet_file=Path(packet_file);before=stamp(packet_file);packet=metadata(packet_file)
    if packet.get('version')!=1:raise ValueError('Legacy packet v1 required')
    output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.review-export-',dir=output.parent))
    try:
        with (temp/'decisions.jsonl').open('w') as f:
            for key,entry in sorted(packet['examples'].items()):
                if key!=entry['record']['example_id'] or digest(entry['record'])!=entry['record_sha256']:raise ValueError('Legacy review record differs')
                f.write(canonical(entry)+'\n')
        header={k:deepcopy(packet[k]) for k in ('dataset_manifest_sha256','reviewer','human_attestation','source_reviews')}
        if packet.get('review_mode')=='delegated_expert':
            header.update(review_mode=packet['review_mode'],review_authorization=deepcopy(packet['review_authorization']))
        elif packet.get('review_mode','human')!='human' or 'review_authorization' in packet:
            raise ValueError('Unknown or inconsistent review authority')
        header.update(version=2,scope='explicit_rows_only',decisions_sha256=sha(temp/'decisions.jsonl'),legacy_packet_sha256=sha(packet_file))
        (temp/'header.json').write_text(canonical(header)+'\n')
        if stamp(packet_file)!=before:raise ValueError('Legacy packet changed during export')
        os.rename(temp,output)
        return dict(decisions=len(packet['examples']),human_attestation=header['human_attestation'],scope=header['scope'])
    except BaseException:shutil.rmtree(temp,ignore_errors=True);raise


class Index(Mapping):
    def __init__(self,path,limits):
        self.db=sqlite3.connect(path);self.limits=limits;self.count=0;self.peak=0
        self.db.executescript('''PRAGMA page_size=4096; PRAGMA cache_size=-8192; PRAGMA temp_store=FILE;
 CREATE TABLE snapshot(eid TEXT PRIMARY KEY,data TEXT) WITHOUT ROWID;
 CREATE TABLE decisions(eid TEXT PRIMARY KEY) WITHOUT ROWID;
 CREATE TABLE groups(gid TEXT PRIMARY KEY,priority INTEGER) WITHOUT ROWID;
 CREATE TABLE approved(eid TEXT PRIMARY KEY,data TEXT,gid TEXT,split TEXT,seen INTEGER DEFAULT 0) WITHOUT ROWID;
 CREATE INDEX approved_split ON approved(split,eid);
 CREATE TABLE leaf_seen(eid TEXT PRIMARY KEY) WITHOUT ROWID;''')
        self.db.execute('PRAGMA max_page_count='+str(limits['max_db_bytes']//4096))
    def tick(self):
        self.count+=1
        if self.count%256==0:self.db.commit()
        self.peak=max(self.peak,self.db.execute('PRAGMA page_count').fetchone()[0]*4096)
    def __getitem__(self,key):
        row=self.db.execute('SELECT data FROM approved WHERE eid=? AND split="train"',(key,)).fetchone()
        if row is None:raise KeyError(key)
        return parse(row[0])
    def __len__(self):return self.db.execute('SELECT count(*) FROM approved WHERE split="train"').fetchone()[0]
    def __iter__(self):
        for key, in self.db.execute('SELECT eid FROM approved WHERE split="train" ORDER BY eid'):yield key
    def values(self):
        for data, in self.db.execute('SELECT data FROM approved WHERE split="train" ORDER BY eid'):yield parse(data)
    def clear_seen(self):self.db.execute('DELETE FROM leaf_seen')
    def claim(self,key):
        try:self.db.execute('INSERT INTO leaf_seen VALUES(?)',(key,));self.tick();return True
        except sqlite3.IntegrityError:return False
    def ingest_reviews(self,header,ledger,sources,snapshot=False):
        binding=header_checked(header,sources,ledger);count=0
        for entry in lines(ledger,self.limits):
            count+=1;key=entry['record']['example_id']
            try:self.db.execute('INSERT INTO decisions VALUES(?)',(key,))
            except sqlite3.IntegrityError as exc:raise ValueError('Duplicate review identity') from exc
            if snapshot:
                prior=self.db.execute('SELECT data FROM snapshot WHERE eid=?',(key,)).fetchone()
                if prior is None or prior[0]!=canonical(entry['record']):raise ValueError('Review does not match frozen input record')
            mode=header.get('review_mode','human')
            item,group,partitions=check_entry(key,entry,sources,header['source_reviews'],binding,mode)
            self.db.execute('INSERT INTO groups VALUES(?,?) ON CONFLICT(gid) DO UPDATE SET priority=max(priority,excluded.priority)',(group,max(PRIORITY[p] for p in partitions)))
            if item is not None:
                receipt_key='human_review' if mode=='human' else 'delegated_expert_review'
                item['validation_results'][receipt_key]={'review_schema_version':2,'review_binding_sha256':binding,'reviewed_record_sha256':entry['record_sha256']}
                self.db.execute('INSERT INTO approved(eid,data,gid,split) VALUES(?,?,?,?)',(key,canonical(item),group,item['split']))
            self.tick()
        if not self.db.execute('SELECT 1 FROM approved LIMIT 1').fetchone():raise ValueError('No approved records; no training release')
        for key,data,priority in self.db.execute('SELECT a.eid,a.data,g.priority FROM approved a JOIN groups g ON g.gid=a.gid ORDER BY a.eid'):
            item=parse(data);item['split']=next(k for k,v in PRIORITY.items() if v==priority)
            if item['split']=='train':
                from slm.data.holdout import check_training_context
                check_training_context(item['messages'],(key,item['parent_group_id'],item['validation_results']['split_group']))
            self.db.execute('UPDATE approved SET data=?,split=? WHERE eid=?',(canonical(item),item['split'],key));self.tick()
        self.db.commit();return count
    def shard_rows(self,root,table):
        total=0
        for split in PRIORITY:
            for path in sorted(Path(root).glob(split+'-*.jsonl')):
                for item in lines(path,self.limits):
                    total+=1
                    if total>self.limits['max_records']:raise ValueError('Review record limit exceeded')
                    key=item['example_id']
                    if item['split']!=split:raise ValueError('Shard partition differs')
                    if table=='snapshot':
                        try:self.db.execute('INSERT INTO snapshot VALUES(?,?)',(key,canonical(item)))
                        except sqlite3.IntegrityError as exc:raise ValueError('Duplicate snapshot identity') from exc
                    else:
                        expected=self.db.execute('SELECT data,seen FROM approved WHERE eid=?',(key,)).fetchone()
                        if expected is None or expected[1] or expected[0]!=canonical(item):raise ValueError('Released records differ from approved review')
                        self.db.execute('UPDATE approved SET seen=1 WHERE eid=?',(key,))
                    self.tick()
        self.db.commit()
        if table!='snapshot' and self.db.execute('SELECT 1 FROM approved WHERE seen=0 LIMIT 1').fetchone():raise ValueError('Approved released record missing')
        return total


def release(dataset,review,output,*,limits,shard_size=1000):
    dataset,review,output=map(Path,(dataset,review,output));limits=limits_checked(limits)
    if output.exists():raise FileExistsError(output)
    if type(shard_size) is not int or shard_size<1:raise ValueError('Positive review shard size required')
    if {p.name for p in review.iterdir()}!={'header.json','decisions.jsonl'}:raise ValueError('Review bundle file set differs')
    metadata(dataset/'manifest.json');check=guarded([dataset,review],limits);verify(dataset)
    header=metadata(review/'header.json');sources=metadata(dataset/'sources.json')
    if sha(dataset/'manifest.json')!=header['dataset_manifest_sha256']:raise ValueError('Reviewed dataset manifest differs')
    header_checked(header,sources,review/'decisions.jsonl');check()
    output.parent.mkdir(parents=True,exist_ok=True);temp=Path(tempfile.mkdtemp(prefix='.review-stream-',dir=output.parent));index=None
    try:
        index=Index(temp/'work.sqlite',limits);snapshot_count=index.shard_rows(dataset,'snapshot')
        count=index.ingest_reviews(header,review/'decisions.jsonl',sources,True);check()
        splits=Counter();handle=None;current=None
        try:
            for data,split in index.db.execute('SELECT data,split FROM approved ORDER BY split,eid'):
                number=splits[split]//shard_size
                if number>=10000:raise ValueError('Review shard metadata limit exceeded')
                if current!=(split,number):
                    if handle:handle.close()
                    handle=(temp/f'{split}-{number:06d}.jsonl').open('w');current=(split,number)
                handle.write(data+'\n');splits[split]+=1
        finally:
            if handle:handle.close()
        report=dict(release='training',review_schema_version=2,scope='explicit_rows_only',snapshot_records=snapshot_count,
                    reviewed_entries=count,approved_examples=sum(splits.values()),splits=dict(splits),peak_database_allocated_bytes=index.peak,
                    limitation='Validates explicit attestations and integrity, not human judgment, legal clearance or unreviewed corpus rows.')
        index.db.close();index=None;(temp/'work.sqlite').unlink()
        for source,name in ((review/'header.json','review-header.json'),(review/'decisions.jsonl','review-decisions.jsonl'),(dataset/'sources.json','sources.json')):shutil.copyfile(source,temp/name)
        (temp/'report.json').write_text(canonical(report)+'\n');check()
        manifest=dict(version=1,release='training',review_schema_version=2,parent_dataset_manifest_sha256=header['dataset_manifest_sha256'],
                      review_binding_sha256=digest(header),review_decisions_sha256=header['decisions_sha256'],verification_limits=limits,
                      files={p.name:sha(p) for p in sorted(temp.iterdir()) if p.is_file()})
        (temp/'manifest.json').write_text(canonical(manifest)+'\n');metadata(temp/'manifest.json');verify(temp);os.rename(temp,output)
        return report
    except BaseException:
        if index is not None:index.db.close()
        shutil.rmtree(temp,ignore_errors=True);raise


@contextmanager
def open_checked(root,limits=None):
    """Fully verify before exposing train-only records or random lookups."""
    root=Path(root);manifest=metadata(root/'manifest.json')
    if manifest.get('release')=='research_training' and manifest.get('review_schema_version')==3:
        from slm.data.research_admission import open_research
        with open_research(root,limits) as index:yield index
        return
    if manifest.get('release')!='training' or manifest.get('review_schema_version') not in (1,2):raise ValueError('Reviewed training release required; sample-only data is refused')
    limits=limits_checked(limits or manifest.get('verification_limits',DEFAULT_LIMITS));check=guarded([root],limits);verify(root)
    with tempfile.TemporaryDirectory(prefix='slm-checked-review-') as temp:
        index=Index(Path(temp)/'index.sqlite',limits)
        try:
            if manifest['review_schema_version']==2:
                header=metadata(root/'review-header.json');sources=metadata(root/'sources.json')
                if (digest(header)!=manifest['review_binding_sha256'] or header['dataset_manifest_sha256']!=manifest['parent_dataset_manifest_sha256']
                    or header['decisions_sha256']!=manifest['review_decisions_sha256']):raise ValueError('Review lineage differs')
                index.ingest_reviews(header,root/'review-decisions.jsonl',sources)
                index.shard_rows(root,'released')
            else:
                # Legacy bounded packet path remains exact; corpus-sized packets must migrate.
                metadata(root/'review.json')
                from slm.data.review import training_examples
                for item in training_examples(root):
                    index.db.execute('INSERT INTO approved(eid,data,gid,split) VALUES(?,?,?,?)',
                        (item['example_id'],canonical(item),item['validation_results']['split_group'],'train'));index.tick()
            check();yield index
        finally:index.db.close()


def training_examples(root):
    with open_checked(root) as index:yield from index.values()


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('export');a.add_argument('--packet',required=True);a.add_argument('--output',required=True)
    a=sub.add_parser('release');a.add_argument('--dataset',required=True);a.add_argument('--review',required=True);a.add_argument('--output',required=True);a.add_argument('--limits',required=True)
    a=p.parse_args();result=export_packet(a.packet,a.output) if a.command=='export' else release(a.dataset,a.review,a.output,limits=metadata(a.limits))
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
