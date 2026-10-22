"""Freeze index metadata only; no native archive binding or content access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import sqlite3
import sys
import time

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
DB=BASE/'m2-intake/enwiki-complete-index-identity-frame-v1/index.sqlite'
OUT=HERE/'frozen-selection'
OUTPUT=8000000
RSS=256000000
FIELDS=['index_row_ordinal','group_ordinal','page_ID','exact_title','raw_line_SHA256','raw_line_bytes','line_ends_LF','exact_raw_line_UTF8']


def clock():return time.clock_gettime(time.CLOCK_MONOTONIC)


def stat(path):
    s=Path(path).stat()
    return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def guard(out):
    value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform!='darwin':value*=1024
    if value>RSS:raise ValueError('RSS256MB')
    if sum(p.stat().st_size for p in out.iterdir() if p.is_file())>OUTPUT-65536:
        raise ValueError('output8MB_receipt_headroom')


def write(path,value):
    raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
    if len(raw)+sum(p.stat().st_size for p in path.parent.iterdir() if p.is_file())>OUTPUT:
        raise ValueError('output8MB_before_write')
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())


def freeze(connection,out,target,check=lambda:None):
    groups=[];last_row=0;previous_end=None;written=0;largest=0
    # Caller already established a read-only transaction. Queries use existing
    # integer primary keys only; no full DB scan, sort, body fields, or rehash.
    cursor=connection.execute('SELECT group_ordinal,block_start,block_end_exclusive,first_row,last_row,row_count FROM groups WHERE group_ordinal BETWEEN 1 AND ? ORDER BY group_ordinal',(target['groups'],))
    row_path=out/'rows.jsonl'
    with row_path.open('xb') as row_file:
        for g,start,end,first,last,count in cursor:
            check()
            if g!=len(groups)+1 or first!=last_row+1 or last-first+1!=count or count<=0 or end<=start:
                raise ValueError('group_or_row_contiguity')
            if previous_end is not None and start!=previous_end:
                raise ValueError('compressed_group_boundaries_not_contiguous')
            if not groups and start!=target['header_bytes']:
                raise ValueError('exact_preindex_header_bound')
            groups.append({'group_ordinal':g,'compressed_start':start,'compressed_end_exclusive':end,
                'compressed_bytes':end-start,'first_row_ordinal':first,'last_row_ordinal':last,'index_rows':count})
            seen=0
            for row,page,row_group,title,h,length,lf,a,b in connection.execute('SELECT row_ordinal,page_id,group_ordinal,title,raw_line_sha256,raw_line_bytes,line_ends_LF,noncanonical_offset_ascii,noncanonical_page_ascii FROM rows WHERE row_ordinal BETWEEN ? AND ? ORDER BY row_ordinal',(first,last)):
                check()
                if row!=last_row+1 or row_group!=g or type(page)is not int or not 0<page<2**63 or lf not in (0,1) or type(title)is not str:
                    raise ValueError('exact_row_identity_group')
                raw=((str(start) if a is None else a)+':'+(str(page) if b is None else b)+':'+title).encode('utf8')+(b'\n' if lf else b'')
                if len(raw)!=length or type(h)is not bytes or len(h)!=32 or hashlib.sha256(raw).digest()!=h:
                    raise ValueError('stored_raw_line_reconstruction_hash')
                fields=[row,g,page,title,h.hex(),length,lf,raw.decode('utf8')]
                line=(json.dumps(fields,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf8')
                if written+len(line)>OUTPUT-65536:
                    raise ValueError('row_manifest_prewrite8MB')
                
                if row_file.write(line)!=len(line):raise OSError('short_row_manifest_write')
                written+=len(line);seen+=1;last_row=row
            if seen!=count:raise ValueError('all_group_rows_reconciled')
            previous_end=end;largest=max(largest,end-start)
        row_file.flush();os.fsync(row_file.fileno())
    if len(groups)!=target['groups'] or last_row!=target['rows'] or previous_end!=target['end_exclusive'] or largest!=target['maximum_group_bytes']:
        raise ValueError('exact_frozen_calibration_frame')
    boundary=connection.execute('SELECT group_ordinal,block_start,first_row FROM groups WHERE group_ordinal=?',(target['groups']+1,)).fetchone()
    if boundary!=(target['groups']+1,target['end_exclusive'],target['rows']+1):
        raise ValueError('exact_next_group_boundary_not_part_of_selection')
    return {'groups':groups,'next_group_boundary_not_selected':{'group_ordinal':boundary[0],'compressed_start':boundary[1],'first_row_ordinal':boundary[2]},'row_manifest_fields':FIELDS,'rows':last_row,'row_manifest_bytes':written,
            'row_manifest_SHA256':sha(row_path),'all_raw_line_hashes_reconstructed_exact':True,
            'header_bytes':target['header_bytes'],'compressed_prefix_end_exclusive':previous_end,
            'largest_group_bytes':largest}


def verify(a):
    if sha(HERE/'code-pins.json')!=a.code_pins_sha256:raise ValueError('external_codepins_digest')
    pins=json.loads((HERE/'code-pins.json').read_text())['SHA256']
    profile=json.loads((HERE/'profile.json').read_text())
    if set(pins)!=set(profile['required_metadata_code_paths']):raise ValueError('exact_pin_inventory')
    for path,h in pins.items():
        if Path(path).is_symlink() or sha(path)!=h:raise ValueError('metadata_code_pin_changed')
    if DB.is_symlink() or stat(DB)!=profile['index_DB_stat']:
        raise ValueError('index_DB_stat_changed')
    for suffix in ['-wal','-shm','-journal']:
        if Path(str(DB)+suffix).exists():raise ValueError('source_SQLite_sidecar_refused')
    producer=json.loads(Path(profile['producer_receipt']).read_text())
    independent=json.loads(Path(profile['independent_receipt']).read_text())
    supervisor=json.loads(Path(profile['producer_supervisor']).read_text())
    if supervisor['worker_receipt_SHA256']!=sha(profile['producer_receipt']) or supervisor['worker_exit_code']!=0 or not supervisor['worker_reaped'] or independent['output_pins']['result.json']!=sha(profile['producer_receipt']) or independent['output_pins']['supervisor.json']!=sha(profile['producer_supervisor']):
        raise ValueError('index_producer_independent_receipt_byte_binding')
    if producer['status']!='COMPLETE_INDEX_IDENTITY_FRAME_NO_ADMISSION' or independent['status']!='COMPLETE_INDEPENDENT_INDEX_IDENTITY_METADATA_VERIFICATION_NO_ADMISSION' or producer['SQLite_SHA256']!=profile['inherited_DB_SHA256'] or independent['SQLite_SHA256_independently_rehashed']!=profile['inherited_DB_SHA256'] or not independent['all_unique_page_ID_constraint_and_exact_row_coverage_verified']:
        raise ValueError('prior_index_complete_identity_verification_chain')
    return profile


def main():
    p=argparse.ArgumentParser();p.add_argument('--freeze-index-metadata',action='store_true');p.add_argument('--code-pins-sha256',required=True);a=p.parse_args()
    def stop(s,f):raise TimeoutError('60sec_metadata_bound')
    for sig in [signal.SIGALRM,signal.SIGTERM,signal.SIGINT]:signal.signal(sig,stop)
    signal.setitimer(signal.ITIMER_REAL,60);started=clock();created=False;connection=None
    try:
        profile=verify(a)
        if not a.freeze_index_metadata:print('READY_INDEX_METADATA_ONLY_NO_NATIVE_ACCESS');return
        if OUT.exists() or OUT.is_symlink():raise ValueError('existing_selection_no_overwrite')
        OUT.mkdir();created=True;before=stat(DB)
        connection=sqlite3.connect(f'file:{DB}?mode=ro&immutable=1',uri=True)
        connection.execute('PRAGMA query_only=ON');connection.execute('PRAGMA cache_size=-8192');connection.execute('BEGIN')
        result=freeze(connection,OUT,profile['target'],lambda:guard(OUT))
        connection.execute('COMMIT');connection.close();connection=None
        if stat(DB)!=before:raise ValueError('index_DB_mutated_during_selection')
        verify(a);guard(OUT)
        result.update(status='FROZEN_PRECONTENT_INDEX_SELECTION_ONLY_NO_NATIVE_SOURCE_BINDING_OR_DISPATCH',
            index_DB_path=str(DB),index_DB_stat=before,index_DB_SHA256_inherited_not_rehashed=profile['inherited_DB_SHA256'],
            source_metadata_pins=json.loads((HERE/'code-pins.json').read_text())['SHA256'],
            target_precontent=profile['target'],native_publication_pins_bound=False,native_body_reads=0,
            source_compressed_index_reads=0,full_index_DB_rehash=False,index_SQLite_rows_read=profile['target']['rows'],index_group_metadata_rows_read=profile['target']['groups']+1,
            native_page_ID_uniqueness_proven=False,calibration_execution_authorized=False,
            no_probability_sample_or_usable_data_claim=True,elapsed_seconds=clock()-started)
        write(OUT/'selection.json',result)
        write(OUT/'manifest.json',{'status':result['status'],'SHA256':{name:sha(OUT/name) for name in ['rows.jsonl','selection.json']},
            'output_bytes_before_manifest':sum(q.stat().st_size for q in OUT.iterdir()),'index_DB_stat_unchanged':stat(DB)==before})
        fd=os.open(OUT,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        print(json.dumps({'status':result['status'],'groups':len(result['groups']),'rows':result['rows'],'row_manifest_bytes':result['row_manifest_bytes'],'selection_SHA256':sha(OUT/'selection.json')}))
    except BaseException as e:
        if created:write(OUT/'failure.json',{'status':'PARTIAL_SELECTION_NO_RETRY','error':type(e).__name__+':'+str(e)[:1000],'native_body_reads':0})
        raise
    finally:
        if connection is not None:connection.close()
        signal.setitimer(signal.ITIMER_REAL,0)


if __name__=='__main__':main()
