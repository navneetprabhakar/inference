"""Aggregate explicit per-record reviews, refuse missing/duplicate labels."""
import collections,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
labels={}
for name in ['independent-labels.json','fit30-labels.json']:
 data=json.loads((P/name).read_text())
 for r in data['labels']:
  key=(r['file'],r['index']);assert key not in labels,key;labels[key]=r
summary={'scope':'Exposed local diagnostic, not release or corpus admission','panel':[],'rollouts':[],'paired_modes':[],'input_hashes':{}}
for name in ['panel.json','rollout-panel.json','PROTOCOL.md','independent-labels.json','fit30-labels.json']:
 summary['input_hashes'][name]=hashlib.sha256((P/name).read_bytes()).hexdigest()
for model in ['base10b','fit30','sft194']:
 for suffix,expected in [('',192),('-rollouts',72)]:
  file=model+suffix+'.jsonl';raw=[json.loads(x) for x in (P/file).read_text().splitlines()];assert len(raw)==expected,(file,len(raw))
  assert len([k for k in labels if k[0]==file])==expected,file
  records=[]
  for i,r in enumerate(raw):
   l=labels[(file,i)];assert isinstance(l['core_correct'],bool) and isinstance(l['clean_content'],bool);assert not l['clean_content'] or l['core_correct']
   x=dict(r,**{k:l[k] for k in ['core_correct','clean_content','reason']})
   x['valid']=r['native_valid_text'] if not suffix else r['result']['status']=='complete'
   x['usable_native']=x['clean_content'] and x['valid'] and x['mode']=='chat';records.append(x)
  (P/(model+suffix+'-reviewed.jsonl')).write_text(''.join(json.dumps(x)+'\n' for x in records))
  for mode in ['plain','chat']:
   subset=[r for r in records if r['mode']==mode]
   row=dict(checkpoint=model,mode=mode,records=len(subset),core_correct=sum(r['core_correct'] for r in subset),clean_content=sum(r['clean_content'] for r in subset),native_valid_text=sum(r['valid'] for r in subset) if mode=='chat' else None,usable_native=sum(r['usable_native'] for r in subset) if mode=='chat' else None)
   if not suffix:
    fam={}
    for f in sorted(set(r['family'] for r in subset)):
     fr=[r for r in subset if r['family']==f]
     pairs=collections.defaultdict(list)
     for r in fr:pairs[r['pair']].append(r)
     assert all(len(v)==2 for v in pairs.values())
     fam[f]=dict(records=len(fr),core_correct=sum(r['core_correct'] for r in fr),clean_content=sum(r['clean_content'] for r in fr),both_core_pairs=sum(all(r['core_correct'] for r in v) for v in pairs.values()),both_clean_pairs=sum(all(r['clean_content'] for r in v) for v in pairs.values()),native_usable=sum(r['usable_native'] for r in fr) if mode=='chat' else None)
    row['families']=fam;row['both_core_pairs']=sum(x['both_core_pairs'] for x in fam.values());row['both_clean_pairs']=sum(x['both_clean_pairs'] for x in fam.values());summary['panel'].append(row)
   else:
    sessions=collections.defaultdict(list)
    for r in subset:sessions[(r['pair'],r['variant'])].append(r)
    assert len(sessions)==12 and all(len(v)==3 for v in sessions.values())
    row.update(sessions=12,final_core_correct=sum(r['core_correct'] for r in subset if r['turn']==2),all_turn_core_sessions=sum(all(r['core_correct'] for r in v) for v in sessions.values()),all_turn_clean_sessions=sum(all(r['clean_content'] for r in v) for v in sessions.values()),usable_native_sessions=sum(all(r['usable_native'] for r in v) for v in sessions.values()) if mode=='chat' else None,blocked_turns=sum(r['result'].get('error_code')=='session_blocked' for r in subset));summary['rollouts'].append(row)
  if not suffix:
   index={(r['pair'],r['variant'],r['mode']):r for r in records};counts=collections.Counter()
   for pair,v in {(r['pair'],r['variant']) for r in records}:
    a=index[(pair,v,'plain')]['core_correct'];b=index[(pair,v,'chat')]['core_correct'];counts[f'plain_{a}_chat_{b}']+=1
   summary['paired_modes'].append(dict(checkpoint=model,counts=dict(counts)))
(P/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'panel':[{k:v for k,v in x.items() if k!='families'} for x in summary['panel']],'rollouts':summary['rollouts'],'paired_modes':summary['paired_modes']},indent=2))
