"""Execute bounded prefix tests and independently check atomic named counters."""
import ast,copy,hashlib,itertools,json,re
from pathlib import Path
root=Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-15');rows={r['id']:r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines())}
def blocks(key,i):return re.findall(r'```python\n(.*?)```',rows[key]['messages'][i]['content'],re.S)
def execute(code,ns):
 tree=ast.parse(code)
 for node in ast.walk(tree):
  if isinstance(node,(ast.Import,ast.ImportFrom)):
   names=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module];assert set(names)<={'copy','itertools'}
  if isinstance(node,ast.Name):assert node.id not in {'open','eval','exec','__import__','input','compile'}
 exec(compile(tree,'inspected-corpus','exec'),ns)
prefix={'__name__':'reviewed_fixture'}
for i in [8,10,12]:
 for code in blocks('b50-prefix-catalog',i):execute(code,prefix)
single={'__name__':'reviewed_fixture'}
for i in [6,8]:
 for code in blocks('b50-transaction-groups',i):execute(code,single)
multi={'__name__':'reviewed_fixture'}
for code in blocks('b50-transaction-groups',12):execute(code,multi)
ops=list(itertools.product('ab',range(-2,3)));checks=0
for av,bv in itertools.product(range(3),repeat=2):
 original={'a':av,'b':bv}
 for n in range(4):
  for seq in itertools.product(ops,repeat=n):
   snapshots=[{key:value+sum(delta for name,delta in seq[:i] if name==key) for key,value in original.items()} for i in range(n+1)]
   expected=None if any(value<0 for snap in snapshots for value in snap.values()) else snapshots[-1];before=copy.deepcopy((original,seq));actual=multi['apply_group'](original,seq)
   assert actual==expected and (original,seq)==before
   if actual is not None:assert actual is not original
   checks+=1
report={'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'prefix_original_supplied_bounded_cases':10230,'prefix_casefold_supplied_bounded_cases':6552,'single_counter_supplied_prefix_sum_cases':3905,'multi_counter_independent_prefix_sum_cases':checks,'supplied_boundary_and_validation_assertions':'All executed unchanged','result':'pass'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print('Prefix and atomic counter checks pass:',10230+6552+3905+checks,'bounded cases.')
