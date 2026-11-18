import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
pairs=[
('snack','figs','pretzels',lambda x:[f'For our trip, my chosen snack is {x}. Please acknowledge that choice briefly.','We will travel by bus. Please acknowledge that detail briefly.','What snack did I choose earlier?']),
('contact','Anil','Reema',lambda x:[f'If the shop closes early, contact {x}. Please acknowledge this briefly.','The shop has a wooden sign. Please acknowledge that detail briefly.','Whom should you contact if the shop closes early?']),
('room','balcony','courtyard',lambda x:[f'We will meet in the {x}. Please acknowledge the place briefly.','Please bring a bottle of water. Acknowledge this briefly.','Where did we agree to meet?']),
('drink','cocoa','lemonade',lambda x:[f'I want {"lemonade" if x=="cocoa" else "cocoa"}. Please acknowledge briefly.',f'Correction: change my drink to {x}. Please acknowledge the correction briefly.','What drink do I want now?']),
('day','Monday','Sunday',lambda x:[f'My appointment is on {"Sunday" if x=="Monday" else "Monday"}. Please acknowledge briefly.',f'Move my appointment to {x}. Please acknowledge the new day briefly.','Which day is my appointment now?']),
('place','cinema','aquarium',lambda x:[f'We planned to visit the {"aquarium" if x=="cinema" else "cinema"}. Please acknowledge briefly.',f'Change our visit to the {x}. We will still go by bus. Please acknowledge briefly.','Where are we going now?'])]
rows=[]
for key,a,b,fn in pairs:
 for v,x in enumerate([a,b]):rows.append(dict(pair=key,variant=v,turns=fn(x),final_expected=x,turn_rubrics=['brief accurate acknowledgement','brief accurate acknowledgement of detail or correction','correct recall of active value']))
(P/'rollout-panel.json').write_text(json.dumps({'scope':'exposed generated-history diagnostic','reply_budget':64,'sessions':rows},indent=2)+'\n')
print(hashlib.sha256((P/'rollout-panel.json').read_bytes()).hexdigest())
