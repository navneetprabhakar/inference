"""Sequential finite campaign; no admission, training or cloud activity."""
import datetime,json,subprocess
from pathlib import Path
root=Path('runs/long-context-campaign-v3');root.mkdir(exist_ok=True)
state={'status':'generating','cohorts_planned':6,'cohorts_complete':0,'admitted':0,'trained':0,'review':'Primary-agent review required per complete dialogue'}
def save():
 state['updated_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(root/'progress.json').write_text(json.dumps(state,indent=2)+'\n')
save()
for n in range(1,7):
 state['active_cohort']=n;save()
 with (root/f'cohort-{n:02d}.log').open('w') as log:
  p=subprocess.run(['runs/l4-data-prep/.venv/bin/python','reports/l4-qualification-v1/long-context-campaign-v3/generate.py',str(n)],stdout=log,stderr=subprocess.STDOUT)
 if p.returncode:
  state.update(status='generation_failed_requires_inspection',failed_cohort=n);save();raise SystemExit(p.returncode)
 state['cohorts_complete']=n;save()
state['status']='generation_complete_pending_full_review';save()
