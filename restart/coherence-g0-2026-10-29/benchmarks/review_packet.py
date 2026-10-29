import json
from pathlib import Path
P=Path(__file__).resolve().parent
for name in ['development','native_continuations','grounded_choices','grammar_contrasts']:
 rows=json.loads((P/(name+'.json')).read_text())
 if name=='grounded_choices':rows=[{k:v for k,v in x.items() if k not in ['joint_encoding','controls']} for x in rows]
 if name=='grammar_contrasts':rows=[{k:v for k,v in x.items() if k!='joint_encoding'} for x in rows]
 (P/(name+'_review.json')).write_text(json.dumps(rows,indent=2)+'\n')
