"""Freeze historical development retention histories, without changing training."""
import copy,hashlib,json
from pathlib import Path
sources=[('instruction-v2','instruction-repair-v2/heldout-suite.json','regression-v2'),('instruction-v3','instruction-repair-v3/heldout-suite.json','regression-v3'),('literal','literal-state-repair-v1/heldout-suite.json','after'),('context','conversation-repair-v1/heldout-suite.json','conversation-regression'),('general','conversation-repair-v1/general-challenge.json','general-challenge')]
root=Path('reports/l4-qualification-v1');sessions=[];lineage=[]
for label,name,result in sources:
 path=root/name;digest=hashlib.sha256(path.read_bytes()).hexdigest();historical=json.loads((root/'literal-state-repair-v1'/(result+'.json')).read_text());assert digest==historical['suite_sha256']
 suite=json.loads(path.read_text());assert suite['purpose']=='development_only_never_train'
 for item in suite['sessions']:
  row=copy.deepcopy(item);row['id']=label+'-'+row['id'];sessions.append(row)
 lineage.append({'label':label,'source':str(path),'sha256':digest,'historical_cuda_exact_passed':historical['automated_passed'],'historical_cuda_exact_total':historical['automated_total']})
assert len({s['id'] for s in sessions})==len(sessions)
report={'purpose':'development_only_never_train','sessions':sessions,'source_hashes':lineage,'scope':'Historical exposed retention, whole session histories preserved. Establish matched MPS baseline; do not claim independent benchmark results. Training packet unchanged.'}
out=Path('reports/ownbase-budget50-v1/historical-retention.json');assert not out.exists();out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'sessions':len(sessions),'turns':sum(len(s['turns']) for s in sessions),'exact_turns':sum('exact_answers' in t for s in sessions for t in s['turns'])}))
