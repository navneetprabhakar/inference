"""Reproduce integrity/count checks for the bounded partial SQL snapshot, without admission."""
import os
os.environ['OMP_NUM_THREADS']='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import resource
import unicodedata
import sys
import tarfile
import time
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[2]
DATA=ROOT/'data/language-mixture-v1'


def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def verify():
    start=time.monotonic();output=DATA/'candidate-verification.json'
    if output.exists():raise FileExistsError(output)
    result={'state':'pending','failures':[],'source_checks':[]}
    con=None;archive=None
    def check():
        if time.monotonic()-start>900:raise RuntimeError('15minute combined verification cap')
        peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform!='darwin':peak*=1024
        if peak>3*1024**3:raise RuntimeError('3GiB verifier peak RSS cap')
        if (ROOT/'runs/STOP').exists() or (DATA/'STOP').exists():raise RuntimeError('explicit STOP')
    try:
        manifest_path=DATA/'partial-candidate-manifest.json'
        manifest=json.loads(manifest_path.read_text())
        if manifest['state']!='partial_incomplete_not_admitted':raise ValueError('not a declared partial snapshot')
        db=DATA/'candidates.sqlite'
        if digest(db)!=manifest['candidate_database_sha256'] or db.stat().st_size!=manifest['candidate_database_bytes']:
            raise ValueError('SQL digest/size changed')
        for key,name in [('builder_sha256','build.py'),('protocol_sha256','PROTOCOL.md')]:
            if digest(Path(__file__).with_name(name))!=manifest[key]:raise ValueError('source code/protocol differs from snapshot')
        if digest(DATA/'status.json')!=manifest['failure']['status_sha256']:raise ValueError('original stopped receipt changed')
        previous=json.loads((DATA/'input-verification.json').read_text())
        if previous['state']!='passed_input_integrity_only' or previous['candidate_database_sha256']!=manifest['candidate_database_sha256'] or previous['candidate_manifest_sha256']!=digest(manifest_path):
            raise ValueError('prior input verification does not bind this snapshot')
        hold=manifest['official_story_validation'];hp=Path(hold['path'])
        if hp.resolve()!=DATA/'TinyStories-valid.txt' or hp.stat().st_size!=hold['bytes'] or digest(hp)!=hold['sha256']:
            raise ValueError('official validation artifact differs from snapshot')
        if hold['revision']!='f54c09fd23315a6f9c86f9dc80f725de7d8f9c64' or hold['bytes']>25*1024**2:
            raise ValueError('official validation revision/size outside authorization')
        story_root=Path(manifest['source_files'][0]['path']).parent
        archive_path=story_root.with_suffix('.tar.gz')
        archive_sha=digest(archive_path)
        if archive_sha!='26cf7605aca15bc4ea6fa637256400d9d01317b28ed296172b2d1dd160cd7699':
            raise ValueError('original story archive checksum mismatch')
        archive=tarfile.open(archive_path)
        members={Path(m.name).name:m for m in archive.getmembers() if m.isfile()}
        lengths={}
        for index,entry in enumerate(manifest['source_files']):
            check();path=Path(entry['path'])
            actual=digest(path)
            if actual!=entry['sha256'] or path.stat().st_size!=entry['bytes']:
                raise ValueError('raw file digest/bytes changed: '+str(path))
            if entry['source']=='stories':
                if entry['archive_sha256']!=archive_sha:raise ValueError('story archive receipt mismatch')
                with archive.extractfile(members[path.name]) as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=actual:raise ValueError('raw story differs from original archive member')
                rows=len(json.loads(path.read_bytes()))
            elif entry['source']=='dialogue':
                receipt=json.loads((path.parent/'receipt.json').read_text())
                if receipt['sha256']!=actual or receipt['revision']!=entry['revision'] or receipt['bytes']!=entry['bytes']:
                    raise ValueError('chat raw receipt mismatch')
                rows=pq.ParquetFile(path).metadata.num_rows
            elif entry['source']=='web':
                if actual!='3fcf2dc69cd52503986276d3d2d26a8c356d0f2ea28a0de4fdbda8cf87755693':raise ValueError('web source differs from fixed archive')
                rows=pq.ParquetFile(path).metadata.num_rows
            else:raise ValueError('unknown source')
            lengths[index]=rows
            result['source_checks'].append(dict(index=index,path=str(path),sha256=actual,bytes=path.stat().st_size,rows=rows))
        archive.close();archive=None
        con=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
        if con.execute('pragma quick_check').fetchone()!=('ok',):raise ValueError('SQLite integrity failure')
        if con.execute("select name from sqlite_master where type='table'").fetchall()!=[('documents',)]:raise ValueError('unexpected SQL tables')
        page_count=con.execute('pragma page_count').fetchone()[0];page_size=con.execute('pragma page_size').fetchone()[0]
        if page_count*page_size>500*1024**2:raise ValueError('candidate snapshot exceeds 500MiB cap')
        counts={}
        for src,split,n,t in con.execute('select source,split,count(*),sum(tokens) from documents group by source,split'):
            counts[f'{src}_{split}_docs']=n;counts[f'{src}_{split}_tokens']=t
        if counts!=manifest['counts']:raise ValueError('committed SQL aggregates differ from manifest')
        inventory=[list(r) for r in con.execute('select source,source_file,count(*),min(source_row),max(source_row) from documents group by source,source_file')]
        if inventory!=manifest['source_file_sql_inventory']:raise ValueError('sourcefile row inventory differs from manifest')
        for src,index,n,lo,hi in inventory:
            if index not in lengths or src!=manifest['source_files'][index]['source'] or lo<0 or hi>=lengths[index]:
                raise ValueError('source_file/source_row outside raw inventory')
        if con.execute("select count(*) from documents where source_row<0 or tokens<1 or split not in ('train','validation')").fetchone()[0]:raise ValueError('invalid SQL row cursor/count/split')
        if con.execute('select count(*) from (select source,family from documents group by source,family having count(distinct split)>1)').fetchone()[0]:raise ValueError('family crosses train/validation')
        if con.execute('select count(*)-count(distinct normalized_sha256) from documents').fetchone()[0]:raise ValueError('exact duplicate candidate text hashes')
        shortfalls={f'{s}_{split}':max(0,targets[s]-counts[f'{s}_{split}_tokens']) for s in manifest['train_targets'] for split,targets in [('train',manifest['train_targets']),('validation',manifest['validation_targets'])]}
        if shortfalls!=manifest['shortfalls']:raise ValueError('target shortfalls differ from SQL')
        if time.monotonic()-start>300:raise RuntimeError('5minute provenance phase cap')
        # Independent full per-row recount; no token streams or source text output.
        sys.path.insert(0,str(ROOT))
        from tokenizer import load
        if digest(ROOT/'tokenizer.py')!=previous['checks']['tokenizer_code_sha256']:
            raise ValueError('tokenizer changed after input verification')
        tok=load();retoken_started=time.monotonic();retoken_counts=Counter();retoken_rows=0
        for doc_id,src,split,stored_n,stored_raw,stored_norm,text in con.execute('select doc_id,source,split,tokens,raw_sha256,normalized_sha256,text from documents'):
            if retoken_rows%1000==0:
                check()
                if time.monotonic()-retoken_started>600:raise RuntimeError('10minute full retokenization cap')
            if hashlib.sha256(text.encode()).hexdigest()!=stored_raw:
                raise ValueError('candidate raw text digest mismatch: '+doc_id)
            normalized=' '.join(unicodedata.normalize('NFKC',text).casefold().split())
            if hashlib.sha256(normalized.encode()).hexdigest()!=stored_norm:
                raise ValueError('candidate normalized digest mismatch: '+doc_id)
            ids=tok.encode(text).ids
            if len(ids)+1!=stored_n or not ids or min(ids)<0 or max(ids)>50255:
                raise ValueError('candidate token count/range/EOT mismatch: '+doc_id)
            retoken_counts[f'{src}_{split}_tokens']+=len(ids)+1
            retoken_counts[f'{src}_{split}_docs']+=1
            retoken_rows+=1
        if dict(retoken_counts)!=counts:raise ValueError('independent full token aggregates differ')
        result['full_candidate_retokenization']={'rows':retoken_rows,'counts':dict(retoken_counts),'seconds':time.monotonic()-retoken_started,'raw_and_normalized_hashes_checked':True,'tokenizer_code_sha256':digest(ROOT/'tokenizer.py')}
        check()
        if digest(db)!=manifest['candidate_database_sha256']:raise ValueError('SQL changed during verification')
        result.update(state='passed_partial_snapshot_integrity_only',not_admitted=True,counts=counts,shortfalls=shortfalls,
                      candidate_database_sha256=manifest['candidate_database_sha256'],candidate_manifest_sha256=digest(manifest_path),
                      input_verification_sha256=digest(DATA/'input-verification.json'),official_holdout_sha256=digest(hp),
                      source_archive_sha256=archive_sha,sqlite_pages=page_count,sqlite_page_bytes=page_size,
                      pending='Root protected-case custody, independent quality review and target shortfall resolution. No packing/training.',
                      limitations='Full independent text/hash/token recount does not establish semantic quality or protected-case independence. Post-hoc builder SHA verifies current file identity, not execution attestation against a changed-then-restored program.')
    except Exception as error:
        result['state']='rejected_partial_snapshot_integrity'
        result['failures'].append(f'{type(error).__name__}: {error}')
    finally:
        if con is not None:con.close()
        if archive is not None:archive.close()
    result['seconds']=time.monotonic()-start;result['verifier_sha256']=digest(__file__)
    temp=output.with_suffix('.tmp');temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(output)
    print(json.dumps({'state':result['state'],'failures':result['failures'],'seconds':result['seconds']}))
    return 0 if result['state']=='passed_partial_snapshot_integrity_only' else 1


if __name__=='__main__':sys.exit(verify())
