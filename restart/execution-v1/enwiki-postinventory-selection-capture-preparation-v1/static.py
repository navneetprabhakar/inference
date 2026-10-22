"""Pin/import-only CLI. No source-execution option, SQL open or native read."""
from pathlib import Path
import json,hashlib,argparse,sys
HERE=Path(__file__).resolve().parent;BASE=HERE.parent
OWN=['select_core.py','capture_pipeline.py','terminal_guard.py','source_view.py','metadata_pipeline.py','old_capture_core.py','maintext_core.py','title_decode.py','native_codec.py','checks.py','terminal_checks.py','static.py','profile-template.json','contract.json','README.md']
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def required():
 extra=[BASE/'enwiki-native-development20-capture-preparation-v1/capture_core.py',BASE/'enwiki-native-development20-maintext-preparation-v1/extract_core.py',BASE/'enwiki-index-XML-title-proposal-v1/title_decode.py',BASE/'enwiki-retained-prefix-frame-preparation-v3/codec.py',BASE/'enwiki-retained-prefix-frame-preparation-v3/profile.json',BASE/'enwiki-retained-prefix-frame-preparation-v3/code-pins.json',BASE/'enwiki-compact-SQLite-sink-preparation-v3/sink.py',BASE/'enwiki-semantic-SAX-metadata-preparation-v3/semantic.py',BASE/'enwiki-incremental-XML-span-preparation-v4/spans.py',BASE/'enwiki-retained-prefix-terminal-verifier-preparation-v2/runner.py',BASE/'enwiki-retained-prefix-terminal-verifier-preparation-v2/profile.json',BASE/'enwiki-retained-prefix-terminal-verifier-preparation-v2/code-pins.json',BASE/'enwiki-generic-AST-policy-preparation-v4/policy_core.py',BASE/'enwiki-integrated-companion-preparation-v7/integrated_core.py',BASE/'enwiki-page-local-reference-preparation-v2/reference_core.py',BASE/'enwiki-short-footnote-preparation-v4/short_core.py',BASE/'enwiki-literal-year-qualifier-preparation-v1/qualifier_core.py',BASE/'enwiki-structural-companion-policy-preparation-v1/rules.py']
 return {str(HERE/n) for n in OWN}|{str(p) for p in extra}
def verify(profile_digest,registry_digest):
 if sha(HERE/'profile-template.json')!=profile_digest or sha(HERE/'code-pins.json')!=registry_digest:raise ValueError('external_preparation_pins')
 p=json.loads((HERE/'profile-template.json').read_text());pins=json.loads((HERE/'code-pins.json').read_text())['SHA256']
 if set(pins)!=required() or p['status']!='UNBOUND_PREPARATION_ONLY_NO_RETAINED_SOURCE_OR_LIVE_SQL_ACCESS' or p['terminal_binding'] is not None or p['materialized_selection'] is not None:raise ValueError('exact_unbound_preparation_inventory')
 for n,h in pins.items():
  if Path(n).is_symlink() or sha(n)!=h:raise ValueError('pinned_preparation_changed')
 import select_core,capture_pipeline,terminal_guard,source_view,metadata_pipeline,old_capture_core,maintext_core,title_decode,native_codec
 if capture_pipeline.LIMITS!={k:p['capture_stage_limits'][k] for k in capture_pipeline.LIMITS}:raise ValueError('capture_limits_contract')
 return len(pins)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--profile-sha256',required=True);a.add_argument('--code-pins-sha256',required=True);q=a.parse_args();print(json.dumps({'status':'PASS_UNBOUND_IMPORT_PIN_ONLY_NO_SQL_NATIVE_READ_OR_EXECUTE','pins':verify(q.profile_sha256,q.code_pins_sha256)}))
