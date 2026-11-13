"""Independent regex grammar oracle and bounded routing-state enumeration."""
import ast,hashlib,io,itertools,json,re,unittest
from pathlib import Path
root=Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-06');rows={r['id']:r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines())}
def blocks(row,index):return re.findall(r'```python\n(.*?)```',row['messages'][index]['content'],re.S)
def execute(code,ns):
 tree=ast.parse(code)
 for node in ast.walk(tree):
  if isinstance(node,(ast.Import,ast.ImportFrom)):
   names=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module];assert set(names)<={'unittest'}
  if isinstance(node,ast.Name):assert node.id not in {'open','eval','exec','__import__','input','compile'}
 exec(compile(tree,'inspected-corpus','exec'),ns)
parser=rows['b50-box-label-parser'];counts={}
pattern=re.compile(r'"(?:[^"]|"")*"|[^",]*')
def oracle(line):
 pos=0;result=[]
 while True:
  m=pattern.match(line,pos);assert m is not None
  raw=m.group();value=raw[1:-1].replace('""','"') if raw.startswith('"') else raw
  result.append((value,pos));pos=m.end()
  if pos==len(line):return result
  if line[pos]!=',':raise ValueError('invalid grammar')
  pos+=1
for version,index,testindex in [('original',2,10),('offsets',14,14)]:
 ns={'__name__':'reviewed_fixture'}
 for code in blocks(parser,index):execute(code,ns)
 if index!=testindex:
  for code in blocks(parser,testindex):execute(code,ns)
 result=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(ns['TestParseLabel']));assert result.wasSuccessful()
 count=0
 for n in range(8):
  for chars in itertools.product('a," ',repeat=n):
   line=''.join(chars)
   try:expected=oracle(line)
   except ValueError:expected=None
   try:actual=ns['parse_label'](line)
   except ValueError:assert expected is None,line
   else:assert expected is not None and actual==(expected if version=='offsets' else [v for v,_ in expected]),(line,expected,actual)
   count+=1
 counts[version]={'exhaustive_strings':count,'supplied_tests':result.testsRun}
router=rows['b50-instruction-routing'];route_counts={};route_functions={}
for version,index in [('original',11),('fallback',15)]:
 ns={'__name__':'reviewed_fixture'};execute(blocks(router,index)[0],ns);count=0
 for start,dest,budget in itertools.product('ABC',['alpha','beta','gamma','omega','delta'],range(8)):
  node=start;trace=[node];remaining=budget;status=None
  for _ in range(budget+1):
   if dest=={'A':'alpha','B':'beta','C':'gamma'}[node]:status='delivered';break
   edges={('A','beta'):'B',('B','gamma'):'C',('B','omega'):'A',('C','omega'):'B'}
   nxt=edges.get((node,dest),'A' if version=='fallback' else None)
   if nxt is None:status='parked';break
   if remaining==0:status='budget-exhausted';break
   remaining-=1;node=nxt;trace.append(node)
  assert status and ns['route'](start,dest,budget)==(status,node,remaining,trace);count+=1
 route_counts[version]=count;route_functions[version]=ns['route']
 # Preserve exact proposed files for running the supplied pytest suite separately.
 testdir=root/'code-tests';testdir.mkdir(exist_ok=True);(testdir/('original_router.py' if version=='original' else 'revised_router.py')).write_text(blocks(router,index)[0])
(testdir/'test_router.py').write_text(blocks(router,17)[0])
# Execute the supplied assertion functions without requiring pytest installation.
testtree=ast.parse(blocks(router,17)[0]);testtree.body=[node for node in testtree.body if not isinstance(node,(ast.Import,ast.ImportFrom))]
for node in testtree.body:
 assert isinstance(node,ast.FunctionDef);node.decorator_list=[]
testns={'original_route':route_functions['original'],'revised_route':route_functions['fallback']};exec(compile(testtree,'reviewed-router-tests','exec'),testns);assertions=0
for name,fn in testns.items():
 if not name.startswith('test_'):continue
 if fn.__code__.co_argcount:
  for route in route_functions.values():fn(route);assertions+=1
 else:fn();assertions+=1
report={'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'parser':counts,'routing_state_checks':route_counts,'supplied_router_assertion_cases':assertions,'pytest_runner':'Not installed locally; exact assertion functions executed with original/revised functions, decorators handled explicitly.','result':'pass','semantic_admission_separate':True}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
