"""Bounded pinned corpus acquisition and full own-tokenizer fitting.

Does not admit production training data. Exact/near duplicates, evaluation
contamination and licensing evidence remain explicit downstream gates.
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
import subprocess
import sys
import time
import urllib.request

from cloud_training.nano_data import sha256_file

REVISION='915333b4f8b8684f39aeaafea600fea6f43fb703'
BASE=f'https://huggingface.co/datasets/karpathy/climbmix-400b-shuffle/resolve/{REVISION}'
MAX_DOWNLOAD=3_000_000_000
TARGET_CHARS=2_000_000_000
DOC_CAP=10_000
EXCLUDED={1,6542}


def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.partial')
    with temp.open('w') as f:
        json.dump(value,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def check_disk(path, minimum=80*1024**3):
    if shutil.disk_usage(path).free<minimum:raise RuntimeError('free disk below80GiB guard')


def download_resume(url,path,ledger,ledger_path,*,opener=urllib.request.urlopen,guard=check_disk):
    """Resume only after validating server range; count all newly received bytes."""
    path=Path(path);part=path.with_suffix(path.suffix+'.partial')
    if path.exists():raise FileExistsError('completed file requires receipt verification by caller')
    start=part.stat().st_size if part.exists() else 0
    headers={'Range':f'bytes={start}-'} if start else {}
    with opener(urllib.request.Request(url,headers=headers),timeout=60) as response:
        status=getattr(response,'status',200)
        if start:
            content_range=response.headers.get('Content-Range','')
            match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',content_range)
            if status!=206 or not match or int(match.group(1))!=start or int(match.group(2))+1!=int(match.group(3)):
                raise RuntimeError('server did not honor full remaining resume range; partial retained')
        elif status!=200:raise RuntimeError('unexpected initial response status')
        with part.open('ab' if start else 'wb') as f:
            while True:
                guard(path.parent)
                remaining=MAX_DOWNLOAD-ledger.get('transferred_bytes',0)
                if remaining<=0:raise RuntimeError('3GB total download budget exhausted')
                chunk=response.read(min(1024*1024,remaining))
                if not chunk:break
                ledger['transferred_bytes']=ledger.get('transferred_bytes',0)+len(chunk)
                f.write(chunk);f.flush()
                atomic_json(ledger_path,ledger)
            os.fsync(f.fileno())
    length=response.headers.get('Content-Length')
    if length is not None and part.stat().st_size-start!=int(length):
        raise RuntimeError('incomplete download; partial retained')
    os.replace(part,path)
    return {'file':path.name,'bytes':path.stat().st_size,'sha256':sha256_file(path),'url':url}


def clipped_characters(path):
    import pyarrow.parquet as pq
    total=0;docs=0
    pf=pq.ParquetFile(path)
    if 'text' not in pf.schema.names:raise ValueError('missing text column')
    for group in range(pf.num_row_groups):
        for text in pf.read_row_group(group,columns=['text']).column('text').to_pylist():
            if not isinstance(text,str):raise ValueError('invalid text value')
            total+=min(len(text),DOC_CAP);docs+=1
    return total,docs


def full_fit_texts(paths,stats,target_chars=TARGET_CHARS):
    """Exact pinned tok_train semantics: cap each doc, yield, stop when >target."""
    import pyarrow.parquet as pq
    count=0;docs=0
    for path in paths:
        pf=pq.ParquetFile(path)
        for group in range(pf.num_row_groups):
            for text in pf.read_row_group(group,columns=['text']).column('text').to_pylist():
                if not isinstance(text,str):raise ValueError('invalid text')
                text=text[:DOC_CAP];count+=len(text);docs+=1
                stats.update(characters=count,documents=docs,last_file=str(path),last_row_group=group)
                yield text
                if count>target_chars:return
    raise RuntimeError('source exhausted before full tokenizer fit target; do not claim completion')


def fit_worker(args):
    import pyarrow
    pyarrow.set_cpu_count(2);pyarrow.set_io_thread_count(2)
    root=Path(args.root);manifest=json.loads((root/'sources.json').read_text())
    paths=[]
    for entry in manifest['train']:
        path=root/'source'/entry['file']
        if sha256_file(path)!=entry['sha256']:raise RuntimeError('source changed')
        paths.append(path)
    spec=importlib.util.spec_from_file_location('pinned_nano_tok',args.tokenizer_module)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    target=root/'tokenizer'
    if target.exists():raise FileExistsError('final tokenizer is immutable; inspect existing receipt rather than refit')
    stats={};start=time.time()
    tok=module.RustBPETokenizer.train_from_iterator(full_fit_texts(paths,stats),32768)
    if stats.get('characters',0)<=TARGET_CHARS or tok.get_vocab_size()!=32768:
        raise RuntimeError('incomplete fit or wrong vocabulary')
    target=root/'tokenizer';temporary=root/f'tokenizer-fit-{os.getpid()}'
    if target.exists():raise FileExistsError('final tokenizer is immutable')
    tok.save(str(temporary))
    probes=['नमस्ते 🌍','{"tool":"convert","value":12.5}','<|assistant_end|> literal','Hello, world!']
    if not all(tok.decode(tok.encode(p))==p for p in probes):raise RuntimeError('roundtrip failed')
    special={tok.encode_special(s) for s in tok.get_special_tokens()}
    token_bytes=[0 if i in special else len(tok.decode_single_token_bytes(i)) for i in range(32768)]
    atomic_json(temporary/'token_bytes.json',token_bytes)
    receipt=dict(status='full_own_tokenizer_fit_complete_not_corpus_admission',fit=stats,
                 vocab=32768,tokenizer_sha256=sha256_file(temporary/'tokenizer.pkl'),
                 source_manifest_sha256=sha256_file(root/'sources.json'),
                 tokenizer_module_sha256=sha256_file(args.tokenizer_module),
                 seconds=time.time()-start,threads=2,roundtrip_passed=True,
                 training_admitted=False)
    atomic_json(temporary/'receipt.json',receipt);os.replace(temporary,target)
    print(json.dumps(receipt),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default='runs/ownbase-v2-data')
    parser.add_argument('--reuse',default='runs/l4-data-prep/source/shard_00000.parquet')
    parser.add_argument('--tokenizer-module',default='runs/research-20261110/nanochat/nanochat/tokenizer.py')
    parser.add_argument('--report',default='reports/l4-qualification-v1/final-data-preparation.json')
    parser.add_argument('--fit-worker',action='store_true')
    args=parser.parse_args()
    for key in ('RAYON_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='2'
    if args.fit_worker:return fit_worker(args)
    import pyarrow
    pyarrow.set_cpu_count(2);pyarrow.set_io_thread_count(2)
    root=Path(args.root);(root/'source').mkdir(parents=True,exist_ok=True)
    check_disk(root)
    ledger_path=root/'download-ledger.json'
    ledger=json.loads(ledger_path.read_text()) if ledger_path.exists() else {'cap_bytes':MAX_DOWNLOAD,'transferred_bytes':0}
    source_path=root/'sources.json'
    source=json.loads(source_path.read_text()) if source_path.exists() else dict(
        schema=1,dataset='karpathy/climbmix-400b-shuffle',revision=REVISION,
        upstream_license='CC-BY-NC-4.0',upstream_source='https://huggingface.co/datasets/nvidia/Nemotron-ClimbMix',
        train=[],split_policy={'train':'ascending shard IDs excluding1and6542','development':[1],
                              'final_holdout':[6542],'assigned_before_tokenizer':True},training_admitted=False)
    if source.get('revision')!=REVISION or any(int(e['file'][6:11]) in EXCLUDED for e in source['train']):
        raise RuntimeError('existing source manifest violates pinned revision/split policy')
    report={'status':'acquiring','target_chars':TARGET_CHARS,'doc_cap':DOC_CAP,'threads':2,'training_admitted':False}
    atomic_json(args.report,report)
    try:
        total=0;index=0;byfile={e['file']:e for e in source['train']}
        while total<=TARGET_CHARS:
            if index in EXCLUDED:index+=1;continue
            if index>=6542:raise RuntimeError('dataset exhausted')
            name=f'shard_{index:05d}.parquet';path=root/'source'/name
            if name in byfile:
                entry=byfile[name]
                if sha256_file(path)!=entry['sha256']:raise RuntimeError('receipt hash mismatch')
            elif index==0 and Path(args.reuse).exists():
                check_disk(root)
                if not path.exists():os.link(Path(args.reuse).resolve(),path)
                entry={'file':name,'bytes':path.stat().st_size,'sha256':sha256_file(path),'url':BASE+'/'+name,'reused':True}
            else:
                entry=download_resume(BASE+'/'+name,path,ledger,ledger_path)
            if 'clipped_characters' not in entry:
                entry['clipped_characters'],entry['documents']=clipped_characters(path)
            if name not in byfile:source['train'].append(entry);byfile[name]=entry
            atomic_json(source_path,source)
            total+=entry['clipped_characters'];index+=1
            report.update(status='acquiring',available_fit_characters=total,source_shards=len(source['train']),downloaded_bytes=ledger['transferred_bytes'])
            atomic_json(args.report,report);print(json.dumps(report),flush=True)
        report.update(status='fitting_full_own_tokenizer',source_manifest_sha256=sha256_file(source_path))
        atomic_json(args.report,report)
        log=(root/'tokenizer-fit.log').open('a')
        command=[sys.executable,'-m','cloud_training.nano_final_data','--fit-worker','--root',str(root),'--tokenizer-module',args.tokenizer_module]
        with log:
            proc=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=os.environ.copy())
            try:
                while proc.poll() is None:
                    check_disk(root)
                    rss=subprocess.check_output(['ps','-o','rss=','-p',str(proc.pid)],text=True).strip()
                    pressure=subprocess.check_output(['memory_pressure','-Q'],text=True)
                    match=re.search(r'free percentage:\s*(\d+)%',pressure)
                    if (rss and int(rss)>12*1024*1024) or (match and int(match.group(1))<20):
                        raise RuntimeError('memory guard: worker>12GiB RSS or system available<20%')
                    report.update(worker_pid=proc.pid,worker_rss_kib=int(rss or 0),memory_free_percent=int(match.group(1)) if match else None)
                    atomic_json(args.report,report)
                    try:proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:pass
            except BaseException:
                proc.terminate()
                try:proc.wait(timeout=10)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
                raise
        if proc.returncode:raise RuntimeError(f'tokenizer worker failed code{proc.returncode}; inspect tokenizer-fit.log')
        receipt=json.loads((root/'tokenizer/receipt.json').read_text())
        report.update(status='full_own_tokenizer_ready_not_training_admitted',tokenizer=receipt,
                      outstanding=['exact/near duplicate and evaluation-contamination checks','final training tokenization and packing','immutable multi-shard admission manifest'])
        atomic_json(args.report,report);print(json.dumps(report),flush=True)
    except BaseException as exc:
        report.update(status='stopped_incomplete',error=str(exc));atomic_json(args.report,report)
        raise


if __name__=='__main__':main()
