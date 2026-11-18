import json,hashlib,pathlib
from arithmetic_audit import A,check
R=pathlib.Path(__file__).parent
rows=list(map(json.loads,(R/'selected.jsonl').read_text().splitlines()));audit=json.loads((R/'arithmetic-audit.json').read_text());entries={x['group']:x for x in audit['entries']}
assert len(rows)==len(entries)==24
for row in rows:
 digest=hashlib.sha256(json.dumps(row['messages'],ensure_ascii=False,sort_keys=True).encode()).hexdigest(); e=entries[row['group']];assert e['messages_sha256']==digest
 ops=A[row['group'][-2:]];assert len(ops)==len(e['turns'])==len(row['messages'])//2
 for i,(turn,checks) in enumerate(zip(e['turns'],ops)):
  assert turn['turn']==i+1 and turn['quoted_assistant_reply']==row['messages'][2*i+1]['content'];assert turn['checks']==[check(*op) for op in checks];assert turn['explanation_review']
print(json.dumps({'sessions':len(rows),'assistant_turns':sum(len(r['messages'])//2 for r in rows),'exact_calculations':sum(len(t['checks']) for e in entries.values() for t in e['turns']),'pass':True}))
