import pathlib,json,hashlib,re,sys
HERE=pathlib.Path(__file__).resolve().parent
def verify(expected):
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();p=HERE/'code-pins.json'
 if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected) or p.is_symlink() or sha(p)!=expected:raise ValueError('external_registry_pin')
 import run
 r=json.loads(p.read_text())
 if set(r.get('sha256',{}))!=run.inventory():raise ValueError('exact_inventory')
 if r['runtime']!={'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve())}:raise ValueError('actual_runtime_mismatch')
 for f,h in r['sha256'].items():
  path=pathlib.Path(f)
  if path.is_symlink() or not path.is_file() or sha(path)!=h:raise ValueError('dependency_pin:'+f)
 return r
