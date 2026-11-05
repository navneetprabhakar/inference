import json,subprocess,time,os
from pathlib import Path
R=Path(__file__).resolve().parents[2];run=Path(__file__).resolve().parent;python=R.parent/'inference-archive-20261029/.venv/bin/python';plan=json.loads((run/'edit-plan.json').read_text());auth=json.loads((run/'authorization.json').read_text())
for c in plan['candidates']:
 if time.time()>=auth['deadline_unix'] or (run/'STOP').exists():raise RuntimeError('Run closed')
 state={'state':'evaluating','candidate':c['id'],'driver_pid':os.getpid(),'updated_unix':time.time()};(run/'stage-status.json').write_text(json.dumps(state,indent=2)+'\n')
 cmd=[str(python),'scripts/evaluate_weight_edits.py','--checkpoint',str(run/'candidates'/c['id']),'--dataset',auth['development'],'--output',str(run/'evaluation'/c['id']),'--split','development']
 with (run/(c['id']+'-console.log')).open('a') as f:subprocess.run(cmd,cwd=R,stdout=f,stderr=subprocess.STDOUT,check=True)
 print(c['id']+' decoded',flush=True)
(run/'stage-status.json').write_text(json.dumps({'state':'first_wave_decoded_review_required','driver_pid':None,'updated_unix':time.time()},indent=2)+'\n')
