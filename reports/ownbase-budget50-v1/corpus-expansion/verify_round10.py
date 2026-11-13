"""Execute reviewed examples and independent finite grammar/mapping oracles."""
import ast,hashlib,io,itertools,json,re,unittest
from pathlib import Path
root=Path('runs/ownbase-budget50-v1/corpus-expansion/cohort-10');rows={r['id']:r for r in map(json.loads,(root/'candidates.jsonl').read_text().splitlines())}
def block(key,i):return re.findall(r'```python\n(.*?)```',rows[key]['messages'][i]['content'],re.S)[0]
def execute(code,ns):
 tree=ast.parse(code);tree.body=[n for n in tree.body if not (isinstance(n,ast.ImportFrom) and n.module in {'wrapper','decoder'})]
 for n in ast.walk(tree):
  if isinstance(n,(ast.Import,ast.ImportFrom)):
   names=[x.name for x in n.names] if isinstance(n,ast.Import) else [n.module];assert set(names)<={'unittest','itertools','re'}
  if isinstance(n,ast.Name):assert n.id not in {'open','eval','exec','__import__','input','compile'}
 exec(compile(tree,'inspected-corpus','exec'),ns)
def tests(ns,name):
 r=unittest.TextTestRunner(stream=io.StringIO()).run(unittest.defaultTestLoader.loadTestsFromTestCase(ns[name]));assert r.wasSuccessful();return r.testsRun
wrap={'__name__':'reviewed_fixture'}
for i in [5,7,9]:execute(block('b50-subtitle-wrap',i),wrap)
wrap_tests=tests(wrap,'WrapTests')+tests(wrap,'GeneratedWrapTests')
original={};execute(block('b50-subtitle-wrap',0),original);assert original['wrap'](['elephant  a','bb c'],4)=='\nelephant\na\nbb c'
rle={'__name__':'reviewed_fixture'}
for i in [7,11]:execute(block('b50-rle-chunks',i),rle)
rle_tests=tests(rle,'DecoderComparisonTests');checks=0
for n in range(6):
 for chars in itertools.product('01:A;',repeat=n):
  stream=''.join(chars)
  for limit in [0,1,3]:
   parts=[];valid=True
   if stream:
    for part in stream.split(';'):
     m=re.fullmatch(r'([0-9]+):([A-Za-z])',part)
     if m is None or int(m[1])<=0:valid=False;break
     parts.append(m[2]*int(m[1]))
   expected=''.join(parts);valid=valid and len(expected)<=limit
   for cut in range(len(stream)+1):
    d=rle['Decoder'](limit)
    try:actual=d.feed(stream[:cut])+d.feed('')+d.feed(stream[cut:])+d.finish()
    except ValueError:
     assert not valid,(stream,limit,cut)
     assert d.state=='error'
    else:
     assert valid and actual==expected,(stream,limit,cut,actual)
     try:d.finish()
     except RuntimeError:pass
     else:raise AssertionError('finish must be terminal')
    checks+=1
# Streaming accumulation rejects excessive counts before expansion, tolerates zeros.
d=rle['Decoder'](2);assert d.feed('0'*10000+'2:A')=='' and d.finish()=='AA'
d=rle['Decoder'](2)
try:d.feed('9'*10000)
except ValueError:assert d.state=='error' and d.total==0
else:raise AssertionError('limit not enforced')
kit={};execute(block('b50-kit-revision',6),kit);mapping_checks=0
for values in itertools.product(range(3),repeat=6):
 before={k:v for k,v in zip('abc',values[:3]) if v};after={k:v for k,v in zip('abc',values[3:]) if v};expected={k:{} for k in ['unchanged','changed','added','removed']};expected['replacements']=[]
 for k in 'abc':
  a,b=before.get(k),after.get(k)
  if a is None and b is not None:expected['added'][k]=b
  elif b is None and a is not None:expected['removed'][k]=a
  elif a is not None:expected['unchanged' if a==b else 'changed'][k]=a if a==b else (a,b)
 assert kit['compare_items'](before,after)==expected;mapping_checks+=1
assert kit['compare_items']({'cord':2},{'ribbon':2},[('cord','ribbon')])['replacements']==[('cord','ribbon')]
for pairs in [[('cord','missing')],[('cord','ribbon'),('cord','ribbon')]]:
 try:kit['compare_items']({'cord':2},{'ribbon':2},pairs)
 except ValueError:pass
 else:raise AssertionError('bad replacement')
report={'source_sha256':hashlib.sha256((root/'candidates.jsonl').read_bytes()).hexdigest(),'wrapper_supplied_tests':wrap_tests,'wrapper_generated_comparisons':(1+40+1600)*4,'original_wrapper_trace_verified':True,'rle_supplied_tests':rle_tests,'rle_grammar_partition_checks':checks,'rle_large_count_guards':True,'kit_mapping_oracle_cases':mapping_checks,'result':'pass','test_loading':'Only documented local module imports removed; original implementation supplied in same namespace.'}
(root/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
