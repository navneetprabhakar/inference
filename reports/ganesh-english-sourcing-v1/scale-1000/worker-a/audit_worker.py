import collections,hashlib,json,pathlib,re,sys
R=pathlib.Path(__file__).resolve().parent;ROOT=R.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
rows=[json.loads(l) for l in (R/'accepted.jsonl').read_text().splitlines()]
assert len({r['group'] for r in rows})==len(rows)
assert len({r['content_sha256'] for r in rows})==len(rows)
for r in rows:
 assert digest(r['messages'])==r['content_sha256']
 raw=ROOT/r['generation']['raw_artifact'];assert sha(raw)==r['generation']['raw_sha256']
 originals={c['group']:c for c in json.loads(raw.read_text())['conversations']};c=originals[r['group']]
 m=[{'role':role,'content':t[key]} for t in c['turns'] for role,key in [('user','user'),('assistant','assistant')]]
 assert r['messages']==m
 p=ROOT/r['plan_receipt']['path'];assert sha(p)==r['plan_receipt']['sha256']
 assert r['group'] in [x['group'] for x in json.loads(p.read_text())]
 for ref in r['review_receipts']:
  path=ROOT/ref['path'];assert sha(path)==ref['sha256']
  rr=next(x for x in json.loads(path.read_text())['reviews'] if x['group']==r['group'])
  assert rr['content_sha256']==r['content_sha256'] and rr['decision']=='accept'
  assert rr['memory_annotation_valid'] and rr['distinct_scenario']
  assert sorted(t['turn'] for t in rr['turn_reviews'])==list(range(1,len(m)//2+1))
  assert all(t['decision']=='pass' and len(t['rationale'].split())>=3 for t in rr['turn_reviews'])
 assert r['max_generation_prompt']+256<=2048 and r['max_reply_targets']<=256
 assert {e['tools_enabled'] for e in r['encoding']}=={False,True}
 assert not r['training_admitted'] and not r['independent_release_review']
def grams(r):
 words=re.findall(r'[a-z0-9]+',' '.join(m['content'] for m in r['messages']).lower());return set(zip(*(words[i:] for i in range(5))))
g=[grams(r) for r in rows]; pairs=[]
for i in range(len(rows)):
 for j in range(i):
  score=len(g[i]&g[j])/max(1,len(g[i]|g[j]))
  if score>=.35:pairs.append({'a':rows[i]['group'],'b':rows[j]['group'],'jaccard5':score})
report={'accepted':len(rows),'assistant_turns':sum(len(r['messages'])//2 for r in rows),'family_counts':dict(collections.Counter(r['family'] for r in rows)),'turn_lengths':dict(collections.Counter(len(r['messages'])//2 for r in rows)),'exact_raw_review_plan_bindings':'pass','native_both_policy_encoding':'pass','max_prompt':max(r['max_generation_prompt'] for r in rows),'max_reply':max(r['max_reply_targets'] for r in rows),'max_context':max(e['tokens'] for r in rows for e in r['encoding']),'target_positions':sum(r['encoding'][0]['assistant_targets'] for r in rows),'lexical_overlap_flags':pairs,'training_admitted':False,'release_independent':False,'limitations':['Fresh review is separate CLI session of same requested model; not independent release evaluation.','Lexical pair screen is not semantic decontamination.','No training or model-quality claim.']}
(R/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
