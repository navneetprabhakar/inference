"""Exhaustive finite-graph oracle for the reviewed universal-arrival explanation."""
import ast,hashlib,json,re
from pathlib import Path
root=Path('runs/ownbase-budget50-v1/corpus-expansion/extensions-07');row=next(r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines()) if r['id']=='b50-puzzle-proof');ns={'__name__':'reviewed_fixture'}
for m in row['messages']:
 if m['role']!='assistant':continue
 for code in re.findall(r'```python\n(.*?)```',m.get('content',''),re.S):
  tree=ast.parse(code)
  for node in ast.walk(tree):
   if isinstance(node,ast.ImportFrom):assert node.module=='collections'
   if isinstance(node,ast.Import):assert False
   if isinstance(node,ast.Name):assert node.id not in {'open','eval','exec','__import__','input','compile'}
  exec(compile(tree,'reviewed-proof','exec'),ns)
for name,fn in list(ns.items()):
 if name.startswith('test_'):fn()
checks=0
for edges in range(512):
 graph={n:tuple(m for m in range(3) if edges & (1<<(3*n+m))) for n in range(3)}
 for goal_bits in range(8):
  goals={n for n in graph if goal_bits & (1<<n)}
  def every_path(n,path):
   if n in goals:return True
   if n in path or not graph[n]:return False
   return all(every_path(m,path|{n}) for m in graph[n])
  expected={n for n in graph if every_path(n,set())};actual=ns['universal_eventual_arrival'](graph,lambda n:n in goals);assert expected==actual,(graph,goals,expected,actual);checks+=1
report={'id':row['id'],'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'three_node_graph_and_goal_configurations':checks,'all_supplied_assertion_functions_pass':True,'result':'pass'};(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
