"""Hash-select training-only review cases; no validation text is displayed."""
from pathlib import Path
from hashlib import sha256
import json,sys
from collections import defaultdict
HERE=Path(__file__).resolve().parent
DEST=HERE.parents[1]/'data/text-continuation-work'
def select(source,qty,salt):
    samples=defaultdict(list)
    for line in (DEST/source).open():
        r=json.loads(line)
        if r['split']=='train':samples[r.get('book',r['source'])].append(r)
    return {k:sorted(v,key=lambda r:sha256((salt+r['document_id']).encode()).digest())[:qty] for k,v in samples.items()}
if __name__=='__main__':
    for k,v in select(sys.argv[1],int(sys.argv[2]),sys.argv[3]).items():
        for r in v:print(k,r['document_id'],r['text'])
