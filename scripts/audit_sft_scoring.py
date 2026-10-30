"""Dataset coverage and gold/negative scoring checks; never evaluates model quality."""
import collections,json
from unittest.mock import patch
from sft_common import ROOT,call_text
from evaluate_sft import evaluate_record
coverage={};checked=0
for split in ['train','dev','test']:
 rows=[json.loads(l) for l in (ROOT/f'data/sft-v2/{split}.jsonl').read_text().splitlines()]
 cities=set();topics=set();routes=collections.Counter();ops=set();units=set()
 for r in rows:
  for c in r.get('calls',[]):
   a=c['arguments'];name=c['name']
   if name=='get_weather':cities.add(a['city'])
   if name=='search_notes':topics.add(a['query'])
   if name=='calculate':ops.add(a['op'])
   if name=='convert':units.add((a['from_unit'],a['to_unit']))
  if r['kind']=='chain':routes[' -> '.join(c['name'] for c in r['calls'])]+=1
  if split=='train' or r['kind'] in ['chat','none']:continue
  outputs=[call_text(c) for c in r.get('calls',[])]+[r['expected_answer']]
  with patch('evaluate_sft.generate',side_effect=[{'output':x} for x in outputs]):assert evaluate_record(None,None,r,{})['success'],r['id']
  with patch('evaluate_sft.generate',return_value={'output':'unrelated nonsense 5 zero city?'}):assert not evaluate_record(None,None,r,{})['success'],r['id']
  checked+=1
 assert len(cities)>=5 and len(topics)>=5 and len(routes)==3 and len(ops)==4 and len(units)==6,(split,len(cities),len(topics),dict(routes),ops,units)
 coverage[split]={'cities':sorted(cities),'note_topics':sorted(topics),'chain_routes':dict(routes),'arithmetic_operations':sorted(ops),'conversion_pairs':sorted(units)}
for a,b in [('train','dev'),('train','test'),('dev','test')]:
 for field in ['cities','note_topics']:assert not set(coverage[a][field])&set(coverage[b][field])
result={'passed':True,'gold_and_negative_cases_checked':checked,'coverage':coverage,'limitation':'Synthetic deterministic fixtures, no claim of broad tool or conversation competence.'}
(ROOT/'reports/sft-v2/scoring-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
