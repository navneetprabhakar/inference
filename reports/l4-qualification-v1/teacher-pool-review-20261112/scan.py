import json,re,hashlib,collections
from pathlib import Path
root=Path('runs/teacher-student-execution-v1/production');seen=set();seen_users=set();stats=collections.Counter();domains=collections.Counter();values=collections.defaultdict(set);flagged=[]
for p in sorted(root.glob('cohort-*/batch-*/candidates.jsonl')):
 for line in p.read_text().splitlines():
  d=json.loads(line);s=d['provenance']['seed'];m=d['messages'];stats['candidates']+=1;domains[s['domain']]+=1
  key=json.dumps(m,sort_keys=True);users=json.dumps([x['content'] for x in m if x['role']=='user'])
  stats['exact_duplicate_conversations']+=key in seen;seen.add(key);stats['duplicate_user_sequences']+=users in seen_users;seen_users.add(users)
  for i,k in enumerate(s['keys']):values[s['domain']+'/'+k].update([s['initial'][i]]+([s['updates'][i]] if i<2 else []))
  updates=[False,False];reasons=set()
  for msg in m[:-2]:
   text=msg['content'].casefold()
   if msg['role']=='user':
    for i in range(2):
     if s['updates'][i].casefold() in text:updates[i]=True
   else:
    for i in range(2):
     if updates[i] and re.search(r'(?<!\w)'+re.escape(s['initial'][i].casefold())+r'(?!\w)',text):reasons.add('old_value_mentioned_after_update_requires_review')
    if re.search(r'\bi (?:have |already )?(?:sent|booked|purchased|uploaded|saved the file|updated the file)\b',text):reasons.add('external_action_claim_requires_review')
  if not all(updates):reasons.add('missing_explicit_update')
  if m[-1]['content']!=s['expected_final']:reasons.add('wrong_final_state')
  if reasons:
   flagged.append({'id':s['id'],'path':str(p),'reasons':sorted(reasons)})
   stats.update(reasons)
r={'training_admitted':False,'stats':dict(stats),'domains':dict(domains),'distinct_field_values':{k:len(v) for k,v in values.items()},'flags':flagged,'limits':['Heuristic mentions can be legitimate comparisons; flags are review requests, not proven errors.','Five whole sampled dialogues reviewed in chat; insufficient for whole-pool semantic admission.','Small closed value pools may reinforce memorization; assess value-heldout generalization before admitting.']}
Path('reports/l4-qualification-v1/teacher-pool-review-20261112/scan.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='flags'},indent=2))
