import hashlib,json,pathlib
HERE=pathlib.Path(__file__).resolve().parent
HASH_CHUNK_BYTES=65536
def stream_SHA256(path):
 h=hashlib.sha256()
 with pathlib.Path(path).open('rb') as f:
  while chunk:=f.read(HASH_CHUNK_BYTES):h.update(chunk)
 return h.hexdigest()
def verify(expected,metadata_only=False):
 import capture as run
 registry=HERE/'code-pins.json'
 if registry.is_symlink() or stream_SHA256(registry)!=expected:raise ValueError('external_code_registry_digest')
 with registry.open('r',encoding='utf8') as f:data=json.load(f)
 if set(data['files'])!=run.expected_inventory():raise ValueError('exact_required_inventory')
 sources=run.source_database_paths() if metadata_only else set()
 if metadata_only and set(data.get('source_database_paths',[]))!=sources:raise ValueError('exact_metadata_only_source_db_inventory')
 for p,h in data['files'].items():
  q=pathlib.Path(p)
  if q.is_symlink() or not q.is_file() or (p not in sources and stream_SHA256(q)!=h):raise ValueError('input_or_code_pin:'+p)
