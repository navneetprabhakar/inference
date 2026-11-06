"""Train-only unigram reference on the exact fixed validation windows."""
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT/'data/base-foundation-100m'

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    manifest=json.loads((DATA/'manifest.json').read_text())
    counts=np.zeros(50257,dtype=np.int64)
    for split in ('train','validation'):
        path=DATA/f'fineweb-{split}.u16'
        assert sha(path)==manifest['shards'][f'fineweb-{split}']['sha256']
    train=np.memmap(DATA/'fineweb-train.u16',dtype='<u2',mode='r')
    for offset in range(0,len(train),1_000_000):
        counts+=np.bincount(train[offset:offset+1_000_000].astype(np.int64),minlength=50257)
    nll=-np.log((counts+.5)/(counts.sum()+.5*len(counts)))
    validation=np.memmap(DATA/'fineweb-validation.u16',dtype='<u2',mode='r')
    blocks=json.loads((DATA/'validation-blocks.json').read_text())
    if isinstance(blocks,dict): blocks=blocks['blocks']
    losses=[]
    for block in blocks:
        start=block.get('offset',block.get('start'))
        losses.append(float(nll[validation[start+1:start+513]].mean()))
    result=dict(model='train-token unigram with Jeffreys smoothing alpha=0.5',
                manifest_sha256=sha(DATA/'manifest.json'),
                validation_blocks_sha256=sha(DATA/'validation-blocks.json'),
                training_tokens=len(train),window_targets=512,windows=len(losses),
                mean_ce=float(np.mean(losses)),document_losses=losses)
    out=ROOT/'reports/base-foundation-100m/unigram.json'
    out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='document_losses'}))

if __name__=='__main__':main()
