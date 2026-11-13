"""Check all delivery orders and collision cases in the two reviewed repairs."""
import ast,copy,hashlib,io,itertools,json,re,unittest
from pathlib import Path
base=Path('runs/ownbase-budget50-v1/corpus-expansion');original=next(r for r in map(json.loads,(base/'cohort-11/candidates.jsonl').read_text().splitlines()) if r['id']=='b50-label-batch')
def blocks(row,i):return re.findall(r'```python\n(.*?)```',row['messages'][i]['content'],re.S)
def execute(code,ns):
 tree=ast.parse(code)
 for node in ast.walk(tree):
  if isinstance(node,(ast.Import,ast.ImportFrom)):
   names=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module];assert set(names)<={'copy','unittest'}
  if isinstance(node,ast.Name):assert node.id not in {'open','eval','exec','__import__','input','compile'}
 exec(compile(tree,'inspected-repair','exec'),ns)
rows=[dict(job=j,revision=v,retry_id=j+str(v),status=s,label=l) for j,v,s,l in [('A',3,'approved','New'),('B',1,'approved','Same'),('A',1,'approved','Old'),('B',2,'cancelled','Same'),('C',1,'approved','Same')]];rows.append(rows[2].copy())
for name in ['repairs-11','repairs-12']:
 root=base/name;row=json.loads((root/'candidates.jsonl').read_text());assert row['messages'][:6]==original['messages'][:6] and row['messages'][7:]==original['messages'][7:] and row['policies']==original['policies'];ns={'__name__':'reviewed_fixture'}
 for i in [6,8]:
  for code in blocks(row,i):execute(code,ns)
 r=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(ns['ManifestTests']));assert r.wasSuccessful();checks=0
 for seq in itertools.permutations(rows):
  before=copy.deepcopy(seq);expected=[]
  for job in dict.fromkeys(r['job'] for r in seq):
   latest=max((r for r in seq if r['job']==job),key=lambda r:r['revision'])
   if latest['status']=='approved':expected.append(dict(job=job,label=latest['label'],copies=7))
  assert ns['manifest'](seq,7)==expected and seq==before;checks+=1
 collision=[rows[0],rows[2],dict(rows[2],retry_id='different')]
 for seq in itertools.permutations(collision):
  try:ns['manifest'](seq)
  except ValueError:pass
  else:raise AssertionError('missed older revision collision')
 for seq in [[rows[0],dict(rows[0],label='changed')],[rows[2],dict(rows[2],status='cancelled')]]:
  try:ns['manifest'](seq)
  except ValueError:pass
  else:raise AssertionError('missed retry collision')
 guard=False
 if name=='repairs-12':
  for value in [True,False,0,-1,1.5,'3']:
   try:ns['manifest']([],value)
   except ValueError:pass
   else:raise AssertionError('copies guard missing')
  guard=True
 report={'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'only_message6_changed':True,'supplied_tests':r.testsRun,'order_permutations':checks,'older_revision_collision_orders':6,'retry_conflicts':2,'positive_copies_guard_verified':guard,'result':'pass_for_stated_verification_scope'}
 (root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print('Both repairs checked:4supplied tests each,720orders each,8collision cases each; final copies guard verified.')
