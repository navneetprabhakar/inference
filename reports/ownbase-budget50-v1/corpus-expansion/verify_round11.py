"""Finite connected-component oracle and manifest collision regression."""
import ast,copy,hashlib,io,itertools,json,re,unittest
from pathlib import Path
root=Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-11');rows={r['id']:r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines())}
def blocks(row,i):return re.findall(r'```python\n(.*?)```',row['messages'][i]['content'],re.S)
def execute(code,ns):
 tree=ast.parse(code)
 for node in ast.walk(tree):
  if isinstance(node,(ast.Import,ast.ImportFrom)):
   names=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module];assert set(names)<={'unittest','copy'}
  if isinstance(node,ast.Name):assert node.id not in {'open','eval','exec','__import__','input','compile'}
 exec(compile(tree,'inspected-corpus','exec'),ns)
ns={'__name__':'reviewed_fixture'}
for i in [8,10]:
 for code in blocks(rows['b50-swatch-grid'],i):execute(code,ns)
r=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(ns['FillTests']));assert r.wasSuccessful()
coords=list(itertools.product(range(3),range(2)));checks=0
for values in itertools.product([None,'red','green'],repeat=len(coords)):
 grid={p:c for p,c in zip(coords,values) if c is not None};before=dict(grid)
 # Independent union-find components for all present cells.
 parent={p:p for p in grid}
 def find(p):
  while parent[p]!=p:p=parent[p]
  return p
 for a,b in itertools.combinations(grid,2):
  if grid[a]==grid[b] and sum(abs(x-y) for x,y in zip(a,b))==1:parent[find(a)]=find(b)
 for start,color in itertools.product(coords+[(9,9)],['red','green','blue']):
  expected={p:(color if start in grid and find(p)==find(start) else c) for p,c in grid.items()}
  actual=ns['fill'](grid,start,color);assert actual==expected and actual is not grid and grid==before;assert ns['fill_oracle'](grid,start,color)==expected;checks+=1
m={};execute(blocks(rows['b50-label-batch'],6)[0],m)
collision=[dict(job='A',revision=3,retry_id='a3',status='approved',label='Newest'),dict(job='A',revision=1,retry_id='a1',status='approved',label='Old'),dict(job='A',revision=1,retry_id='different',status='approved',label='Old')]
assert m['manifest'](collision)==[dict(job='A',label='Newest',copies=14)]
report={'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'swatch_supplied_tests':r.testsRun,'swatch_union_find_oracle_checks':checks,'original_manifest':'Confirmed missed historical same-revision distinct-delivery conflict; original rejected','counterexample':collision}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='counterexample'},indent=2))
