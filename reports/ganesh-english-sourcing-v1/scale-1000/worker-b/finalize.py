import json,pathlib,hashlib
R=pathlib.Path(__file__).resolve().parent;ROOT=R.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dig(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
manual=json.loads((R/'manual.json').read_text()) if (R/'manual.json').exists() else {}
exclude=set(json.loads((R/'cross-worker-replace.json').read_text())['groups'])
staged={}
for p in sorted(R.glob('*.staged.jsonl')):
 for l in p.read_text().splitlines():
  r=json.loads(l);staged[r['group']]=r
out=[];reviews=[]
for g,row in staged.items():
 if g in exclude or g not in manual:continue
 m=manual[g]
 if m['messages_sha256']!=dig(row['messages']):continue
 if m.get('decision')!='pass':continue
 if 'recall_override' in m:row['recall_probe'].update(m['recall_override'])
 q=row['recall_probe'];assert q['probe_turn']-q['last_support_turn']>=3
 review={'group':g,'decision':'pass','messages_sha256':dig(row['messages']),'assistant_turns_reviewed':len(row['messages'])//2,'reviewed_turn_numbers':list(range(1,len(row['messages'])//2+1)),'rationale':m['note'],'reviewer':m.get('reviewer','worker-b orchestrator full content inspection'),'independent_release_acceptance':False,'training_admitted':False}
 reviews.append(review)
 if m.get('external_receipt') and m['external_receipt'] not in row['review_receipts']:row['review_receipts'].append(m['external_receipt'])
 out.append(row)
rp=R/('orchestrator-review-'+dig(reviews)[:16]+'.json');rp.write_text(json.dumps(reviews,indent=2))
for row in out:
 row['orchestrator_review']='pass';row['review_receipts']=[x for x in row['review_receipts'] if 'orchestrator-review' not in x['path']]+[{'path':str(rp.relative_to(ROOT)),'sha256':sha(rp)}]
(R/'accepted.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in out))
progress={'target':240,'staged':len(staged),'accepted':len(out),'manual_inspected':len(manual),'excluded_mechanism_duplicates':sorted(exclude),'accepted_sha256':sha(R/'accepted.jsonl') if out else None,'state':'in_progress','training_admitted':False,'release_eligible':False}
(R/'progress.json').write_text(json.dumps(progress,indent=2));print(json.dumps(progress))
