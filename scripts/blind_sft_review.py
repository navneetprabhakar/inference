"""Export preselected chat/no-tool outputs without model labels; no automated judge."""
import argparse,hashlib,json,random
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('reports',nargs='+',type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
items=[];key={}
for report in a.reports:
 rows=json.loads(report.read_text())
 for kind in ['chat','none']:
  for r in [x for x in rows if x['kind']==kind][:30]:
   identity=str(report.resolve())+'|'+r['id'];blind=hashlib.sha256(identity.encode()).hexdigest()[:12]
   key[blind]={'report':str(report),'case':r['id']}
   items.append({'blind_id':blind,'kind':kind,'prompt':r['prompt'],'answer':r['output'],'relevance_0_2':None,'coherence_0_2':None,'correctness_0_2':None,'unsupported_claims':None,'notes':''})
random.Random(7109).shuffle(items);a.output.mkdir(parents=True,exist_ok=True)
(a.output/'review.json').write_text(json.dumps(items,indent=2))
(a.output/'key.json').write_text(json.dumps(key,indent=2))
(a.output/'rubric.txt').write_text('Review before opening key.json. Relevance: 0 off topic, 1 partial, 2 addresses request. Coherence: 0 unintelligible, 1 material errors/repetition, 2 clear English. Correctness: 0 wrong, 1 incomplete/uncertain, 2 correct; use null if not verifiable. Mark unsupported claims separately. A usable answer requires all three scores 2 and no unsupported claims. Report denominators and unrated cases; do not count abstention alone as success. Fixed first 30 cases per kind, no cherry picking.\n')
