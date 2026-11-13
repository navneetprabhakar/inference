"""Independent pairwise ranking oracle and rejected path trace evidence."""
import ast,hashlib,io,itertools,json,re,unittest
from pathlib import Path
root=Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-13');rows={r['id']:r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines())}
def block(key,i):return re.findall(r'```python\n(.*?)```',rows[key]['messages'][i]['content'],re.S)[0]
def execute(code,ns):
 tree=ast.parse(code)
 for node in ast.walk(tree):
  if isinstance(node,(ast.Import,ast.ImportFrom)):
   names=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module];assert set(names)<={'numbers','unittest'}
  if isinstance(node,ast.Name):assert node.id not in {'open','eval','exec','__import__','input','compile'}
 exec(compile(tree,'inspected-ranking','exec'),ns)
ns={'__name__':'reviewed_fixture'}
for i in [6,8]:execute(block('b50-score-ranking',i),ns)
r=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(ns['TestRank']));assert r.wasSuccessful();checks=0
options=list(itertools.product([-2,0,2,None],[False,True],[False,True]))
for values in itertools.product(options,repeat=3):
 entries=[dict(id=i,score=s,final=f,withdrawn=w) for i,(s,f,w) in enumerate(values)];before=[e.copy() for e in entries];eligible=[e for e in entries if e['final'] and not e['withdrawn'] and e['score'] is not None];slots=[None]*len(eligible)
 for e in eligible:
  position=sum(x['score']>e['score'] or (x['score']==e['score'] and x['id']<e['id']) for x in eligible);assert slots[position] is None;slots[position]=e
 actual=ns['rank'](entries);assert actual==slots and entries==before;checks+=1
bad={};execute(block('b50-path-reducer',0),bad);assert bad['normalize']('../a')=='a'
report={'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'ranking_supplied_tests':r.testsRun,'pairwise_ordinal_oracle_cases':checks,'original_path_counterexample':'Original normalize(../a) returns a, contrary to first assistant target claiming dot. Rejected.','result':'selected_ranking_pass'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print('Ranking verified:',checks,'oracle cases;',r.testsRun,'supplied tests. Path error reproduced.')
