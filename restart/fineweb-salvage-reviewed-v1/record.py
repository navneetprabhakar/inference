import json,pathlib,sys
p=pathlib.Path(__file__).parent;s={x['review_index']:x for x in json.load(open(p/'sample.json'))}
existing=[json.loads(x) for x in (p/'judgments.jsonl').read_text().splitlines()] if (p/'judgments.jsonl').exists() else []
seen={x['review_index'] for x in existing};new=[]
for line in sys.stdin:
 if not line.strip():continue
 i,label,note=line.strip().split('|',2);i=int(i);assert i not in seen and label in ['pass','minor','fail','major'];seen.add(i)
 new.append(dict(audit_id=s[i]['audit_id'],review_index=i,label=label,note=note,reviewer='assistant direct full-text reading',major_corruption_or_boilerplate=label=='major'))
with (p/'judgments.jsonl').open('a') as f:
 for x in new:f.write(json.dumps(x)+'\n')
