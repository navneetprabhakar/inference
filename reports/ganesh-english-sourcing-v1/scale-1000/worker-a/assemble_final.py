import json,pathlib,hashlib,collections,importlib.util
R=pathlib.Path(__file__).resolve().parent;ROOT=R.parents[3]
spec=importlib.util.spec_from_file_location('worker',R/'run_worker.py');w=importlib.util.module_from_spec(spec);spec.loader.exec_module(w)
def rows(p):return [json.loads(l) for l in p.read_text().splitlines()]
# Inspectors create these only after seeing every final assistant target.
inspections=[]
for p in sorted(R.glob('manual-b*.json'))+sorted(R.glob('manual-final-*.json')):
 inspections.extend(json.loads(p.read_text()))
support=R.parent/'worker-c/a-support/manual-review-final.json'
if support.exists():
 data=json.loads(support.read_text());inspections.extend(data if isinstance(data,list) else data['reviews'])
manual={}
for e in inspections:
 g=e['group'];h=e.get('content_sha256',e.get('messages_sha256'));decision=e['decision'];nums=e.get('reviewed_turns',e.get('reviewed_turn_numbers'));note=e.get('notes',e.get('rationale'))
 manual[g,h]={'group':g,'messages_sha256':h,'decision':decision,'assistant_turns_reviewed':len(nums),'reviewed_turn_numbers':nums,'rationale':note}
candidates=[]
for p in sorted(R.glob('b*.accepted.jsonl')):candidates.extend(rows(p))
for p in sorted(R.glob('manual-repairs*.cold-accepted.jsonl')):candidates.extend(rows(p))
selected={};excluded=[];missing=[]
for r in candidates:
 m=manual.get((r['group'],r['content_sha256']))
 if not m:missing.append(r['group']);continue
 if m['decision']!='pass':excluded.append(r['group']);continue
 assert sorted(m['reviewed_turn_numbers'])==list(range(1,len(r['messages'])//2+1))
 selected[r['group']]=r
permanent={'a_034','a_061','a_104','a_156','a_230'}
for g in permanent:selected.pop(g,None)
out=list(sorted(selected.values(),key=lambda x:x['group']))
for r in out:
 assert w.digest(r['messages'])==r['content_sha256']
 raw=ROOT/r['generation']['raw_artifact'];assert w.sha(raw)==r['generation']['raw_sha256']
 c=next(x for x in json.loads(raw.read_text())['conversations'] if x['group']==r['group']);assert w.messages(c)==r['messages']
 planfile=ROOT/r['plan_receipt']['path'];assert w.sha(planfile)==r['plan_receipt']['sha256'];plan=next(x for x in json.loads(planfile.read_text()) if x['group']==r['group']);errs,enc=w.validate(c,plan);assert not errs,(r['group'],errs)
 for ref in r['review_receipts']:
  rp=ROOT/ref['path'];assert w.sha(rp)==ref['sha256'];rr=next(x for x in json.loads(rp.read_text())['reviews'] if x['group']==r['group']);assert rr['content_sha256']==r['content_sha256'];assert rr['decision']=='accept' and rr['memory_annotation_valid'] and rr['distinct_scenario'];assert sorted(x['turn'] for x in rr['turn_reviews'])==list(range(1,len(r['messages'])//2+1));assert all(x['decision']=='pass' for x in rr['turn_reviews'])
 r.update(enc)
(R/'accepted.jsonl').write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in out))
final=[manual[r['group'],r['content_sha256']] for r in out];w.write(R/'final-content-review.json',final)
w.write(R/'final-assembly-status.json',{'selected':len(out),'target':240,'assistant_turns':sum(len(x['messages'])//2 for x in out),'uninspected_candidate_groups':sorted(set(missing)-set(selected)-permanent),'excluded_or_superseded':sorted(set(excluded)-set(selected)),'content_review_sha256':w.sha(R/'final-content-review.json'),'accepted_sha256':w.sha(R/'accepted.jsonl'),'native_replay':'pass','training_admitted':False})
print(json.dumps({'selected':len(out),'missing':sorted(set(missing)-set(selected)-permanent),'excluded':sorted(set(excluded)-set(selected))}))
