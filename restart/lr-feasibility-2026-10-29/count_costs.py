import sys,json
from pathlib import Path
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P.parent/'phase-a-2026-10-28'));from build import serial,sp
old=P.parent/'phase-a-2026-10-28/private/prepared-v2';sent=set(json.loads((P.parent/'phase-a-completion-2026-10-29/sentinel.json').read_text())['ids']);matrix=json.loads((old/'matrix.json').read_text());counter=json.loads((old/'counterfactual.json').read_text());pres=json.loads((P.parent/'runner-readiness-2026-10-29/private/preservation.json').read_text())
def cost(rows):
 total=0;forwards=0;maxcontext=0;turns=0
 for row in rows:
  history=[];prior=0
  for t in range(len(row['messages'])//2):
   history.append(row['messages'][2*t]);n=len(serial(history)[0])-prior+t*32;assert n+32<=256
   total+=32*n+496;forwards+=32;maxcontext=max(maxcontext,n+31);turns+=1
   ans=row['messages'][2*t+1];history.append(ans);prior+=len(sp.encode(ans['content']))+1
 return dict(positions=total,forwards=forwards,max_forward_context=maxcontext,turns=turns)
costs={k:cost(rows) for k,rows in [('sentinel',[r for r in matrix if r['id'] in sent]),('matrix',matrix),('counterfactual',counter),('preservation',pres)]};counts=dict(sentinel=9,matrix=4,counterfactual=4,preservation=13)
result={'worst_case_per_packet':costs,'packet_counts':counts,'generation_positions_upper_bound':sum(costs[k]['positions']*v for k,v in counts.items()),'generation_forwards_upper_bound':sum(costs[k]['forwards']*v for k,v in counts.items()),'narrative_validation_positions':13*512*256,'training_main_positions':4089808+4096000,'training_main_assistant_targets':191636,'training_main_narrative_targets':4096000,'assumption':'No EOS early exit; reserve32 tokens in every prior reply. Source baseline sentinel only. Natural packet not included.'};(P/'feasibility-counts.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
