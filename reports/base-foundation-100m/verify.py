"""Independently verify packed source boundaries, disjointness and sampled decode."""
import hashlib,json,random,sqlite3,sys
from collections import Counter
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tokenizer import load
D=ROOT/'data/base-foundation-100m'
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
m=json.loads((D/'manifest.json').read_text()); docs=[json.loads(x) for x in (D/'documents.jsonl').read_text().splitlines()];windows=json.loads((D/'validation-blocks.json').read_text())
assert sha(D/'documents.jsonl')==m['documents_sha256']
assert sha(D/'validation-blocks.json')==m['validation_blocks_sha256']
arrays={};offset=Counter();domains={'train':set(),'validation':set()};ids=set();hashes=set();urls=set();records={}
for split in domains:
 p=D/f'fineweb-{split}.u16';s=m['shards']['fineweb-'+split]
 assert p.stat().st_size==s['tokens']*2 and sha(p)==s['sha256']
 arrays[split]=np.memmap(p,dtype='<u2',mode='r');assert int(arrays[split].max())<=50256
for r in docs:
 split=r['split'];a=arrays[split];n=r['tokens'];o=r['offset']
 assert o==offset[split] and n>1 and int(a[o+n-1])==50256
 assert not np.any(a[o:o+n-1]==50256)
 assert r['document_id'] not in ids and r['normalized_sha256'] not in hashes and r['canonical_url'] not in urls
 ids.add(r['document_id']);hashes.add(r['normalized_sha256']);urls.add(r['canonical_url']);domains[split].add(r['group']);records[r['document_id']]=r;offset[split]+=n
assert not domains['train']&domains['validation']
receipt=json.loads((D/'custody.json').read_text())
assert receipt['state']=='cleared' and sha(D/'custody.json')==m['custody_receipt_sha256']
assert receipt['candidate_database_sha256']==m['candidate_database_sha256']==sha(D/'candidates.sqlite')
assert not ids&set(receipt['excluded_doc_ids'])
assert len(windows)>=128 and len({w['document_id'] for w in windows})==len(windows)
for w in windows:
 r=records[w['document_id']];assert r['split']=='validation' and r['group']==w['group'] and r['raw_sha256']==w['document_sha256']
 assert r['offset']<=w['start'] and w['start']+w['max_length']<=r['offset']+r['tokens'] and w['max_length']>=1025
for split in domains:assert offset[split]==len(arrays[split])
c=sqlite3.connect(f'file:{D / "candidates.sqlite"}?mode=ro',uri=True);tok=load();samples=random.Random(20261106).sample(docs,64)
for r in samples:
 text=c.execute('select text from documents where priority=?',(r['order_sha256'],)).fetchone()[0]
 decoded=tok.decode(arrays[r['split']][r['offset']:r['offset']+r['tokens']-1].tolist())
 assert decoded==text and hashlib.sha256(text.encode()).hexdigest()==r['raw_sha256']
result=dict(state='passed',documents=len(docs),tokens=dict(offset),domains={k:len(v) for k,v in domains.items()},validation_windows=len(windows),source_decode_samples=64,checks='All shard hashes/counts/token ranges, every document offset/EOT boundary, global normalized hash and URL uniqueness, domain split disjointness, fixed window bounds, matched frozen custody receipt and zero excluded IDs, 64 deterministic full source decode comparisons')
(D/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
