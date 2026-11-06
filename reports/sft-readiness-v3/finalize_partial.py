"""Verify and freeze metadata for the closed partial candidate; no source text reads."""
import os
os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import hashlib
import json
import sqlite3
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'data/sft-readiness-v3'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def collect():
    policy=json.loads((DATA/'policy.json').read_text());failure=json.loads((DATA/'failure.json').read_text());db=DATA/'candidates.sqlite'
    if (DATA/'candidate-manifest.json').exists() or (DATA/'candidates.sqlite-journal').exists():raise ValueError('not closed failed candidate')
    if failure['state']!='failed_not_admitted':raise ValueError('failure identity')
    for name,digest in policy['code_and_policy'].items():
        if sha(ROOT/name)!=digest:raise ValueError('runtime/policy pin mismatch')
    for file in policy['source_files']:
        if sha(Path(file['path']))!=file['sha256']:raise ValueError('source changed')
    conn=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True)
    if conn.execute('PRAGMA quick_check').fetchone()!=('ok',):raise ValueError('SQLite integrity')
    keys=('source','split','documents','input_tokens','target_tokens','whole','has_system','multi_pair','generation_max','input_max')
    aggregates=[dict(zip(keys,row)) for row in conn.execute('SELECT source,split,count(*),sum(input_tokens),sum(target_tokens),sum(whole),sum(has_system),sum(selected_messages>2),max(generation_max),max(input_tokens) FROM documents GROUP BY source,split')]
    inventory=[dict(raw_sha256=s,raw_path=p,committed_rows=n,max_committed_zero_based_row=m) for s,p,n,m in conn.execute('SELECT raw_sha256,raw_path,count(*),max(row_index) FROM documents GROUP BY raw_sha256,raw_path')]
    families=[dict(source=s,split=sp,families=n) for s,sp,n in conn.execute('SELECT source,split,count(distinct family) FROM documents GROUP BY source,split')]
    if conn.execute('SELECT count(*) FROM (SELECT family FROM documents GROUP BY family HAVING count(distinct split)>1)').fetchone()[0]:raise ValueError('family leakage')
    conn.close()
    return dict(state='partial_candidate_not_admitted',reason='Preregistered SQLite 220MiB main-file cap reached; current transaction rolled back; source scan incomplete.',database=dict(path=str(db),sha256=sha(db),bytes=db.stat().st_size),policy_sha256=sha(DATA/'policy.json'),source_integrity_sha256=sha(DATA/'source-integrity.json'),failure_sha256=sha(DATA/'failure.json'),source_files=policy['source_files'],code_and_policy=policy['code_and_policy'],tokenizer=policy['tokenizer'],committed_source_inventory=inventory,aggregates=aggregates,families=families,sqlite_quick_check='ok',limitations='SQL-derived committed counts only. Failure counters include rolled-back attempted inserts and must not be used as committed totals. No full source scan, custody clearance, quality review or admission. No raw text printed.')

def main():
    manifest=collect();path=DATA/'partial-candidate-manifest.json'
    if path.exists():
        if json.loads(path.read_text())!=manifest:raise ValueError('partial manifest changed')
    else:
        with path.open('x') as stream:json.dump(manifest,stream,indent=2)
    coverage=[]
    for file in manifest['source_files']:
        rows=pq.ParquetFile(file['path']).metadata.num_rows
        matched=[r for r in manifest['committed_source_inventory'] if r['raw_sha256']==file['sha256']]
        coverage.append(dict(path=file['path'],sha256=file['sha256'],raw_file_rows=rows,committed_candidate_rows=matched[0]['committed_rows'] if matched else 0,largest_committed_source_row=matched[0]['max_committed_zero_based_row'] if matched else None))
    receipt=dict(state='partial_no_admission',manifest_sha256=sha(path),database_sha256=manifest['database']['sha256'],finalizer_sha256=sha(Path(__file__)),coverage=coverage,scope='Reproduces SQL metadata/byte identities only; independent selected-history retokenization and parent-source verification, root custody and quality review remain required.',sampling_limit='Builder visits source files in pinned order and rows in original order. Resource stop makes this a source-order prefix sample, not a randomized full-pool estimate. Largest committed source row is not the exact scan cursor; rejected and rolled-back rows can occur after it. Do not extrapolate counts or source proportions to the full pool.')
    dest=DATA/'partial-finalization.json'
    if dest.exists():
        if json.loads(dest.read_text())!=receipt:raise ValueError('finalization receipt changed')
    else:
        with dest.open('x') as stream:json.dump(receipt,stream,indent=2)
    print(json.dumps(receipt))

if __name__=='__main__':main()
