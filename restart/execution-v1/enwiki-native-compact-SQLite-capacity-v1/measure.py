"""Synthetic-only native occurrence schema measurement, never a producer."""
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sqlite3
import sys
import tempfile
import time

PAGES = 25792234
GROUPS = 257960
REV_CAP = 30000000
DB_CAP = 3800000000
TOTAL_CAP = 4000000000
SIDE = 128000000
RECEIPTS = 64000000
BATCH = 500
SCHEMA = '''
CREATE TABLE pages(
 row_ordinal INTEGER PRIMARY KEY, page_id INTEGER NOT NULL,
 first_revision_id INTEGER, namespace INTEGER NOT NULL, flags INTEGER NOT NULL,
 model_code INTEGER NOT NULL, revision_count INTEGER NOT NULL,
 main_text_bytes INTEGER NOT NULL, group_decoded_start INTEGER NOT NULL,
 raw_XML_bytes INTEGER NOT NULL, raw_SHA256 BLOB NOT NULL CHECK(length(raw_SHA256)=32));
CREATE TABLE groups(
 group_ordinal INTEGER PRIMARY KEY, compressed_start INTEGER NOT NULL,
 compressed_end_exclusive INTEGER NOT NULL, decoded_bytes INTEGER NOT NULL,
 first_page_ordinal INTEGER UNIQUE NOT NULL, last_page_ordinal INTEGER NOT NULL,
 page_count INTEGER NOT NULL, raw_SHA256 BLOB NOT NULL CHECK(length(raw_SHA256)=32));
CREATE TABLE revisions(
 revision_id INTEGER NOT NULL, page_ordinal INTEGER NOT NULL, revision_ordinal INTEGER NOT NULL,
 PRIMARY KEY(revision_id,page_ordinal,revision_ordinal),
 FOREIGN KEY(page_ordinal) REFERENCES pages(row_ordinal)) WITHOUT ROWID;
'''


def clock():
    return time.clock_gettime(time.CLOCK_MONOTONIC)


def rss():
    n=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return n if sys.platform=='darwin' else n*1024


def guard(root):
    if rss()>1000000000:raise MemoryError('synthetic_process_RSS1GB')
    if sum(p.stat().st_size for p in root.iterdir() if p.is_file())>160000000:
        raise ValueError('synthetic160MBscratch_prewrite_headroom32MB')


def create(path):
    db=sqlite3.connect(path)
    for pragma in ['page_size=4096','max_page_count='+str(DB_CAP//4096),'journal_mode=MEMORY',
                   'synchronous=FULL','cache_size=-32768','temp_store=MEMORY','mmap_size=0','foreign_keys=ON']:
        db.execute('PRAGMA '+pragma)
    db.executescript(SCHEMA);db.commit()
    return db


def scenario(root,name,n,permuted=False,multiple=False,int64=False,wide_ids=False):
    path=root/(name+'.sqlite');db=create(path);started=clock();revision_rows=0
    flags_counts={};namespace_counts={};max_main=0;group_sum=0;group_start=0;samples={}
    ordinal_base=20000000  # Representative 4-byte native-row key, not a small-row varint shortcut.
    try:
        for i in range(n):
            if i%BATCH==0:guard(root)
            ordinal=ordinal_base+i+1
            page_id=100000000+(i*104729)%100000007
            revision_id=1000000000+((i*104729)%100000007 if permuted else i)
            namespace=0 if i%20 else [1,2,4,10,14,828][(i//20)%6]
            flags=0;model=0
            length=[128,512,2048,4096,8192,16384,40960,65536,256,1024][i%10]
            if i%17==0:flags|=1;length=24  # redirect
            if i%997==0:flags|=2;length=0  # deleted text, revision identity still retained
            if i%4999==0:flags|=4;model=255  # unknown model, requires source-bound exception in a producer
            if i in [3,n//2,n-3]:flags|=8;length=100000000  # Explicit oversized metadata, no body allocation.
            count=1+(int(i%100<14)+int(i%100==14) * 2 if multiple else 0)
            if int64 or wide_ids:
                page_id=2**63-1-i;revision_id=2**63-1-i
            if int64:
                namespace=2**31-1;flags=2**31-1;model=65535
                length=2**48+i;position=2**50+i;raw_len=2**51+i
            else:
                position=group_sum;raw_len=length+1024
            first_revision=revision_id
            # Repeated revision IDs in different pages are retained by the composite key.
            if i>0 and i%10000==0:first_revision=1000000000
            digest=hashlib.sha256(str(ordinal).encode()).digest()
            values=(ordinal,page_id,first_revision,namespace,flags,model,count,length,position,raw_len,digest)
            if i in [0,1,3,14,997,n//2,n-3,n-1]:samples[ordinal]=values
            db.execute('INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?,?,?)',values)
            for j in range(count):
                rid=first_revision if j in [0,2] else revision_id+(-2000000000 if int64 or wide_ids else 2000000000)
                db.execute('INSERT INTO revisions VALUES (?,?,?)',(rid,ordinal,j+1));revision_rows+=1
            flags_counts[str(flags)]=flags_counts.get(str(flags),0)+1
            namespace_counts[str(namespace)]=namespace_counts.get(str(namespace),0)+1
            max_main=max(max_main,length);group_sum+=raw_len
            if i%100==99 or i==n-1:
                group=(i//100)+1
                compressed_start=group*100000
                first=ordinal_base+group_start+1
                db.execute('INSERT INTO groups VALUES (?,?,?,?,?,?,?,?)',
                    (group,compressed_start,compressed_start+100000,group_sum,first,ordinal,i-group_start+1,
                     hashlib.sha256(str(group).encode()).digest()))
                group_sum=0;group_start=i+1
            if (i+1)%BATCH==0:db.commit()
        db.commit()
        insert_seconds=clock()-started
        check_start=clock()
        if db.execute('PRAGMA integrity_check').fetchall()!=[('ok',)]:raise ValueError('integrity')
        if db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('FK')
        if db.execute('SELECT COUNT(*),SUM(revision_count) FROM pages').fetchone()!=(n,revision_rows):raise ValueError('page_revision_counts')
        if db.execute('SELECT COUNT(*) FROM revisions').fetchone()[0]!=revision_rows:raise ValueError('occurrence_count')
        for ordinal,values in samples.items():
            if db.execute('SELECT * FROM pages WHERE row_ordinal=?',(ordinal,)).fetchone()!=values:raise ValueError('all_page_scalar_and_hash_roundtrip')
        duplicates=db.execute('SELECT COUNT(*) FROM revisions WHERE revision_id=1000000000').fetchone()[0]
        if n>10000 and duplicates<2:raise ValueError('nonunique_revision_IDs_not_preserved')
        # A deliberately repeated ID within ONE page has distinct revision ordinals too.
        if multiple and db.execute('SELECT COUNT(*) FROM revisions WHERE page_ordinal=? AND revision_id=?',
                                  (ordinal_base+15,(2**63-1-14) if int64 or wide_ids else (1000000014 if not permuted else 1000000000+(14*104729)%100000007))).fetchone()[0]!=2:
            raise ValueError('same_page_repeated_revision_occurrence')
        lookup_plan=db.execute('EXPLAIN QUERY PLAN SELECT page_ordinal,revision_ordinal FROM revisions WHERE revision_id=?',(1000000000,)).fetchall()
        if not any('PRIMARY KEY' in p[-1] for p in lookup_plan):raise ValueError('revision_ID_lookup_not_indexed')
        indexes=db.execute("SELECT name,tbl_name,sql FROM sqlite_master WHERE type='index'").fetchall()
        fk_check_seconds=clock()-check_start
        tables={}
        try:
            for table_name,bytes_,pages in db.execute('SELECT name,SUM(pgsize),COUNT(*) FROM dbstat GROUP BY name'):
                tables[table_name]={'bytes':bytes_,'pages':pages}
        except sqlite3.Error:
            tables={'unavailable':'SQLite dbstat not compiled; fallback whole-size projection below'}
        db.close();db=None
        size=path.stat().st_size
        with path.open('rb') as f:file_sha=hashlib.file_digest(f,'sha256').hexdigest()
        if isinstance(tables.get('pages'),dict) and isinstance(tables.get('revisions'),dict):
            page_bytes=tables['pages']['bytes']/n*PAGES
            revision_bytes_at_cap=tables['revisions']['bytes']/revision_rows*REV_CAP
            group_bytes=(sum(v['bytes'] for k,v in tables.items() if k.startswith('groups') or k=='sqlite_autoindex_groups_1')/((n+99)//100)*GROUPS)
            projected_cap=page_bytes+revision_bytes_at_cap+group_bytes+4096
        else:
            page_bytes=revision_bytes_at_cap=group_bytes=None
            projected_cap=size/n*PAGES*max(1,REV_CAP/(revision_rows/n*PAGES))
        return {'scenario':name,'pages':n,'revisions':revision_rows,'groups':(n+99)//100,'SQLite_bytes':size,
            'bytes_per_page_including_revision_lookup_and_groups':size/n,'DB_SHA256':file_sha,'dbstat':tables,
            'insert_seconds':insert_seconds,'integrity_FK_check_seconds':fk_check_seconds,
            'synthetic_insert_pages_per_second':n/insert_seconds,'revision_IDs_permuted':permuted,
            'multiple_revisions':multiple,'int64_extreme_stress_not_population_model':int64,'int64_IDs_only_stress':wide_ids,
            'duplicate_revision_ID_occurrences_retained':duplicates,'revision_lookup_plan':lookup_plan,
            'all_page_field_roundtrip_checks':len(samples),'indexes':indexes,'flag_counts':flags_counts,'namespace_counts':namespace_counts,'maximum_main_text_bytes':max_main,
            'scaled_observed_ratio_DB_bytes':size/n*PAGES,
            'scaled_at_30M_revision_cap_DB_bytes':projected_cap,'scaled_pages_component_bytes':page_bytes,
            'scaled_revision_component_bytes_at_cap':revision_bytes_at_cap,'scaled_groups_component_bytes':group_bytes,
            'at_30M_plus128Mexceptions64Mreceipts_total_bytes':projected_cap+SIDE+RECEIPTS,
            'at_30M_plus10pct_DB_then_sidecars_total_bytes':projected_cap*1.1+SIDE+RECEIPTS,
            'fits_3_8GB_DB_at_revision_cap':projected_cap<=DB_CAP,
            'fits_4GB_total_at_revision_cap':projected_cap+SIDE+RECEIPTS<=TOTAL_CAP}
    finally:
        if db is not None:db.close()


def main():
    def stop(s,f):raise TimeoutError('60second_synthetic_measurement_bound')
    for sig in [signal.SIGALRM,signal.SIGINT,signal.SIGTERM]:signal.signal(sig,stop)
    signal.setitimer(signal.ITIMER_REAL,60)
    try:
        results=[];start=clock()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,n,permuted,multiple,int64,wide_ids in [
                ('ordered_realistic',100000,False,False,False,False),
                ('permuted_realistic',100000,True,False,False,False),
                ('permuted_near_revision_cap',100000,True,True,False,False),
                ('permuted_larger_than_32MiB_cache',500000,True,True,False,False),
                ('int64_IDs_only_separate_stress',100000,True,True,False,True),
                ('extreme_int64_separate_stress',100000,True,True,True,False)]:
                result=scenario(root,name,n,permuted,multiple,int64,wide_ids);results.append(result)
                (root/(name+'.sqlite')).unlink()
        print(json.dumps({'status':'SYNTHETIC_ONLY_NO_PRODUCER_OR_SOURCE_BODY_READ','SQLite_version':sqlite3.sqlite_version,
            'schema':SCHEMA,'schema_SHA256':hashlib.sha256(SCHEMA.encode()).hexdigest(),
            'cases':results,'elapsed_seconds':clock()-start,'peak_process_RSS_bytes':rss(),
            'page_count_projection':PAGES,'revision_count_cap':REV_CAP,'source_body_reads':0,
            'no_title_or_extra_page_ID_lookup_index':True,'production_settings':{'page_size':4096,'cache_KiB':32768,
              'commit_rows':500,'journal':'MEMORY','temp_store':'MEMORY','synchronous':'FULL','DB_cap':DB_CAP},
            'not_predictions':'Metadata integer distributions and revision multiplicity synthetic. The500k whole DB exceeds32MiB but its revision Btree is still below32MiB, so full-size random-index I/O is not certified. Native parsing, full-frame insert time and disk fragmentation costs remain unmeasured.'},indent=2))
    finally:signal.setitimer(signal.ITIMER_REAL,0)


if __name__=='__main__':main()
