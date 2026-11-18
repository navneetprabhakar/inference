import collections,hashlib,json,re
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];R=ROOT/'runs/ganesh-english-sourcing-v1/scale-1000/worker-c'
rows=[json.loads(x) for x in (R/'baseline.jsonl').read_text().splitlines()]
normalize=lambda x: re.sub(r'\s+',' ',x).strip().lower()
texts=collections.defaultdict(list)
for r in rows:
 for i,m in enumerate([m for m in r['messages'] if m['role']=='assistant'],1):texts[normalize(m['content'])].append([r['group'],i])
family=collections.Counter(r['family'] for r in rows);lengths=collections.Counter(sum(m['role']=='assistant' for m in r['messages']) for r in rows)
# Candidate pairs, lexical hints only; do not assert independence from low overlap.
pairs=[]
for i,r in enumerate(rows):
 rt=set(re.findall(r'[a-z]+',' '.join(m['content'].lower() for m in r['messages'])))
 for t in rows[:i]:
  tt=set(re.findall(r'[a-z]+',' '.join(m['content'].lower() for m in t['messages'])))
  score=len(rt&tt)/len(rt|tt)
  if score>=.48:pairs.append({'groups':[r['group'],t['group']],'word_set_jaccard':round(score,4)})
report={'sessions':len(rows),'assistant_turns':sum(k*v for k,v in lengths.items()),'family_counts':dict(family),'assistant_turn_histogram':dict(lengths),'repeated_exact_normalized_assistant_targets':[{ 'text':k,'occurrences':v} for k,v in texts.items() if len(v)>1],'lexical_overlap_pairs':sorted(pairs,key=lambda x:-x['word_set_jaccard']),'limitations':['Word-set overlap is triage, not semantic decontamination.','All rows are train candidates; no sealed evaluation accessed.','Template-family split grouping must union scenario/source lineage and mechanism, not merely group IDs.']}
(O/'structural-audit.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['repeated_exact_normalized_assistant_targets','lexical_overlap_pairs']}));print('overlap pairs',len(pairs))
