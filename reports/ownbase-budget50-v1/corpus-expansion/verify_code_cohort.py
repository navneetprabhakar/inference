"""Execute fully inspected fictional snippets and independent small-domain checks."""
import ast, contextlib, hashlib, io, itertools, json, re, sys
from pathlib import Path
source=Path(sys.argv[1] if len(sys.argv)>1 else 'runs/ownbase-budget50-v1/corpus-expansion/cohort-03/candidates.jsonl')
results=[]
for row in map(json.loads,source.read_text().splitlines()):
 ns={'__name__':'__main__'};blocks=0;checks=0;failures=[]
 for i,msg in enumerate(row['messages']):
  if msg['role']!='assistant':continue
  for code in re.findall(r'```python\n(.*?)```',msg.get('content',''),re.S):
   tree=ast.parse(code)
   for node in ast.walk(tree):
    if isinstance(node,(ast.Import,ast.ImportFrom)):
     names=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module]
     assert set(names)<= {'heapq','itertools'},names
    if isinstance(node,ast.Name):assert node.id not in {'open','eval','exec','__import__','input','compile'}
   try:
    with contextlib.redirect_stdout(io.StringIO()):exec(compile(tree,str(source), 'exec'),ns)
    blocks+=1
   except Exception as ex:failures.append({'message':i,'error':repr(ex)})
  if row['id']=='b50-dependency-plan' and 'plan' in ns and i in (1,3,7):
   # Independent exhaustive topological-order oracle on all three-node graphs.
   for bits in range(512):
    names=['a','b','c'];graph={n:[d for j,d in enumerate(names) if bits & (1<<(3*k+j))] for k,n in enumerate(names)}
    needed={'c'}
    while True:
     expanded=needed|{d for n in needed for d in graph[n]}
     if expanded==needed:break
     needed=expanded
    scope=set(names) if i==1 else needed
    valid=[p for p in itertools.permutations(scope) if all(p.index(d)<p.index(n) for n in scope for d in graph[n])]
    try:got=ns['plan'](graph,'c')
    except ValueError as ex:
     assert not valid,(graph,ex)
     if hasattr(ex,'cycle'):
      path=ex.cycle;assert len(path)>=2 and path[0]==path[-1]
      assert all(b in graph[a] for a,b in zip(path,path[1:]));assert set(path)<=needed
    else:
     assert valid,graph
     orders=[p for p in itertools.permutations(needed) if all(p.index(d)<p.index(n) for n in needed for d in graph[n])]
     assert tuple(got)==min(orders),(graph,got)
    checks+=1
 if row['id']=='b50-sheet-plan':
  for n in range(101):
   labels=[str(k%3) for k in range(n)];old=labels[:];plan=ns['plan_copy'](labels)
   slots=[v for sheet in plan for side in ['front','back'] for v in sheet[side]];padded=labels+[None]*(-n%4)
   assert sorted(slots,key=lambda x:x[0])==list(enumerate(padded))
   assert labels==old;checks+=1
 if row['id']=='b50-test-matrix':
  axes={'z':['a','b','c'],'a':['x','y'],'q':['p','q'],'b':['1','2','3']}
  rules=[{'z':'c','a':'y'}];expected=[dict(zip(axes,v)) for v in itertools.product(*axes.values()) if not(v[0]=='c' and v[1]=='y')]
  assert len(expected)==30
  for start in range(35):
   for count in range(35):
    assert ns['expand'](axes,rules,start,count)==expected[start:start+count];checks+=1
 results.append({'id':row['id'],'executed_assistant_blocks':blocks,'independent_checks':checks,'errors':failures,'note':'Mechanical code evidence only; semantic admission requires complete root review.'})
report={'source':str(source),'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'results':results}
(source.parent/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
assert not any(r['errors'] for r in results)
