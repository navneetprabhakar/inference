import copy,json,re,hashlib
from build import ROOT,PRIVATE,P,save
old=json.loads((P/'restart/conversation-improvement-v1/private/grounding.json').read_text());rows=[]
for family in ['name','time']:
 source=[r for r in old if r['family']==family];labels={r['messages'][1]['content'] for r in source}
 for i,r in enumerate(source[:8]):
  original=r['messages'][1]['content']
  if family=='name':
   # First four use familiar components in a previously unseen pairing.
   first=sorted({x.split()[0] for x in labels});last=sorted({x.split()[-1] for x in labels});comb=[a+' '+b for a in first for b in last if a+' '+b not in labels]
   novel=comb[i] if i<4 else ['Elena Brooks','Quentin Vale','Felix Marsh','Ruth Bell'][i-4]
   item=re.search(r'owner of the (.+) as ',r['messages'][0]['content']).group(1)
  else:novel=['00:17','02:09','04:31','06:43','08:52','10:27','12:34','14:56'][i];item='meeting'
  # Select an unconsumed time deterministically if a candidate appeared in training.
  if novel in labels:
   assert family=='time';novel=next(f'{h:02d}:{m:02d}' for h in range(24) for m in range(60) if f'{h:02d}:{m:02d}' not in labels)
  for fact,value in [('seen',original),('unseen',novel)]:
   for wording in ['original','new']:
    user=r['messages'][0]['content'].replace(original,value)
    if wording=='new':user=(f'Please return the owner’s entire name and nothing else. The {item} has {value} listed as its owner.' if family=='name' else f'Please return only HH:MM. According to this appointment note, the meeting begins at {value}.')
    for numbered in [False,True]:
     rows.append(dict(id=f'probe-{family}-{i}-{fact}-{wording}-{int(numbered)}',family=family,pair=i,fact=fact,wording=wording,numeric_id=numbered,novelty='known_components' if family=='name' and i<4 else 'new_components' if family=='name' else 'new_digit_combination',messages=[dict(role='user',content=('Reference 7319. ' if numbered else '')+user),dict(role='assistant',content=value)],kind=family))
# History study uses exact existing grounding state questions; both runs identical except history policy.
for i,r in enumerate([r for r in old if r['family']=='state'][:8]):rows.append(dict(id=f'probe-state-{i}',family='state',pair=i,messages=r['messages'],kind='state'))
save(PRIVATE/'inference-probes.json',rows)
save(ROOT/'probe-contract.json',dict(single_turn_cases=128,three_turn_state_cases=8,history_modes=['generated','gold'],seen_definition='Seen in the Cycle10 adapter grounding curriculum only. Original foundation and historical A/B did not consume this same curriculum; cross-checkpoint results are descriptive.',fact_wording_pairs=True,numeric_id='Reference7319 added/removed without changing answers',decoding='Full vocabulary greedy, EOS enabled;16 tokens for names/times,24 for state.',teacher_forcing='Reference-prefix token rank/log probability diagnostic only; never substitutes an answer.',selection='First8 existing records per family; fixed convenience sample, not representative population estimate.',final_test=False))
print('Prepared136 diagnostic conversations; no final payloads used.')
