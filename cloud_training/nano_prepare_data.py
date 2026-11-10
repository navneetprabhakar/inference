"""Bounded benchmark preparation; preserves nanochat BOS best-fit row selection.

No downloads/cloud operations here. Source inputs and tokenizer module must be
pinned and supplied by the caller. This is a provisional benchmark tokenizer,
not production data admission or the complete upstream 2B-character fit.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

from cloud_training.nano_data import sha256_file, write_rows


def finite_bestfit_rows(token_batches, sequence_length, *, buffer_size=1000, stats=None):
    """Same refill, largest-fit and shortest-crop choices as pinned upstream.

    Finite tail differs intentionally: drain remaining buffer; discard incomplete
    final row rather than wrapping the dataset. All input documents need BOS.
    """
    if sequence_length <= 0 or buffer_size <= 0:
        raise ValueError('invalid dimensions')
    stats = stats if stats is not None else {}
    stats.update(documents=0, source_tokens=0, cropped_tokens=0, rows=0,
                 retained_positions=0, incomplete_tail_positions=0)
    batches=iter(token_batches);buffer=[];exhausted=False
    while True:
        row=[]
        while len(row) < sequence_length+1:
            while len(buffer)<buffer_size and not exhausted:
                try: batch=next(batches)
                except StopIteration:
                    exhausted=True
                    break
                for doc in batch:
                    if not doc:raise ValueError('empty tokenized document')
                    buffer.append(list(doc))
                    stats['documents']+=1;stats['source_tokens']+=len(doc)
            if not buffer:
                stats['incomplete_tail_positions']=len(row)
                return
            remaining=sequence_length+1-len(row)
            best_idx=-1;best_len=0
            for i,doc in enumerate(buffer):
                if len(doc)<=remaining and len(doc)>best_len:
                    best_idx=i;best_len=len(doc)
            if best_idx>=0:row.extend(buffer.pop(best_idx))
            else:
                shortest=min(range(len(buffer)),key=lambda i:len(buffer[i]))
                doc=buffer.pop(shortest)
                row.extend(doc[:remaining]);stats['cropped_tokens']+=len(doc)-remaining
        stats['rows']+=1;stats['retained_positions']+=len(row)
        stats['buffered_source_tokens']=sum(map(len,buffer))
        yield row


def parquet_text_batches(paths, batch_size=128):
    import pyarrow.parquet as pq
    for path in paths:
        pf=pq.ParquetFile(path)
        if 'text' not in pf.schema.names:raise ValueError('missing text column')
        for group in range(pf.num_row_groups):
            texts=pf.read_row_group(group,columns=['text']).column('text').to_pylist()
            for i in range(0,len(texts),batch_size):
                batch=texts[i:i+batch_size]
                if any(not isinstance(t,str) for t in batch):raise ValueError('invalid text')
                yield batch


def training_texts(paths, max_chars, stats, doc_cap=10000):
    count=0
    for batch in parquet_text_batches(paths):
        for text in batch:
            text=text[:min(doc_cap,max_chars-count)]
            if text:
                count+=len(text);stats['characters']=count
                stats['documents']=stats.get('documents',0)+1
                yield text
            if count>=max_chars:return


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-manifest',required=True)
    parser.add_argument('--tokenizer-module',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--max-chars',type=int,default=50_000_000)
    parser.add_argument('--train-rows',type=int,default=8192)
    parser.add_argument('--validation-rows',type=int,default=512)
    parser.add_argument('--sequence-length',type=int,default=2048)
    args=parser.parse_args()
    for key in ('RAYON_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
        os.environ[key]='2'
    import pyarrow
    pyarrow.set_cpu_count(2);pyarrow.set_io_thread_count(2)
    source_manifest=Path(args.source_manifest)
    source=json.loads(source_manifest.read_text())
    paths=[]
    for item in source['files']:
        p=source_manifest.parent/'source'/item['file']
        if sha256_file(p)!=item['sha256']:raise ValueError('source hash mismatch')
        paths.append(p)
    if len(paths)!=2:raise ValueError('benchmark requires exactly2source shards')
    if any(v<=0 for v in (args.max_chars,args.train_rows,args.validation_rows,args.sequence_length)):
        raise ValueError('limits must be positive')
    output=Path(args.output);output.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('pinned_nano_tokenizer',args.tokenizer_module)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    fit_stats={}
    tok=module.RustBPETokenizer.train_from_iterator(training_texts(paths[:1],args.max_chars,fit_stats),32768)
    if tok.get_vocab_size()!=32768:raise ValueError('unexpected vocab size')
    tok.save(str(output/'tokenizer'))
    tok_hash=sha256_file(output/'tokenizer'/'tokenizer.pkl')
    source_hash=sha256_file(source_manifest)
    results={}
    for split, selected, count in [('train',paths[:1],args.train_rows),('validation',paths[1:],args.validation_rows)]:
        stats={}
        batches=(tok.encode(texts,prepend=tok.get_bos_token_id(),num_threads=2)
                 for texts in parquet_text_batches(selected))
        rows=finite_bestfit_rows(batches,args.sequence_length,stats=stats)
        packed=write_rows(output/split,rows,sequence_length=args.sequence_length,vocab_size=32768,
                          tokenizer_sha256=tok_hash,split=split,source_manifest_sha256=source_hash,
                          packing='nanochat-92d63d4-BOS-bestfit-finite-tail',max_rows=count)
        results[split]={'packing':stats,'manifest':packed}
        print(split,packed['rows'],packed['target_tokens'],flush=True)
    probes=['Hello, world!','1234.56 minus 78','{"tool":"calculate","arguments":{"expression":"2+3"}}','नमस्ते 🌍','<|assistant_end|> literal text']
    roundtrip=all(tok.decode(tok.encode(p))==p for p in probes)
    report=dict(status='benchmark_only_not_training_admitted',tokenizer_sha256=tok_hash,
                tokenizer_module_sha256=sha256_file(args.tokenizer_module),fit=fit_stats,
                production_upstream_fit_target_chars=2_000_000_000,source_manifest_sha256=source_hash,
                splits={'train':str(paths[0]),'validation':str(paths[1])},roundtrip_passed=roundtrip,
                results=results,threads=2,
                caveat='Preliminary own tokenizer; benchmark weights must be discarded. No final quality/dedup/acceptance admission claimed.')
    (output/'preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    if not roundtrip:raise ValueError('tokenizer roundtrip failed')


if __name__=='__main__':main()
