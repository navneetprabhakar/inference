"""Prepare exactly the pinned TinyStories archive; no model or training imports."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
EXPECTED_BYTES = 1608001638
EXPECTED_SHA = '26cf7605aca15bc4ea6fa637256400d9d01317b28ed296172b2d1dd160cd7699'
REVISION = 'f54c09fd23315a6f9c86f9dc80f725de7d8f9c64'
URL = f'https://huggingface.co/datasets/roneneldan/TinyStories/resolve/{REVISION}/TinyStories_all_data.tar.gz'

def dump(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, indent=2) + '\n')
    tmp.replace(path)

def tokenize(item):
    import numpy as np
    import sentencepiece as spm
    name, source = item
    tok = spm.SentencePieceProcessor(model_file=str(ROOT/'upstream/tokenizer.model'))
    assert tok.vocab_size() == 32000
    rows = json.loads(Path(source).read_text())
    values = []
    for row in rows:
        values.append(tok.bos_id())
        values.extend(tok.encode(row['story'].strip()))
    array = np.asarray(values, dtype='<u2')
    target = ROOT/'upstream/data/TinyStories_all_data'/(Path(name).stem+'.bin')
    target.write_bytes(array.tobytes())
    return dict(shard=Path(name).name, documents=len(rows), tokens=int(array.size),
                source_bytes=Path(source).stat().st_size,
                token_sha256=hashlib.sha256(array.tobytes()).hexdigest())

def main():
    started = time.monotonic()
    data = ROOT/'upstream/data'
    data.mkdir(exist_ok=True)
    archive = data/'TinyStories_all_data.tar.gz'
    receipt = dict(url=URL, expected_bytes=EXPECTED_BYTES, expected_sha256=EXPECTED_SHA,
                   reserved_body_bytes=EXPECTED_BYTES, prior_project_reserved_body_bytes=46277900016,
                   project_authorized_body_bytes=80000000000, retries=0, status='RESERVED')
    digest = hashlib.sha256(); received = 0; last = 0
    if archive.exists():
        prior=json.loads((ROOT/'download.json').read_text())
        if prior['status']!='COMPLETE_VERIFIED':raise RuntimeError('No retry of incomplete download')
        with archive.open('rb') as source:
            while block:=source.read(4*1024*1024):
                digest.update(block);received+=len(block)
        receipt=prior
        print('Reusing checksum-verified archive offline; no second download.',flush=True)
    else:
        dump(ROOT/'download.json', receipt)
        with urllib.request.urlopen(URL, timeout=60) as response, archive.open('xb') as out:
            while block := response.read(4*1024*1024):
                received += len(block)
                if received > EXPECTED_BYTES: raise RuntimeError('Download byte cap')
                if time.monotonic()-started > 14400: raise RuntimeError('Preparation time cap')
                if shutil.disk_usage(ROOT).free < 60*1024**3: raise RuntimeError('Disk reserve')
                out.write(block); digest.update(block)
                if time.monotonic()-last > 20:
                    print(json.dumps(dict(downloaded=received, total=EXPECTED_BYTES)), flush=True)
                    last = time.monotonic()
    if received != EXPECTED_BYTES or digest.hexdigest() != EXPECTED_SHA:
        raise RuntimeError('Publisher archive digest/size mismatch')
    receipt.update(status='COMPLETE_VERIFIED', received_bytes=received, sha256=digest.hexdigest())
    dump(ROOT/'download.json', receipt)
    extracted = data/'TinyStories_all_data'; extracted.mkdir(exist_ok=True)
    entries = []
    with tarfile.open(archive, 'r:gz') as tf:
        for member in tf:
            if not member.isfile(): continue
            p = Path(member.name)
            if p.is_absolute() or len(p.parts)!=1 or p.suffix != '.json' or member.size > 256*1024**2:
                raise RuntimeError('Unexpected archive member '+member.name)
            if shutil.disk_usage(ROOT).free < 60*1024**3:raise RuntimeError('Extraction disk reserve')
            target = extracted/p.name
            with tf.extractfile(member) as source, target.open('xb') as out:
                shutil.copyfileobj(source, out)
            entries.append((member.name, str(target)))
    entries.sort()
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
        stats = []
        for row in pool.map(tokenize, entries):
            stats.append(row)
            print(json.dumps(dict(tokenized_shard=row['shard'], tokens=row['tokens'], completed=len(stats), total=len(entries))), flush=True)
    train, val = stats[1:], stats[:1]
    report = dict(status='PREPARED_NO_TRAINING', recipe_commit='350e04fe35433e6d2941dce5a1f53308f87058eb',
                  dataset_revision=REVISION, archive_sha256=EXPECTED_SHA,
                  tokenizer_sha256=hashlib.sha256((ROOT/'upstream/tokenizer.model').read_bytes()).hexdigest(),
                  training=dict(documents=sum(x['documents'] for x in train), distinct_corpus_positions=sum(x['tokens'] for x in train)),
                  validation=dict(documents=sum(x['documents'] for x in val), corpus_positions=sum(x['tokens'] for x in val)),
                  split='Sorted shard zero validation; all remaining shards train. Upstream native split, not newly deduplicated.',
                  corpus_position_caveat='Corpus positions are not a claim of unique text or semantic deduplication.',
                  preparation_seconds=time.monotonic()-started, shards=stats)
    dump(ROOT/'data-receipt.json', report)
    print(json.dumps({k:v for k,v in report.items() if k!='shards'}), flush=True)

if __name__ == '__main__': main()
