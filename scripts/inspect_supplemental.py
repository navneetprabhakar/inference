"""Bounded source inspection; exact physical row counts are not deduplication."""
import json,sqlite3
from pathlib import Path
import pyarrow.parquet as pq
import pyarrow.compute as pc
root=Path(__file__).resolve().parents[1];archive=root.parent/'inference-archive-20261029';history=root.parent/'inference-history-20261021'
out={'scope':'Selected raw sources; no fresh license, deduplication or training admission claim','jsonl':[]}
for rel in ['data/dolly-complete-v1/rows.jsonl','data/iteration-two-oasst2-snapshot-v1/trees.jsonl']:
 p=history/rel;n=0;keys=None
 with p.open() as f:
  for line in f:
   if line.strip():
    row=json.loads(line);n+=1
    if keys is None:keys=list(row)
 out['jsonl'].append({'path':str(p),'rows':n,'first_record_keys':keys,'bytes':p.stat().st_size})
p=archive/'restart/execution-v1/m2-intake/raw/b393f51fefab26cd6f4c8f65707c1924f6666c4961a0ebebe04bb57f7ec832de.parquet'
t=pq.read_table(p,columns=['token_count']);out['fineweb_upstream_token_count_sum']=pc.sum(t['token_count']).as_py();out['token_caveat']='Upstream tokenizer count; not new-tokenizer training tokens, not unique-token count.'
p=archive/'restart/mac15m-feasibility-v1/data-receipt.json';x=json.loads(p.read_text());out['tinystories_legacy_token_estimate']=sum(s['tokens'] for s in x['shards'])
out['tinystories_legacy_token_caveat']='Prior tokenizer receipt only; actual record counts freshly parsed separately.'
(root/'reports/supplemental-data.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
