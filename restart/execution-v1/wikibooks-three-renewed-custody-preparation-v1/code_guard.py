import pathlib,json,re,hashlib
HERE=pathlib.Path(__file__).resolve().parent
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(65536),b''):h.update(b)
 return h.hexdigest()
def verify(expected):
 import audit
 p=HERE/'code-pins.json'
 if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected) or p.is_symlink() or sha(p)!=expected:raise ValueError('explicit_parent_reviewed_code_registry_digest')
 m=json.loads(p.read_text())
 if set(m.get('input_SHA256',{}))!=audit.inventory() or m['environment']!=audit.environment():raise ValueError('exact_inventory_runtime')
 for name,digest in m['input_SHA256'].items():
  path=pathlib.Path(name)
  if path.is_symlink() or not path.is_file() or audit.sha(path)!=digest:raise ValueError('frozen_input_changed:'+name)
 return m
