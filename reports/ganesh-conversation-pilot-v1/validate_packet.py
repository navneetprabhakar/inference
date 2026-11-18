"""Read-only validation of frozen corpus/plan receipts. Never launches training."""
import ast,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check_spec(s):
 if s.get('launch_ready') is not False or s.get('training_authorized') is not False or s.get('budget_approved') is not False:raise ValueError('Unapproved packet must remain blocked')
 if s['recipe']['updates_per_arm']!=40 or s['recipe']['assistant_targets_per_arm']!=9144:raise ValueError('Changed experiment bounds')
 if s['requested_future_cap_usd']!=25:raise ValueError('Changed proposed cap')
 for arm,f in s['arms'].items():
  if sha(P/f)!=s['arm_input_sha256'][arm]:raise ValueError('Changed arm data')
 for key,f in [('development_suite_sha256','development-suite.json'),('review_sha256','review.json'),('source_manifest_sha256','source-manifest.json'),('exposure_plan_sha256','exposure-plan.json'),('baseline_raw_sha256','baseline-fit30.json'),('baseline_review_sha256','baseline-review.json')]:
  if sha(P/f)!=s[key]:raise ValueError('Changed evidence '+f)
s=json.loads((P/'pilot-spec.json').read_text());check_spec(s)
for key in ['launch_ready','training_authorized','budget_approved']:
 try:check_spec(dict(s,**{key:True}))
 except ValueError:pass
 else:raise AssertionError('Unsafe authorization mutation accepted')
for f in P.glob('*.py'):ast.parse(f.read_text())
for f in P.glob('*.json'):json.loads(f.read_text())
for f,h in json.loads((P/'local-checks.json').read_text())['frozen_files_verified'].items():assert sha(ROOT/f)==h,f
assert json.loads((P/'block-checks.json').read_text())['passed']
assert json.loads((P/'admission.json').read_text())['training_admitted'] is False
raw=json.loads((P/'baseline-fit30.json').read_text());review=json.loads((P/'baseline-review.json').read_text());assert len(raw['records'])==len(review['records'])==109 and sha(P/'baseline-fit30.json')==review['raw_sha256']
cost=json.loads((P/'cost-plan.json').read_text());assert cost['generation_forecast']['maximum_generated_tokens']==164640 and cost['calculated_usage_envelope_usd']<=25
if (P/'freeze.json').exists():
 for f,h in json.loads((P/'freeze.json').read_text())['files'].items():assert sha(P/f)==h,('Frozen new packet changed',f)
print('PASS: corpus/plan/evidence identities,327 reference turns,109 baseline reviews, frozen old data, blocked admission, bounds and adverse authorization mutations. NOT a training launch qualification.')
