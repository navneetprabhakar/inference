"""Recover only the complete original train member from the NYU response and cross-check Stanford train text."""
from hashlib import sha256,file_digest
from pathlib import Path
import json,re,struct,zlib
from urllib.request import urlopen
from acquire import HERE,DEST,CAP,SHA
MEMBER='snli_1.0/snli_1.0_train.jsonl'
CONVERSION_SHA='ef9a7b25d97390a62aeda7abe26aec8640600f50b818eaeb9107097d60ac6620'
SIZE=19614612
CONVERSION_URL='https://huggingface.co/datasets/stanfordnlp/snli/resolve/cdb5c3d5eed6ead6e5a341c8e56e669bb666725b/plain_text/train-00000-of-00001.parquet'
def hashfile(path):
    with path.open('rb') as f:return file_digest(f,'sha256').hexdigest()
def recover():
    zip_path=DEST/'snli_1.0.zip'
    if not zip_path.exists():zip_path=DEST/'snli.partial'
    data=zip_path.read_bytes()
    # Inspect filename headers only. No dev/test compressed payload is decompressed.
    header=data.find(MEMBER.encode())
    at=header-30
    hd=struct.unpack_from('<4s5H3I2H',data,at)
    if hd[0]!=b'PK\x03\x04' or hd[3]!=8 or data[header:header+hd[-2]]!=MEMBER.encode():raise ValueError('train header')
    begin=header+hd[-1]+hd[-2]
    nxt=begin+47356099+16
    sig,expected_crc,packed,size=struct.unpack_from('<4s3I',data,nxt-16)
    assert sig==b'PK\x07\x08' and packed==nxt-16-begin and size==487457790
    obj=zlib.decompressobj(-15);crc=0;count=0;dg=sha256()
    path=DEST/'official-train.jsonl'
    with path.open('wb') as f:
        for start in range(begin,begin+packed,256*1024):
            piece=obj.decompress(data[start:min(start+256*1024,begin+packed)])
            crc=zlib.crc32(piece,crc);count+=len(piece);dg.update(piece);f.write(piece)
    assert obj.eof and not obj.unused_data and crc==expected_crc and count==size
    assert dg.hexdigest()=='ee95dfbc57800f7b1f62b7602ad2b176c2b983210435a49238e660324a01e963'
    return dict(original_member=MEMBER,member_sha256=dg.hexdigest(),uncompressed_bytes=count,crc32=f'{crc:08x}',compressed_bytes=packed,
                original_archive_bytes_received=len(data),original_response_sha256=sha256(data).hexdigest(),full_archive_sha_verified=len(data)==94550081 and sha256(data).hexdigest()==SHA)
def validate():
    import pyarrow.parquet as pq
    rec=recover()
    path=DEST/'stanford-train.parquet'
    if not path.exists():
        ledger=DEST/'network.json'
        n=json.loads(ledger.read_text())['bytes']
        # Includes 16-byte diagnostics and a 256KiB allowance for metadata/probes.
        if n+SIZE+1+262144>CAP:raise ValueError('budget exceeded')
        with urlopen(CONVERSION_URL,timeout=60) as f:
            assert int(f.headers.get('Content-Length',SIZE))==SIZE
            data=f.read(SIZE+1)
        if len(data)!=SIZE or sha256(data).hexdigest()!=CONVERSION_SHA:raise ValueError('train conversion mismatch')
        path.write_bytes(data);ledger.write_text(json.dumps(dict(bytes=n+len(data),cap=CAP)))
    assert hashfile(path)==CONVERSION_SHA
    labels=['entailment','neutral','contradiction'];count=0
    with (DEST/'official-train.jsonl').open() as orig:
        for batch in pq.ParquetFile(path).iter_batches(batch_size=512,use_threads=False):
            for other in batch.to_pylist():
                row=json.loads(next(orig));gold = '-' if other['label']==-1 else labels[other['label']]
                assert row['sentence1']==other['premise'] and row['sentence2']==other['hypothesis'] and row['gold_label']==gold
                count+=1
        assert not orig.readline() and count==550152
    rec.update(official_conversion_sha256=CONVERSION_SHA,independently_verified_original_pairs=count,official_conversion_url=CONVERSION_URL)
    (HERE/'source-recovery.json').write_text(json.dumps(rec,indent=2)+'\n');print(rec)
if __name__=='__main__':validate()
