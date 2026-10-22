import hashlib,json,pathlib
HERE=pathlib.Path(__file__).resolve().parent

def verify(expected):
 import capture as run
 raw=(HERE/'code-pins.json').read_bytes()
 if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('external_code_registry_digest')
 data=json.loads(raw)
 if set(data['files'])!=run.expected_inventory():raise ValueError('exact_required_inventory')
 for p,h in data['files'].items():
  q=pathlib.Path(p)
  if q.is_symlink() or hashlib.sha256(q.read_bytes()).hexdigest()!=h:raise ValueError('input_or_code_pin:'+p)
