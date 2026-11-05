"""Download only the byte-pinned publisher archive, without opening its dev/test members."""
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import urlopen
HERE=Path(__file__).resolve().parent
DEST=HERE.parents[1]/'data/snli-semantic'
SIZE=94550081
SHA='afb3d70a5af5d8de0d9d81e2637e0fb8c22d1235c2749d83125ca43dab0dbd3e'
URL='https://archive.nyu.edu/bitstream/2451/41728/2/snli_1.0.zip'
CAP=120*1024**2
REQUIRED_PREFIX=51660554
PREFIX_SHA='b813e05bcc8b9447c00c8323a26860171490c3ecafece9b91c1fad6aeea90acd'
def main():
    DEST.mkdir(exist_ok=True)
    final=DEST/'snli.partial'
    if final.exists():
        with final.open('rb') as f:
            if sha256(f.read(REQUIRED_PREFIX)).hexdigest()==PREFIX_SHA:return
        raise ValueError('Unexpected prefix; refusing to replace it')
    ledger=DEST/'network.json'
    info=json.loads(ledger.read_text()) if ledger.exists() else {'bytes':0}
    if info['bytes']+REQUIRED_PREFIX+262144>CAP:raise ValueError('budget exhausted')
    tmp=DEST/'snli.download';count=0;dg=sha256()
    with urlopen(URL,timeout=90) as f,tmp.open('xb') as out:
        if int(f.headers['Content-Length'])!=SIZE:raise ValueError('archive size mismatch')
        while count<REQUIRED_PREFIX:
            piece=f.read(min(2**20,REQUIRED_PREFIX-count))
            if not piece:raise IOError('truncated before train member completed')
            out.write(piece);dg.update(piece);count+=len(piece)
            ledger.write_text(json.dumps({'bytes':info['bytes']+count,'cap':CAP}))
    if dg.hexdigest()!=PREFIX_SHA:raise ValueError('archive prefix mismatch')
    tmp.rename(final)
if __name__=='__main__':main()
