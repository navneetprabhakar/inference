import json,collections
from pathlib import Path
P=Path(__file__).resolve().parent
rows=[json.loads(s) for s in (P/'private/responses.jsonl').read_text().splitlines()];old=[json.loads(s) for s in (P.parent/'retained-screen-2026-10-29/private/arm-1/evaluation/1000-matrix.jsonl').read_text().splitlines()];baseline={r['id']:r for r in old if r['cell']=='D' and r['family'] in ['name','time','location','distractor']};counts={}
for r in rows:
 key='|'.join(r[k] for k in ['family','scope','style','instruction']);v=counts.setdefault(key,{'correct':0,'total':0});v['correct']+=int(r['correct']);v['total']+=1
 if (r['scope'],r['style'],r['instruction'])==('full','kv','original'):
  b=baseline[r['source_id']];assert (r['response'],r['correct'],r['eos'],r['bos'],r['overflow'])==(b['response'],b['complete'],b['eos'],b['bos'],b['overflow'])
paired=[]
for axis,a,b in [('scope','full','single'),('style','kv','sentence'),('instruction','original','copy')]:
 other=[k for k in ['scope','style','instruction'] if k!=axis];left={tuple([r['source_id']]+[r[k] for k in other]):r for r in rows if r[axis]==a};right={tuple([r['source_id']]+[r[k] for k in other]):r for r in rows if r[axis]==b};assert left.keys()==right.keys()
 for family in ['name','time','location','distractor']:
  keys=[k for k in left if left[k]['family']==family];paired.append({'axis':axis,'family':family,'from':a,'to':b,'gains':sum(not left[k]['correct'] and right[k]['correct'] for k in keys),'losses':sum(left[k]['correct'] and not right[k]['correct'] for k in keys),'contrasts':len(keys),'independent_scenarios':32})
result={'counts':counts,'paired_contrasts':paired,'original_responses_reproduced':128,'limits':'Same32 previously exposed scenarios per family reused across8conditions. One checkpoint; this is not fresh heldout evidence. Scope changes both fact count and prompt length; query change is one explicit-copy instruction.'};(P/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
for family in ['name','time','location','distractor']:
 print(family,[(k.split('|')[1:],v['correct']) for k,v in counts.items() if k.startswith(family+'|')])
