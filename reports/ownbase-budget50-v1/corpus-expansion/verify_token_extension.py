"""Verify proof examples against an independent finite transitive closure."""
import ast,contextlib,hashlib,io,json,re
from pathlib import Path
root=Path('runs/ownbase-budget50-v1/corpus-expansion/extensions-14');row=json.loads((root/'candidates.jsonl').read_text());original=next(r for r in map(json.loads,Path(row['source_file']).read_text().splitlines()) if r['id']==row['id']);assert row['messages'][:-2]==original['messages'] and row['policies'][:-1]==original['policies']
code=re.findall(r'```python\n(.*?)```',row['messages'][-1]['content'],re.S)[0];tree=ast.parse(code)
for node in ast.walk(tree):
 if isinstance(node,ast.ImportFrom):assert node.module=='collections'
 if isinstance(node,ast.Import):raise AssertionError('unexpected import')
 if isinstance(node,ast.Name):assert node.id not in {'open','eval','exec','__import__','input','compile'}
ns={'__name__':'reviewed_fixture'};exec(compile(tree,'reviewed-proof','exec'),ns)
with contextlib.redirect_stdout(io.StringIO()):ns['check']()
checks=0
for n in range(13):
 states=[(a,u) for a in range(n+1) for u in [False,True]];size=len(states);matrix=[[i==j for j in range(size)] for i in range(size)]
 for i,(a,u) in enumerate(states):
  for j,(b,v) in enumerate(states):
   if u==v and abs(a-b)==2:matrix[i][j]=True
   if not u and v and abs(a-b)==1:matrix[i][j]=True
 for k in range(size):
  for i in range(size):
   if matrix[i][k]:
    for j in range(size):matrix[i][j]=matrix[i][j] or matrix[k][j]
 for a in range(n+1):
  expected={state for j,state in enumerate(states) if matrix[states.index((a,False))][j]};assert ns['reachable'](n,a)==expected;checks+=1
report={'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'whole_prior_history_unchanged':True,'supplied_total_range':[0,20],'supplied_start_states':231,'independent_floyd_warshall_start_states':checks,'independent_total_range':[0,12],'result':'pass'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print('Token proof verified:',231,'supplied and',checks,'independent graph closures.')
