"""Independent slot and canonical-order oracles for booking/merge examples."""
import ast,copy,hashlib,io,itertools,json,re,unittest
from pathlib import Path
root=Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-14');rows={r['id']:r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines())}
def blocks(key,i):return re.findall(r'```python\n(.*?)```',rows[key]['messages'][i]['content'],re.S)
def execute(code,ns):
 tree=ast.parse(code)
 for node in ast.walk(tree):
  if isinstance(node,(ast.Import,ast.ImportFrom)):
   names=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module];assert set(names)<={'unittest','copy'}
  if isinstance(node,ast.Name):assert node.id not in {'open','eval','exec','__import__','input','compile'}
 exec(compile(tree,'inspected-corpus','exec'),ns)
peak={'__name__':'reviewed_fixture'}
for i in [8,10]:
 for code in blocks('b50-reservation-sweep',i):execute(code,peak)
tests=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(peak['PeakDemandTests']));assert tests.wasSuccessful()
intervals=list(itertools.combinations_with_replacement(range(-1,4),2));peak_checks=0
for seq in itertools.product(intervals,repeat=3):
 bookings=[(str(i),a,b) for i,(a,b) in enumerate(seq)];expected=max(sum(a<=t<b for a,b in seq) for t in range(-1,4));before=list(bookings);assert peak['peak_demand'](bookings)==expected and bookings==before;peak_checks+=1
original={'__name__':'reviewed_fixture'}
for i in [4,6]:
 for code in blocks('b50-merge-streams',i):execute(code,original)
revised={'__name__':'reviewed_fixture'}
for code in blocks('b50-merge-streams',8):execute(code,revised)
sequences=[s for n in range(4) for s in itertools.combinations_with_replacement(range(3),n)];plain_checks=dedup_checks=0
for lt,rt in itertools.product(sequences,repeat=2):
 for mode in range(3):
  arrays=[]
  for source,times in enumerate([lt,rt]):
   arrays.append([dict(time=t,id=(str(source)+':'+str(i) if mode==0 else str(i%2)),payload=('p' if mode<2 else str(source))) for i,t in enumerate(times)])
  left,right=arrays;before=copy.deepcopy(arrays)
  ordered=[e for _,_,_,e in sorted((e['time'],source,i,e) for source,arr in enumerate(arrays) for i,e in enumerate(arr))]
  assert original['merge'](left,right)==ordered;plain_checks+=1
  grouped={}
  for e in ordered:grouped.setdefault(e['id'],[]).append(e)
  valid=all(len({(e['time'],e['payload']) for e in group})==1 for group in grouped.values());expected=[g[0] for g in grouped.values()]
  try:actual=revised['merge'](left,right)
  except ValueError:assert not valid
  else:assert valid and actual==expected and all(a is b for a,b in zip(actual,expected))
  assert arrays==before;dedup_checks+=1
report={'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'peak_supplied_tests':tests.testsRun,'peak_integer_slot_oracle_cases':peak_checks,'merge_supplied_assertions':'All original and revised code blocks executed unchanged','original_merge_canonical_order_cases':plain_checks,'deduplicating_merge_canonical_cases':dedup_checks,'result':'pass'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print('Peak',peak_checks,'and merge',dedup_checks,'oracle cases pass.')
