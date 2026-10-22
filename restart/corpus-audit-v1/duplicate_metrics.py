from pathlib import Path
from collections import defaultdict,Counter
import sqlite3,json
O=Path(__file__).resolve().parent;c=sqlite3.connect(f'file:{O}/audit.sqlite?mode=ro',uri=True)
rows={i:(s,h) for i,s,h in c.execute('select id,source,sha from docs')};p={i:i for i in rows}
def root(i):
 while p[i]!=i:p[i]=p[p[i]];i=p[i]
 return i
for line in (O/'near-pairs.tsv').open():
 a,b,_,kind=line.rstrip().split('\t');a=int(a);b=int(b);p[root(b)]=root(a)
sources={'TinyStories','FineWeb','Cosmopedia'};groups=defaultdict(list);counts=defaultdict(Counter);hashes=defaultdict(set)
for i,(s,h) in rows.items():
 if s not in sources:continue
  # Raw snapshot denominator includes official heldouts.
 counts[s]['raw_records']+=1
 if h in hashes[s]:counts[s]['normalized_exact_redundant_records']+=1
 hashes[s].add(h);groups[root(i)].append(i)
for ids in groups.values():
 if len({rows[i][1] for i in ids})>1:
  for i in ids:counts[rows[i][0]]['records_in_nonexact_near_components']+=1
for s,v in counts.items():
 v['normalized_exact_redundancy_rate']=v['normalized_exact_redundant_records']/v['raw_records'];v['nonexact_near_component_participation_rate']=v['records_in_nonexact_near_components']/v['raw_records']
result={'denominator':'All candidate snapshot records, including official heldouts, before quality and leakage exclusions. Rates are separate and overlap; do not sum. Near components may be transitive and include protection links.','by_source':counts}
(O/'duplicate-metrics.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
