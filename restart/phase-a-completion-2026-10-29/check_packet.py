import json,sys,collections,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent; OLD=P.parent/'phase-a-2026-10-28';sys.path.insert(0,str(OLD))
from build import serial,sp
rows=json.loads((P/'natural-development.json').read_text()); assert len(rows)==24
assert collections.Counter(r['family'] for r in rows)==dict.fromkeys(['grounding','comprehension','clarification','correction','instructions','explanation'],4)
assert len({r['frame'] for r in rows})==24
assert collections.Counter(len(r['turns']) for r in rows)=={2:2,3:4,4:18}
reports={}
for cap in [32,48]:
 turns=[]
 for r in rows:
  history=[]; prior_reply_tokens=0
  for i,t in enumerate(r['turns']):
   history.append({'role':'user','content':t['user']});ids,_=serial(history)
   worst=len(ids)-prior_reply_tokens+i*cap+cap
   gold=len(ids)+cap
   n=len(sp.encode(t['reference']))+1
   assert n<=cap,(r['id'],i,n)
   turns.append({'id':r['id'],'turn':i+1,'gold_history_with_allowance':gold,'worst_generated_history_with_allowance':worst,'reference_tokens_including_eos':n})
   history.append({'role':'assistant','content':t['reference']});prior_reply_tokens+=n
  ids,mask=serial(history);assert len(ids)==len(mask);assert sum(mask)==prior_reply_tokens
 reports[str(cap)]={'maximum':max(t['worst_generated_history_with_allowance'] for t in turns),'overflows_at_256':[t for t in turns if t['worst_generated_history_with_allowance']>256],'gold_overflows_at_256':[t for t in turns if t['gold_history_with_allowance']>256],'max_reference_tokens':max(t['reference_tokens_including_eos'] for t in turns),'turns':turns}
# Exact user-sequence overlap with proposed training and old natural candidates.
def us(r):
 if 'messages' in r:return tuple(m['content'] for m in r['messages'] if m['role']=='user')
 return tuple(t['user'] for t in r['turns'])
new={us(r) for r in rows};overlap={}
for name in ['canonical','diverse','prospective-final-candidates']:
 old=json.loads((OLD/'private/prepared-v2'/f'{name}.json').read_text()); overlap[name]=len(new & {us(r) for r in old})
assert not any(overlap.values())
# CPU-only exact accounting for planned paired training schedule (not wall-time forecast).
schedule=json.loads((OLD/'private/prepared-v2/training-schedule.json').read_text());exposures={}
for name in ['canonical','diverse']:
 data=json.loads((OLD/'private/prepared-v2'/f'{name}.json').read_text());targets=sum(sum(data[i]['mask'][1:]) for batch in schedule for i in batch);unpadded=sum(len(data[i]['ids'])-1 for batch in schedule for i in batch);padded=sum(max(len(data[i]['ids'])-1 for i in batch)*len(batch) for batch in schedule)
 exposures[name]={'assistant_targets':targets,'unpadded_input_positions':unpadded,'batch_padded_input_positions':padded,'updates':len(schedule),'conversations':sum(map(len,schedule))}
assert exposures['canonical']['assistant_targets']==exposures['diverse']['assistant_targets']
result={'status':'PASS','scope':'schema, serialization, exact sequence overlap, conservative context and analytical exposure checks; not semantic quality','scenarios':24,'turns':sum(len(r['turns']) for r in rows),'distinct_authored_frames':24,'exact_user_sequence_overlap':overlap,'context':reports,'planned_training_exposure_per_arm':exposures}
(P/'checks.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='context'},indent=2));print({k:{a:b for a,b in v.items() if a!='turns'} for k,v in reports.items()})
