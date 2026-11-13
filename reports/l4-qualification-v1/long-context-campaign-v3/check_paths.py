"""Compare the reviewed lexical normalizer to POSIX normpath with the specified slash rule."""
import hashlib,itertools,json,posixpath,re,subprocess,sys
from pathlib import Path
r=Path('runs/long-context-campaign-v3/cohort-04');s=next(s for s in map(json.loads,(r/'candidates.jsonl').read_text().splitlines()) if s['id']=='v3-04-paths')
code=re.findall(r'```python\n(.*?)```',s['messages'][11]['content'],re.S)[0];p=r/'reviewed_paths.py';p.write_text(code);subprocess.run([sys.executable,str(p)],check=True)
ns={'__name__':'reviewed'};exec(compile(code,str(p),'exec'),ns);fn=ns['normalize'];cases=set()
for n in range(5):
 for components in itertools.product(['','a','..','.','.hidden','...'],repeat=n):
  for prefix in ['','/','//']:cases.add(prefix+'/'.join(components))
for path in cases:
 expected=posixpath.normpath(path)
 if path.startswith('/'):expected='/'+expected.lstrip('/')
 actual=fn(path);assert actual==expected,(path,actual,expected);assert fn(actual)==actual
report={'result':'pass','displayed_cases':15,'independent_unique_paths':len(cases),'reference':'stdlib posixpath.normpath; collapse all leading slash runs per explicit user rule','implementation_sha256':hashlib.sha256(code.encode()).hexdigest(),'limits':'Pure lexical semantics; no filesystem access or containment guarantee.'}
(r/'code-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
