"""Reviewed external digest + exact input/code dependency inventory; no writes."""
import hashlib,json,pathlib,re,sys
HERE=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(expected):
 if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected):raise ValueError('explicit_registry_digest')
 p=HERE/'code-pins.json'
 if p.is_symlink() or sha(p)!=expected:raise ValueError('external_registry_digest')
 import acquire
 d=json.loads(p.read_text());inventory=d.get('sha256',{})
 if set(inventory)!=acquire.bound_inventory():raise ValueError('exact_code_policy_dependency_inventory')
 if d['runtime']!={'python':sys.version,'executable':str(pathlib.Path(sys.executable).resolve())}:raise ValueError('runtime_pin')
 for path,h in inventory.items():
  f=pathlib.Path(path)
  if f.is_symlink() or not f.is_file() or sha(f)!=h:raise ValueError('pinned_dependency_changed:'+path)
 return d
