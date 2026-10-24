"""Separate timestamp numeric content from separator syntax in conditional diagnostics."""
import json
from pathlib import Path
from sentencepiece import SentencePieceProcessor
R=Path(__file__).resolve().parent;P=R.parents[1];sp=SentencePieceProcessor(model_file=str(P/'restart/mac15m-feasibility-v1/upstream/tokenizer.model'));out={}
for model in ['short_answer','broader_candidate']:
 rows=json.loads((R/'private'/(model+'-forward.json')).read_text());rows=[r for r in rows if r['source']=='matched' and r['section']=='copy' and r['family']=='time' and r['mode']=='actual'];groups={g:[0,0] for g in ['digit','separator_or_boundary']}
 for r in rows:
  for gold,pred in zip(r['gold_ids'][:-1],r['argmax_ids'][:-1]):
   g='digit' if sp.id_to_piece(gold).replace('▁','').isdigit() else 'separator_or_boundary';groups[g][0]+=gold==pred;groups[g][1]+=1
 out[model]={g:dict(correct=n[0],tokens=n[1],accuracy=n[0]/n[1]) for g,n in groups.items()}
(R/'time-token-analysis.json').write_text(json.dumps(dict(models=out,interpretation='Conditional next-token accuracy given correct answer prefix. Numeric values separated from whitespace/colon syntax; neither is free-generation success.',training_updates=0),indent=2)+'\n')
