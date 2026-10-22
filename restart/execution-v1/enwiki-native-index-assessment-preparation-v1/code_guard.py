import pathlib,json,hashlib,sys,re
HERE=pathlib.Path(__file__).resolve().parent
def verify(expected):
 sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();p=HERE/'code-pins.json'
 if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected) or p.is_symlink() or sha(p)!=expected:raise ValueError('external_code_registry_digest')
 import run
 registry=json.loads(p.read_text())
 if set(registry.get('sha256',{}))!=run.inventory():raise ValueError('exact_code_input_inventory')
 if registry['runtime']!={'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve())}:raise ValueError('runtime_pin')
 for f,h in registry['sha256'].items():
  path=pathlib.Path(f)
  if path.is_symlink() or not path.is_file() or sha(path)!=h:raise ValueError('pin:'+f)
 return registry
