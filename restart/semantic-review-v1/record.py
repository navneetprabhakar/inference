import json,pathlib,sys
p=pathlib.Path(__file__).parent
source=sys.argv[1]
samples={x['review_index']:x for x in json.load(open(p/'sample.json')) if x['source']==source}
with open(p/'judgments.jsonl','a') as out:
 for line in sys.stdin:
  if not line.strip():continue
  index,label,note=line.strip().split('|',2)
  x=samples[int(index)]
  out.write(json.dumps(dict(audit_id=x['audit_id'],source=source,review_index=int(index),label=label,note=note,reviewer='assistant direct full-text reading',major_corruption_or_boilerplate=label=='major'))+'\n')
