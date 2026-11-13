"""Independent bounded oracles for inspected interval, geometry, and TTL examples."""
import ast,hashlib,io,itertools,json,random,re,unittest
from pathlib import Path
root=Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-09');rows={r['id']:r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines())}
def blocks(key,index):return re.findall(r'```python\n(.*?)```',rows[key]['messages'][index]['content'],re.S)
def execute(code,ns):
 tree=ast.parse(code)
 for node in ast.walk(tree):
  if isinstance(node,(ast.Import,ast.ImportFrom)):
   names=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module];assert set(names)<={'unittest','math','numbers'}
  if isinstance(node,ast.Name):assert node.id not in {'open','eval','exec','__import__','input','compile'}
 exec(compile(tree,'inspected-corpus','exec'),ns)
def supplied(ns,name):
 r=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(ns[name]));assert r.wasSuccessful();return r.testsRun
cue={'__name__':'reviewed_fixture'}
for i in [6,8]:
 for code in blocks('b50-cue-timeline',i):execute(code,cue)
cue_tests=supplied(cue,'TestDucking');rng=random.Random(713);cue_count=0
for _ in range(2500):
 cues=[(str(i),*sorted(rng.choices(range(10),k=2))) for i in range(rng.randrange(5))];voices=[tuple(sorted(rng.choices(range(10),k=2))) for _ in range(rng.randrange(7))];expected=[]
 for name,a,b in cues:
  cells=[x for x in range(a,b) if any(c<=x<d for c,d in voices)]
  for _,group in itertools.groupby(enumerate(cells),lambda pair:pair[1]-pair[0]):
   run=[x for _,x in group];expected.append((name,run[0],run[-1]+1,-12))
 assert cue['ducked'](cues,voices)==expected;cue_count+=1
svg={'__name__':'reviewed_fixture'};execute(blocks('b50-svg-coordinate',6)[0],svg);svg_tests=supplied(svg,'TestRectToGlobal');svg_count=0
for _ in range(2500):
 x,y=[rng.randrange(-4,5) for _ in range(2)];w,h=[rng.randrange(5) for _ in range(2)];s=rng.randrange(1,4);ox,oy=[rng.randrange(-4,5) for _ in range(2)];cx,cy=[rng.randrange(-5,6) for _ in range(2)];cw,ch=[rng.randrange(8) for _ in range(2)]
 cells={(a,b) for a in range(x*s+ox,(x+w)*s+ox) for b in range(y*s+oy,(y+h)*s+oy)}&{(a,b) for a in range(cx,cx+cw) for b in range(cy,cy+ch)}
 expected=None
 if cells:
  xs,ys=zip(*cells);expected=(min(xs),min(ys),max(xs)-min(xs)+1,max(ys)-min(ys)+1)
 assert svg['rect_to_global']((x,y,w,h),s,(ox,oy),(cx,cy,cw,ch))==expected;svg_count+=1
cache={'__name__':'reviewed_fixture'}
for i in [5,7]:
 for code in blocks('b50-cache-clock',i):execute(code,cache)
cache_tests=supplied(cache,'TestCacheProperties');ops=[('advance',1),('advance',2),('set','a','red',2),('set','a','new',1),('set','b','blue',3),('get','a'),('get','b')];cache_checks=0
for seq in itertools.product(ops,repeat=5):
 clock=cache['FakeClock']();actual=cache['Cache'](clock);model={};now=0
 for op in seq:
  if op[0]=='advance':now+=op[1];clock.advance(op[1])
  elif op[0]=='set':_,key,value,ttl=op;model[key]=(value,now,ttl);actual.set(key,value,ttl)
  else:
   key=op[1];r=model.get(key);expected=None
   if r and now-r[1]<r[2]:expected=r[0]
   elif r:del model[key]
   assert actual.get(key)==expected
  assert set(actual.data)==set(model)
  for key,(value,start,ttl) in model.items():assert actual.data[key]==(value,start+ttl)
  cache_checks+=1
report={'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'cue':{'supplied_tests':cue_tests,'unit_cell_union_oracle_cases':cue_count},'svg':{'supplied_tests':svg_tests,'unit_cell_intersection_oracle_cases':svg_count},'cache':{'supplied_tests':cache_tests,'independent_age_model_sequences':len(ops)**5,'operation_checks':cache_checks},'result':'pass'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
