"""Check each reviewed reconciler version and both displayed test suites."""
import copy,hashlib,json,random,re,subprocess,sys
from pathlib import Path
r=Path('runs/long-context-campaign-v3/cohort-03');s=next(s for s in map(json.loads,(r/'candidates.jsonl').read_text().splitlines()) if s['id']=='v3-03-ledger')
checks=0;versions=[]
for index in [1,5,7,13]:
 code=re.findall(r'```python\n(.*?)```',s['messages'][index]['content'],re.S)[0];p=r/f'ledger-message-{index}.py';p.write_text(code);ns={'__name__':'reviewed'};exec(compile(code,str(p),'exec'),ns);fn=ns['reconcile']
 base={'a':2,'b':1};updates={'a':0,'b':None,'absent':None};assert fn(base,updates)=={'a':0};assert base=={'a':2,'b':1};checks+=1
 if index>=5:
  pairs=[('a',1),('a',1)];before=pairs.copy()
  try:fn(base,pairs)
  except ValueError:pass
  else:raise AssertionError('duplicate accepted')
  assert pairs==before and base=={'a':2,'b':1};checks+=1
 if index>=7:
  rng=random.Random(117)
  for _ in range(200):
   base={k:rng.randrange(6) for k in 'abc' if rng.choice([True,False])};update={k:rng.choice([None,0,2,5]) for k in 'abcd' if rng.choice([True,False])};pairs=list(update.items());rng.shuffle(pairs)
   expected={k:update.get(k,base.get(k)) for k in set(base)|set(update) if update.get(k,base.get(k)) is not None};saved=copy.deepcopy((base,pairs))
   assert fn(base,iter(pairs))==expected and (base,pairs)==saved;checks+=1
  for key,qty in [('',1),(1,2),([],2),('x',True),('x',False),('x',-1),('x',1.2),('x','2')]:
   base={'a':3};pairs=[('a',0),(key,qty)];before=copy.deepcopy((base,pairs))
   try:fn(base,pairs)
   except ValueError:pass
   else:raise AssertionError(('bad update',key,qty))
   assert (base,pairs)==before;checks+=1
  for base in [{'x':None},{'x':True},{'x':False},{'x':-1},{'x':1.0},{'':2},{1:2}]:
   before=copy.deepcopy(base)
   try:fn(base,[])
   except ValueError:pass
   else:raise AssertionError(('bad current',base))
   assert base==before;checks+=1
 versions.append({'message_index':index,'sha256':hashlib.sha256(code.encode()).hexdigest()})
# Run the supplied standalone tests against precisely their contemporaneous implementation.
(r/'reconciler.py').write_text((r/'ledger-message-7.py').read_text())
tests=re.findall(r'```python\n(.*?)```',s['messages'][11]['content'],re.S)[0];(r/'test_reconcile.py').write_text(tests)
subprocess.run([sys.executable,'-m','unittest','test_reconcile'],cwd=r,check=True)
subprocess.run([sys.executable,str(r/'ledger-message-13.py')],check=True)
report={'result':'pass','independent_checks':checks,'random_patch_checks':400,'displayed_tests':9,'implementations':versions,'limits':'Plain current dictionary and well-formed update pairs as declared; one-shot iterators consumed, input containers unchanged.'}
(r/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
