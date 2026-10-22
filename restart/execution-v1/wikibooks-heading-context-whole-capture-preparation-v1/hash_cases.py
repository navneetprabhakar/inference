"""Production helper hash path:64MiB sparse synthetic fixture, no corpus access."""
import pathlib,sys,hashlib,json,tempfile,time
from unittest.mock import patch
HERE=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import capture,pins
started=time.monotonic();checks=[]
with tempfile.TemporaryDirectory() as tmp:
 root=pathlib.Path(tmp);large=root/'large-fixture.sqlite';length=64*1024*1024+37
 with large.open('wb') as f:f.truncate(length)
 with large.open('rb') as f:expected=hashlib.file_digest(f,'sha256').hexdigest()
 registry=root/'code-pins.json';registry.write_text(json.dumps({'files':{str(large):expected}}));expected_registry=capture.sha(registry)
 original=pathlib.Path.open;reads=[]
 class Reader:
  def __init__(self,f):self.f=f
  def __enter__(self):return self
  def __exit__(self,*args):self.f.close()
  def read(self,n=-1):
   assert 0<n<=65536,'largefile_unbounded_or_oversize_read';reads.append(n);return self.f.read(n)
 def bounded(path,*a,**kw):
  f=original(path,*a,**kw)
  return Reader(f) if path==large and a and a[0]=='rb' else f
 def prohibited(*_a,**_kw):raise AssertionError('read_bytes_prohibited_in_any_verification_path')
 with patch.object(pins,'HERE',root),patch.object(capture,'expected_inventory',return_value={str(large)}),patch.object(pathlib.Path,'open',bounded),patch.object(pathlib.Path,'read_bytes',side_effect=prohibited):
  pins.verify(expected_registry);checks.append({'check':'actual_production_pins_verify_large64MiB_file_no_read_bytes','PASS':True})
  assert pins.stream_SHA256(large)==expected;checks.append({'check':'actual_production_helper_digest_exact','PASS':True})
  assert capture.sha(large)==expected;checks.append({'check':'actual_capture_sha_also_fixed65536byte_stream','PASS':True})
  assert len(reads)>3000 and max(reads)==65536;checks.append({'check':'all_largefile_read_requests_bounded_not_single_allocation','PASS':True})
  try:pins.verify('0'*64)
  except ValueError:pass
  else:raise AssertionError('wrong_external_registry_digest_accepted')
  checks.append({'check':'wrong_registry_digest_still_refused','PASS':True})
 with large.open('r+b') as f:f.seek(length-1);f.write(b'X')
 with patch.object(pins,'HERE',root),patch.object(capture,'expected_inventory',return_value={str(large)}),patch.object(pathlib.Path,'read_bytes',side_effect=prohibited):
  try:pins.verify(expected_registry)
  except ValueError:pass
  else:raise AssertionError('tampered_source_accepted')
  checks.append({'check':'actual_streaming_helper_source_tamper_still_refused','PASS':True})
report={'status':'PASS_PRODUCTION_HASH_HELPER_BOUNDED_SYNTHETIC_ONLY','checks':checks,'count':len(checks),'fixture_logical_bytes':length,'maximum_hash_read_bytes':max(reads),'captured_largefile_read_calls':len(reads),'temporary_scratch_removed':True,'read_bytes_globally_prohibited_during_productionverification':True,'elapsed_seconds':time.monotonic()-started,'retained_selected_body_queries':0}
print(json.dumps(report,indent=2))
