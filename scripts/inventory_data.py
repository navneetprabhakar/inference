"""Read retained data without importing legacy code or treating old approvals as evidence."""
import argparse, collections, json, sqlite3
from pathlib import Path
import pyarrow.parquet as pq

p=argparse.ArgumentParser()
p.add_argument('--archive',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(); root=a.archive.resolve()
out={'archive':str(root),'scope':'Physical files and parsed records; not deduplicated/admitted training volume.'}
small=root/'restart/mac15m-feasibility-v1/upstream/data/TinyStories_all_data'
shards=[]
for path in sorted(small.glob('*.json')):
    rows=json.loads(path.read_text()); counts=collections.Counter()
    for row in rows: counts.update(row.keys())
    shards.append({'file':str(path),'rows':len(rows),'bytes':path.stat().st_size,'keys':dict(counts),'sample_text_chars':len(rows[0].get('story','')) if rows else 0})
out['tinystories']={'shards':shards,'rows':sum(x['rows'] for x in shards),'note':'Native data archive; not a fresh train/eval split. Rebuild splits and deduplicate before training.'}
out['parquet']=[]
for path in sorted((root/'restart/execution-v1/m2-intake/raw').glob('*.parquet')):
    f=pq.ParquetFile(path); sample=next(f.iter_batches(batch_size=3)).to_pylist()
    out['parquet'].append({'file':str(path),'bytes':path.stat().st_size,'rows':f.metadata.num_rows,'columns':f.schema.names,'sample_text_characters':[len(x.get('text','')) for x in sample]})
db=root/'restart/corpus-audit-v1/audit.sqlite'
c=sqlite3.connect(f'file:{db}?mode=ro',uri=True)
out['legacy_index_counts_not_fresh_quality_verification']=[dict(zip(['source','records','heldout','legacy_token_estimate'],r)) for r in c.execute('SELECT source,count(*),sum(held),sum(tokens) FROM docs GROUP BY source')]
c.close()
out['incomplete_downloads']=[{'file':str(x),'bytes':x.stat().st_size} for x in root.rglob('*.partial')]
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ['tinystories','incomplete_downloads']},indent=2));print('TinyStories rows:',out['tinystories']['rows'],'shards:',len(shards))
