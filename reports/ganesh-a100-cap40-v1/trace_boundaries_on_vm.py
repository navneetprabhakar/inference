import json
from pathlib import Path
R=Path('/opt/english/results')
def rows(branch):return [json.loads(p.read_text()) for p in sorted((R/branch/'update-trace').glob('*.json'))]
a=rows('uninterrupted');b=rows('split_first');c=rows('split_resume')
def compare(x,y):
 out=[]
 for i,(u,v) in enumerate(zip(x,y)):
  keys=set(u['values'])|set(v['values']);different=[k for k in sorted(keys) if u['values'].get(k)!=v['values'].get(k)]
  out.append({'index':i,'reference_event':u['event'],'resumed_event':v['event'],'reference_step':u['update_start_step'],'resumed_step':v['update_start_step'],'different_components':different})
 return out
first=compare(a[:len(b)],b)
# Ignore the resumed-only initial observation, then compare equal step1 event schedules.
second=compare([r for r in a if r['update_start_step']==1],[r for r in c if r['event']!='initial'])
report={'first_independent_update':first,'resumed_update':second}
(R/'trace-boundary-diagnosis.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
