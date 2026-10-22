"""Externally bound registry and exact required inventory (OpenStax-v2 pattern)."""
import hashlib,json,os,pathlib,re
REQUIRED=frozenset({'aggregate.py','supervisor.py','render_shard.py','launch.py','reader_core.py','extraction_core.py','dom_renderer.py','shared_clock.py','profile.py','code_guard.py','check_profile.py','check_worker.py','check_controls.py','check_code_guard.py','baseline-v3-holds.json','effective-inputs.json'})
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(expected,here=None):
 here=pathlib.Path(__file__).resolve().parent if here is None else pathlib.Path(here);p=here/'code-pins.json'
 if not isinstance(expected,str) or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Explicit parent-reviewed code-pins SHA256 required')
 if p.is_symlink() or not p.is_file():raise ValueError('Code-pins must be ordinary file')
 if sha(p)!=expected:raise ValueError('Parent-reviewed code-pins digest mismatch')
 pins=json.loads(p.read_text());inventory=pins.get('sha256',{})
 if set(inventory)!=REQUIRED:raise ValueError('Exact required code and policy inventory')
 for name,h in inventory.items():
  f=here/name
  if f.is_symlink() or not f.is_file() or not isinstance(h,str) or not re.fullmatch('[0-9a-f]{64}',h) or sha(f)!=h:raise ValueError('Code or policy pin mismatch:'+name)
 return pins
def inherited():return verify(os.environ.get('WIKIBOOKS_CODE_PINS_SHA256'))
