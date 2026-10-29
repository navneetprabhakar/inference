import json,collections,math,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;PRIVATE=ROOT/'private'
rows=[json.loads(x) for x in (PRIVATE/'inference-responses.jsonl').read_text().splitlines()];out={}
for model in sorted({r['model'] for r in rows}):
 a=[r for r in rows if r['model']==model];cells=[]
 for f in ['name','time']:
  for fact in ['seen','unseen']:
   for wording in ['original','new']:
    for numbered in [False,True]:
     rs=[r for r in a if r['family']==f and r['fact']==fact and r['wording']==wording and r['numeric_id']==numbered]
     cells.append(dict(family=f,fact=fact,wording=wording,numeric_id=numbered,correct=sum(r['correct'] for r in rs),n=len(rs),first_errors_predicting_eos=sum(bool(r['first_reference_error']) and r['first_reference_error']['predicted_eos'] for r in rs),mean_reference_nll=-sum(t['log_probability'] for r in rs for t in r['reference_tokens'])/sum(len(r['reference_tokens']) for r in rs)))
 effects={}
 for factor in ['numeric_id','wording','fact']:
  pair={};before=False if factor=='numeric_id' else 'original' if factor=='wording' else 'seen'
  for r in a:
   if r['family']=='state':continue
   keys=tuple(r[k] for k in ['family','pair','fact','wording','numeric_id'] if k!=factor);pair.setdefault(keys,{})[r[factor]]=r
  gains=losses=changes=0;byfamily={f:dict(gains=0,losses=0,changed_response=0,pairs=0) for f in ['name','time']}
  for k,pp in pair.items():
   x=pp[before];y=next(v for z,v in pp.items() if z!=before);g=int(y['correct'])-int(x['correct']);gains+=g>0;losses+=g<0;changed=x['response']!=y['response'];changes+=changed;bf=byfamily[x['family']];bf['pairs']+=1;bf['gains']+=g>0;bf['losses']+=g<0;bf['changed_response']+=changed
  effects[factor]=dict(gains=gains,losses=losses,changed_response=changes,pairs=len(pair),byfamily=byfamily)
 history={}
 for mode in ['gold','generated']:
  rr=[r for r in a if r['family']=='state' and r['mode']==mode];history[mode]=dict(correct_turns=sum(r['correct'] for r in rr),turns=len(rr),complete_conversations=sum(all(x['correct'] for x in rr if x['id']==rid) for rid in {x['id'] for x in rr}))
 out[model]=dict(cells=cells,paired_effects=effects,history=history)
ledger=json.loads((ROOT/'inference-ledger.json').read_text());assert ledger['updates']==0 and 'active' not in ledger;assert sum(e['positions'] for e in ledger['events'])==ledger['positions']
events=[json.loads(x) for x in (ROOT/'inference-ledger.events.jsonl').read_text().splitlines()];assert [r['index'] for r in events]==list(range(len(events)));assert [r['event'] for r in events]==ledger['events']
result=dict(models=out,work=dict(positions=ledger['positions'],seconds=ledger['seconds'],updates=0,turns=len(rows)),limits='8 convenience-sampled facts per cell; paired descriptive effects, no population estimate. Seen refers to historical grounding-adapter curriculum, not all checkpoints. Gold-prefix metrics are diagnostic only.')
(ROOT/'assessment.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
