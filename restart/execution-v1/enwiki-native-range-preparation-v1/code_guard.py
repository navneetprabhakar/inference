import pathlib,hashlib,json,re,sys
HERE=pathlib.Path(__file__).resolve().parent
def verify(expected):
 p=HERE/'code-pins.json';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected) or p.is_symlink() or sha(p)!=expected:raise ValueError('external_code_registry_digest')
 import ranges
 r=json.loads(p.read_text())
 if set(r.get('sha256',{}))!=ranges.inventory():raise ValueError('exact_inventory')
 if r['runtime']!={'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve())}:raise ValueError('runtime_pin')
 for f,h in r['sha256'].items():
  p=pathlib.Path(f)
  if p.is_symlink() or sha(p)!=h:raise ValueError('dependency_pin:'+f)
 return r
