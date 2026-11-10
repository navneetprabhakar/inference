"""Resumable finite corpus packing; review required before training admission.

Exact dedup: NFKC/casefold/whitespace-normalized full document SHA256.
Near dedup: four 64-character anchors select at most32earlier candidates each;
compare a deterministic <=64hash sample of <=256 evenly sampled five-word
shingles, Jaccard>=0.9. This bounded heuristic can miss edited anchors, reordered
text and unsampled differences. It is not a comprehensive semantic duplicate or
benchmark-contamination detector. Validation is indexed before any train text.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import struct
import subprocess
import time
import urllib.request
import unicodedata

from cloud_training.nano_data import write_rows,sha256_file
from cloud_training.nano_prepare_data import finite_bestfit_rows
from cloud_training.nano_final_data import atomic_json,check_disk,BASE,REVISION

_last_memory_check=0

def resource_guard(root):
    global _last_memory_check
    check_disk(root)
    if time.monotonic()-_last_memory_check>15:
        rss=int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())],text=True).strip())
        pressure=subprocess.check_output(['memory_pressure','-Q'],text=True)
        match=re.search(r'free percentage:\s*(\d+)%',pressure)
        if rss>12*1024*1024 or (match and int(match.group(1))<20):
            raise RuntimeError('memory guard tripped')
        _last_memory_check=time.monotonic()

TOKENIZER='ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5'


def normalize(text):return ' '.join(unicodedata.normalize('NFKC',text).casefold().split())


def signature(text):
    words=text.split();n=max(1,len(words)-4)
    positions=sorted({i*(n-1)//min(255,n-1) for i in range(min(256,n))}) if n>1 else [0]
    values=sorted({int.from_bytes(hashlib.blake2b(' '.join(words[i:i+5]).encode(),digest_size=8).digest(),'little') for i in positions})[:64]
    return set(values)


def anchors(text):
    return sorted({hashlib.sha256(text[p:p+64].encode()).hexdigest()[:24]
                   for p in (0,max(0,len(text)//3-32),max(0,2*len(text)//3-32),max(0,len(text)-64))})


class DedupIndex:
    def __init__(self,path):
        self.db=sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA cache_size=-32768')
        self.db.execute('CREATE TABLE IF NOT EXISTS docs(hash TEXT PRIMARY KEY, source TEXT, split TEXT, signature BLOB)')
        self.db.execute('CREATE TABLE IF NOT EXISTS anchors(anchor TEXT, hash TEXT, PRIMARY KEY(anchor,hash))')
        self.db.execute('CREATE INDEX IF NOT EXISTS source_idx ON docs(source)')
    def rollback_source(self,source):
        self.db.execute('DELETE FROM anchors WHERE hash IN (SELECT hash FROM docs WHERE source=?)',(source,))
        self.db.execute('DELETE FROM docs WHERE source=?',(source,));self.db.commit()
    def admit(self,text,source,split):
        normalized=normalize(text)
        if getattr(self,'check_fit_prefix',False):
            prefix=hashlib.sha256(normalize(text[:10000]).encode()).hexdigest()
            if self.db.execute('SELECT 1 FROM docs WHERE hash=?',(prefix,)).fetchone():return False,'tokenizer_fit_prefix_duplicate',False
        if not normalized:return False,'empty',False
        digest=hashlib.sha256(normalized.encode()).hexdigest()
        if getattr(self,'allowed_hashes',None) is not None and digest not in self.allowed_hashes:
            return False,'not_original_validation_kept',False
        if self.db.execute('SELECT 1 FROM docs WHERE hash=?',(digest,)).fetchone():return False,'exact_duplicate',False
        sig=signature(normalized);keys=anchors(normalized);candidates=set();truncated=False
        for key in keys:
            rows=self.db.execute('SELECT hash FROM anchors WHERE anchor=? ORDER BY hash LIMIT 33',(key,)).fetchall()
            if len(rows)>32:truncated=True
            candidates.update(r[0] for r in rows[:32])
        if truncated and getattr(self,'reject_truncated',False):return False,'near_screen_incomplete',True
        for candidate in sorted(candidates):
            blob=self.db.execute('SELECT signature FROM docs WHERE hash=?',(candidate,)).fetchone()[0]
            other=set(struct.unpack('<'+'Q'*(len(blob)//8),blob))
            if len(sig&other)/max(1,len(sig|other))>=0.9:return False,'near_duplicate',truncated
        blob=struct.pack('<'+'Q'*len(sig),*sorted(sig))
        self.db.execute('INSERT INTO docs VALUES(?,?,?,?)',(digest,source,split,blob))
        self.db.executemany('INSERT INTO anchors VALUES(?,?)',[(key,digest) for key in keys])
        return True,'kept',truncated
    def close(self):self.db.commit();self.db.close()


def token_batches(path,tok,index,split,counts,root):
    import pyarrow.parquet as pq
    source=path.name;pf=pq.ParquetFile(path)
    for group in range(pf.num_row_groups):
        resource_guard(root)
        rows=pf.read_row_group(group,columns=['text']).column('text').to_pylist()
        texts=[]
        for text in rows:
            counts['seen']=counts.get('seen',0)+1
            if not isinstance(text,str):counts['corrupt']=counts.get('corrupt',0)+1;continue
            if len(text)>1_000_000:counts['oversize']=counts.get('oversize',0)+1;continue
            kept,reason,truncated=index.admit(text,source,split)
            counts[reason]=counts.get(reason,0)+1
            if truncated:counts['near_candidate_limit_hits']=counts.get('near_candidate_limit_hits',0)+1
            if kept:texts.append(text)
            if len(texts)==128:
                yield tok.encode(texts,prepend=tok.get_bos_token_id(),num_threads=2);texts=[]
        if texts:yield tok.encode(texts,prepend=tok.get_bos_token_id(),num_threads=2)
        index.db.commit()


def pack_one(path,split,root,tok,index,receipt,tokenizer_sha):
    target=root/'packed'/split/path.stem
    if target.exists():
        manifest=target/'manifest.json'
        stats=target/'audit.json'
        if manifest.exists() and stats.exists():
            data=json.loads(manifest.read_text())
            if sha256_file(target/'rows.u16')!=data['sha256']:raise RuntimeError('packed data hash mismatch')
            audit=json.loads(stats.read_text())
            if data['tokenizer_sha256']!=tokenizer_sha or data['split']!=split or data['sequence_length']!=2048:
                raise RuntimeError('completed shard identity mismatch')
            if sha256_file(manifest)!=audit['manifest_sha256'] or audit['source']['sha256']!=receipt['sha256']:
                raise RuntimeError('completed audit receipt mismatch')
            indexed=index.db.execute('SELECT COUNT(*) FROM docs WHERE source=?',(path.name,)).fetchone()[0]
            if indexed!=audit['documents'].get('kept',0):raise RuntimeError('dedup index does not match completed shard receipt')
            return audit
        # Incomplete private output is reconstructed; source transaction is rolled back.
        shutil.rmtree(target)
    index.rollback_source(path.name)
    counts={};packing={}
    rows=finite_bestfit_rows(token_batches(path,tok,index,split,counts,root),2048,stats=packing)
    source_receipt={'revision':REVISION,'source':str(path),'sha256':receipt['sha256'],
                    'license':'CC-BY-NC-4.0','split':split,'tokenizer_sha256':tokenizer_sha}
    pin=hashlib.sha256(json.dumps(source_receipt,sort_keys=True).encode()).hexdigest()
    manifest=write_rows(target,rows,sequence_length=2048,vocab_size=32768,
                        tokenizer_sha256=tokenizer_sha,split=split,source_manifest_sha256=pin,
                        packing='nanochat-92d63d4-BOS-bestfit-finite-tail-after-bounded-dedup',max_rows=100_000_000)
    index.db.commit()
    audit=dict(source=source_receipt,documents=counts,packing=packing,
               targets=manifest['target_tokens'],rows=manifest['rows'],
               manifest_sha256=sha256_file(target/'manifest.json'),directory=str(target),training_admitted=False)
    atomic_json(target/'audit.json',audit)
    return audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default='runs/ownbase-v2-data/corpus')
    parser.add_argument('--source-root',default='runs/ownbase-v2-data')
    parser.add_argument('--validation',default='runs/l4-data-prep/source/shard_00001.parquet')
    parser.add_argument('--report',default='reports/l4-qualification-v1/corpus-progress.json')
    parser.add_argument('--target-tokens',type=int,default=2_000_000_000)
    parser.add_argument('--download-cap',type=int,default=5_000_000_000)
    parser.add_argument('--continuation-receipt',help='Root-reviewed receipt required before intake beyond5GB')
    parser.add_argument('--tokenizer-module',default='runs/research-20261110/nanochat/nanochat/tokenizer.py')
    args=parser.parse_args()
    if not 0<args.download_cap<=25_000_000_000 or args.target_tokens<=0:raise ValueError('invalid bounded intake limits')
    if args.download_cap>5_000_000_000:
        if not args.continuation_receipt:raise ValueError('continuation review receipt required beyond5GB')
        approval=json.loads(Path(args.continuation_receipt).read_text())
        if approval.get('state')!='approved_for_continuation' or approval.get('tokenizer_sha256')!=TOKENIZER:
            raise ValueError('continuation receipt not approved or wrong tokenizer')
        if args.download_cap>approval.get('raw_download_cap_bytes',0) or args.target_tokens>approval.get('maximum_target_tokens',0):
            raise ValueError('continuation request exceeds reviewed bounds')
        reviewed=Path(approval['reviewed_initial_report'])
        if sha256_file(reviewed)!=approval['reviewed_initial_report_sha256']:
            raise ValueError('reviewed initial report hash mismatch')
    for k in ('RAYON_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='2'
    import pyarrow
    pyarrow.set_cpu_count(2);pyarrow.set_io_thread_count(2)
    root=Path(args.root);root.mkdir(parents=True,exist_ok=True);check_disk(root)
    source_root=Path(args.source_root);source=json.loads((source_root/'sources.json').read_text())
    tokenizer_path=source_root/'tokenizer'
    if sha256_file(tokenizer_path/'tokenizer.pkl')!=TOKENIZER:raise RuntimeError('final tokenizer mismatch')
    spec=importlib.util.spec_from_file_location('pinned_nano_tok',args.tokenizer_module)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    tok=module.RustBPETokenizer.from_directory(str(tokenizer_path))
    index=DedupIndex(root/'dedup.sqlite')
    report={'status':'packing','training_admitted':False,'tokenizer_sha256':TOKENIZER,
            'method':__doc__,'source_revision':REVISION,'train':[],'validation':[],'retained_train_targets':0,'threads':2,
            'outstanding':['root review of receipts','benchmark-contamination checks beyond split dedup','full10B inventory']}
    atomic_json(args.report,report)
    try:
        val=Path(args.validation);val_receipt={'sha256':sha256_file(val)}
        order=[(val,'validation',val_receipt)]
        for entry in source['train']:
            path=source_root/'source'/entry['file']
            if int(path.stem.split('_')[1]) in (1,6542):raise RuntimeError('excluded shard in train')
            order.append((path,'train',entry))
        acquired_path=root/'acquired-sources.json'
        acquired=json.loads(acquired_path.read_text()) if acquired_path.exists() else []
        for e in acquired:order.append((root/'raw'/e['file'],'train',e))
        ledger_path=root/'download-ledger.json'
        ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {'cap_bytes':args.download_cap,'transferred_bytes':sum(e['bytes'] for e in source['train'])+val.stat().st_size,'initial_note':'Conservative total includes all existing final train and benchmark validation raw files once.'}
        ledger['cap_bytes']=args.download_cap
        atomic_json(ledger_path,ledger)
        def pack_and_report(path,split,receipt):
            if sha256_file(path)!=receipt['sha256']:raise RuntimeError('source checksum failed')
            result=pack_one(path,split,root,tok,index,receipt,TOKENIZER)
            report[split].append(result)
            correction_path=root/'development-v2-correction.json'
            if split=='validation' and correction_path.exists():
                correction=json.loads(correction_path.read_text())
                if not correction.get('subset_of_original_validation_keep_set'):raise RuntimeError('development subset correction unverified')
                report['validation_historical']=[result]
                report['validation']=[correction['new_validation']]
                report['development_correction_sha256']=sha256_file(correction_path)
            report['retained_train_targets']=sum(e['targets'] for e in report['train'])
            report['retained_validation_targets']=sum(e['targets'] for e in report['validation'])
            atomic_json(args.report,report);print(json.dumps({'split':split,'source':path.name,'targets':result['targets'],'retained_train_targets':report['retained_train_targets']}),flush=True)
        for path,split,receipt in order:pack_and_report(path,split,receipt)
        import cloud_training.nano_final_data as intake
        intake.MAX_DOWNLOAD=args.download_cap
        (root/'raw').mkdir(exist_ok=True)
        next_id=max(int(p.stem.split('_')[1]) for p,split,_ in order if split=='train')+1
        while report['retained_train_targets']<args.target_tokens:
            resource_guard(root)
            if next_id in (1,6542):next_id+=1;continue
            if next_id>6542:break
            name=f'shard_{next_id:05d}.parquet';url=BASE+'/'+name;path=root/'raw'/name
            with urllib.request.urlopen(urllib.request.Request(url,method='HEAD'),timeout=30) as response:
                size=int(response.headers.get('Content-Length','0'))
            if not size:raise RuntimeError('source size unavailable before bounded download')
            partial=path.with_suffix(path.suffix+'.partial')
            needed=size-(partial.stat().st_size if partial.exists() else 0)
            if ledger['transferred_bytes']+needed>=args.download_cap:
                report['intake_stop']='raw_download_cap';break
            for attempt in range(3):
                try:
                    receipt=intake.download_resume(url,path,ledger,ledger_path,guard=resource_guard,minimum_rate=(512*1024 if attempt<2 else 0),rate_grace_seconds=45)
                    break
                except TimeoutError:
                    if attempt==2:raise
                    print(json.dumps({'resuming_slow_source':name,'attempt':attempt+2}),flush=True)
            acquired.append(receipt);atomic_json(acquired_path,acquired)
            pack_and_report(path,'train',receipt);next_id+=1
        report.update(status='bounded_corpus_packed_review_pending',raw_download_accounted_bytes=ledger['transferred_bytes'],raw_download_cap_bytes=args.download_cap)
        correction_path=root/'development-v2-correction.json'
        if correction_path.exists():
            correction=json.loads(correction_path.read_text())
            if not correction.get('subset_of_original_validation_keep_set'):raise RuntimeError('development subset correction unverified')
            if 'validation_historical' not in report:report['validation_historical']=report['validation']
            report['validation']=[correction['new_validation']]
            report['retained_validation_targets']=correction['new_validation']['targets']
            report['development_correction_sha256']=sha256_file(correction_path)
        else:
            report['outstanding'].append('tokenizer-fit/development isolation correction')
        candidate={'schema':1,'training_admitted':False,'tokenizer_sha256':TOKENIZER,'sequence_length':2048,'vocab_size':32768,'train':[],'validation':[],'admission':{'status':'pending_root_review_and_contamination_check'}}
        for split in ('train','validation'):
            candidate[split]=[{'directory':str(Path(e['directory']).relative_to(root)),'manifest_sha256':e['manifest_sha256']} for e in report[split]]
        atomic_json(root/'candidate-campaign.json',candidate)
        atomic_json(args.report,report)
    except BaseException as exc:
        report.update(status='stopped_incomplete',error=str(exc));atomic_json(args.report,report);raise
    finally:index.close()


if __name__=='__main__':main()


def correct_development_split(source_root,corpus_root,validation_path,tokenizer_module):
    """Exclude every raw tokenizer-fit source and capped fit prefix from dev.

    Indexing all nine shards conservatively includes documents beyond the exact
    2B-character stop. Existing training packs need no mutation because they were
    already filtered against the older, larger validation candidate set.
    """
    import pyarrow
    import pyarrow.parquet as pq
    pyarrow.set_cpu_count(2);pyarrow.set_io_thread_count(2)
    source_root=Path(source_root);corpus_root=Path(corpus_root);validation_path=Path(validation_path)
    source=json.loads((source_root/'sources.json').read_text())
    reference=DedupIndex(corpus_root/'tokenizer-reference.sqlite')
    reference.db.execute('CREATE TABLE IF NOT EXISTS reference_sources(source TEXT PRIMARY KEY, sha256 TEXT, rows INTEGER)')
    reference_counts=[]
    try:
        for entry in source['train']:
            path=source_root/'source'/entry['file'];source_id='tokenizer:'+path.name
            if sha256_file(path)!=entry['sha256']:raise RuntimeError('tokenizer source hash changed')
            done=reference.db.execute('SELECT sha256,rows FROM reference_sources WHERE source=?',(source_id,)).fetchone()
            if done:
                if done[0]!=entry['sha256']:raise RuntimeError('reference receipt mismatch')
                reference_counts.append({'source':path.name,'rows':done[1]});continue
            reference.rollback_source(source_id)
            pf=pq.ParquetFile(path);row_count=0
            for group in range(pf.num_row_groups):
                resource_guard(corpus_root)
                for raw in pf.read_row_group(group,columns=['text']).column('text').to_pylist():
                    if not isinstance(raw,str):raise ValueError('invalid tokenizer source text')
                    row_count+=1
                    for form in {normalize(raw),normalize(raw[:10000])}:
                        if not form:continue
                        digest=hashlib.sha256(form.encode()).hexdigest()
                        if reference.db.execute('SELECT 1 FROM docs WHERE hash=?',(digest,)).fetchone():continue
                        sig=signature(form);blob=struct.pack('<'+'Q'*len(sig),*sorted(sig))
                        reference.db.execute('INSERT INTO docs VALUES(?,?,?,?)',(digest,source_id,'tokenizer_reference',blob))
                        reference.db.executemany('INSERT INTO anchors VALUES(?,?)',[(key,digest) for key in anchors(form)])
                reference.db.commit()
            reference.db.execute('INSERT INTO reference_sources VALUES(?,?,?)',(source_id,entry['sha256'],row_count));reference.db.commit()
            reference_counts.append({'source':path.name,'rows':row_count})
            print(json.dumps({'tokenizer_reference_complete':path.name,'rows':row_count}),flush=True)
        spec=importlib.util.spec_from_file_location('pinned_tokenizer_correction',tokenizer_module)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        if sha256_file(source_root/'tokenizer/tokenizer.pkl')!=TOKENIZER:raise RuntimeError('tokenizer mismatch')
        tok=module.RustBPETokenizer.from_directory(str(source_root/'tokenizer'))
        # Independent namespace; never overwrite original validation or its audit.
        fixed_root=corpus_root/'development-v2'
        fixed_root.mkdir(exist_ok=True)
        original=sqlite3.connect(f'file:{(corpus_root/"dedup.sqlite").resolve()}?mode=ro',uri=True)
        try:reference.allowed_hashes={r[0] for r in original.execute('SELECT hash FROM docs WHERE source=? AND split=?',(validation_path.name,'validation'))}
        finally:original.close()
        if not reference.allowed_hashes:raise RuntimeError('original validation keep-set missing')
        reference.check_fit_prefix=True
        reference.reject_truncated=True
        result=pack_one(validation_path,'validation',fixed_root,tok,reference,{'sha256':sha256_file(validation_path)},TOKENIZER)
        new_hashes={r[0] for r in reference.db.execute('SELECT hash FROM docs WHERE source=?',(validation_path.name,))}
        if not new_hashes<=reference.allowed_hashes:raise RuntimeError('corrected dev is not a subset of original validation keep-set')
        receipt={'status':'corrected_development_packed_review_pending','subset_of_original_validation_keep_set':True,'training_admitted':False,
                 'tokenizer_sha256':TOKENIZER,'fit_source_manifest_sha256':sha256_file(source_root/'sources.json'),
                 'reference_sources':reference_counts,'reference_forms':'full normalized document plus normalized raw[:10000] prefix; every source row indexed before dev selection',
                 'scope':'all nine tokenizer training shards including conservative unused tail; also reject validation prefix matches and incomplete near-candidate screens',
                 'new_validation':result,'old_validation':'not strict tokenizer-heldout; retained only as historical audit',
                 'near_duplicate_limitations':__doc__,
                 'train_packs':'unchanged; already filtered against the larger original validation candidate pool'}
        atomic_json(corpus_root/'development-v2-correction.json',receipt)
        return receipt
    finally:reference.close()
