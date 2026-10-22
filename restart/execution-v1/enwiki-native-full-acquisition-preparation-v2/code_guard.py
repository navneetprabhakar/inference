import pathlib,hashlib,json,re
HERE=pathlib.Path(__file__).resolve().parent
def verify(expected):
 p=HERE/'code-pins.json';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
 if not isinstance(expected,str) or not re.fullmatch('[a-f0-9]{64}',expected) or p.is_symlink() or sha(p)!=expected:raise ValueError('external_code_registry_digest')
 import archive
 r=json.loads(p.read_text())
 if set(r.get('sha256',{}))!=archive.inventory():raise ValueError('exact_inventory')
 if r['runtime']!=archive.runtime():raise ValueError('runtime_pin')
 for f,h in r['sha256'].items():
  q=pathlib.Path(f)
  if q.is_symlink() or not q.is_file() or sha(q)!=h:raise ValueError('dependency_pin:'+f)
 return r
