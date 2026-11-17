"""Read-only logical value versus storage-layout diagnosis of existing captures."""
import json,sys,torch
from pathlib import Path
from cloud_training.nano_optimizer_capture import load_capture
from cloud_training.nano_restart_compare import compare_and_record
R=Path('/opt/english/results');a=R/'uninterrupted/optimizer-capture/step-00000001';b=R/'split_resume/optimizer-capture/step-00000001'
ma,ba,aa=load_capture(a);mb,bb,ab=load_capture(b)
def diff(x,y):
 out=[]
 for i,(sx,sy) in enumerate(zip(x['specs'],y['specs'])):
  row={'argument':i,'layout_equal':sx==sy}
  if 'scalar' in sx:row['scalar_reference']=sx['scalar'];row['scalar_resumed']=sy.get('scalar');row['values_equal']=sx==sy
  else:
   vx=x['stores'][sx['group']].as_strided(sx['shape'],sx['stride'],sx['offset']);vy=y['stores'][sy['group']].as_strided(sy['shape'],sy['stride'],sy['offset'])
   row.update(shape=list(vx.shape),dtype=str(vx.dtype),values_equal=torch.equal(vx,vy),reference_layout=sx,resumed_layout=sy)
   if vx.shape==vy.shape and not row['values_equal']:
    delta=(vx.float()-vy.float()).abs();row.update(different_elements=int((vx!=vy).sum()),max_abs=float(delta.max()),nonfinite_reference=int((~torch.isfinite(vx)).sum()),nonfinite_resumed=int((~torch.isfinite(vy)).sum()))
  out.append(row)
 return out
report={'context_equal':ma==mb,'inputs':diff(ba,bb),'outputs':diff(aa,ab)}
(R/'capture-logical-difference.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
del ma,mb,ba,bb,aa,ab
import gc;gc.collect()
try:
 comparison=compare_and_record(R/'uninterrupted/step-00000002',R/'split_resume/step-00000002',R/'normal-comparison-supplemental.json');print(json.dumps(comparison),flush=True)
except Exception as e:print(repr(e),flush=True);raise
