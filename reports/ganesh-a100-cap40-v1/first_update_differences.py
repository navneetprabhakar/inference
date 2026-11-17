import json
from pathlib import Path
R=Path('/opt/english/results')
def last(n):return json.loads(sorted((R/n/'update-trace').glob('*.json'))[11].read_text())
a,b=last('uninterrupted'),last('split_first');out={}
for kind in ('model','optimizer'):
 x,y=a['values'][kind]['tensor_layouts'],b['values'][kind]['tensor_layouts'];out[kind]=[n for n in sorted(set(x)|set(y)) if x.get(n)!=y.get(n)]
(R/'first-update-different-tensors.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
