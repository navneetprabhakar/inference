"""Freeze eight full raw documents for extraction discovery, not acceptance."""
import hashlib,json,random
from pathlib import Path
import pyarrow.parquet as pq
O=Path(__file__).resolve().parent/'m2-intake'
d=json.loads((O/'wikipedia-pilot-download.json').read_text())
p=Path(d['local_file'])
assert hashlib.sha256(p.read_bytes()).hexdigest()==d['sha256']
f=pq.ParquetFile(p)
selected=set(random.Random(2026102103).sample(range(f.metadata.num_rows),8))
rows=[];offset=0
for b in f.iter_batches(batch_size=128):
 for row in b.to_pylist():
  if offset in selected:
   rows.append(dict(row,row_index=offset,text_sha256=hashlib.sha256(row['text'].encode()).hexdigest(),role='discovery only; exclude page family from future acceptance samples'))
  offset+=1
out=O/'wikipedia-discovery-sample.jsonl'
if out.exists():raise FileExistsError('Discovery sample already exists; do not overwrite')
out.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
print(json.dumps({'raw_rows':offset,'selected_rows':[r['row_index'] for r in rows],'sample_sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
