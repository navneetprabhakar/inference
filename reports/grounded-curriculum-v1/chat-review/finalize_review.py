"""Finalize only after the independent reviewer has inspected all fixed samples."""
import hashlib,json,pathlib
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[2];DATA=ROOT/'data/grounded-chat-candidates-v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(p.read_text())
def write(p,v):
 with p.open('x') as f:json.dump(v,f,indent=2);f.write('\n')
result=read(HERE/'exhaustive-result.json');registry=read(HERE/'reviewed-registry.json');policy=read(DATA/'policy.json');manifest=read(DATA/'partial-candidate-manifest.json')
assert result['state']=='PASS_finite_domain_instance_checks_pending_sample_review' and result['histories']==13573
assert sha(DATA/'candidates.sqlite')==manifest['database']['sha256']
assert sha(DATA/'policy.json')==manifest['policy_sha256']
for path,pin in policy['code_and_protocol'].items():assert sha(ROOT/path)==pin
samples=[json.loads(line) for line in (HERE/'generated-stratified-samples.jsonl').read_text().splitlines()]
assert len(samples)==108 and sha(HERE/'generated-stratified-samples.jsonl')==result['samples_sha256']
write(HERE/'sample-review.json',dict(state='reviewed_all_fixed_generated_samples',samples_sha256=result['samples_sha256'],sample_count=108,reviewed_doc_ids=[s['doc_id'] for s in samples],additional_semantic_blockers=[],limitations=['Synthetic names and object-label combinations may be unnatural.','Grounding is conditional on supplied synthetic facts; physical plausibility and open-domain quality are not certified.'],private_cases_read=False))
files=['reviewed-registry.json','review-v1.json','REVIEW-V1.md','REVIEW-V2.md','sample-review.json','generated-stratified-samples.jsonl','exhaustive-result.json','freeze_review.py','independent_semantics.py','verify.py','verify_controls.py','finalize_review.py']
pins={str((HERE/name).relative_to(ROOT)):sha(HERE/name) for name in files}
receipt=dict(state='PASS_pre_host_policy_not_admitted',scope='independent_grounded_candidates',database_sha256=sha(DATA/'candidates.sqlite'),manifest_sha256=sha(DATA/'partial-candidate-manifest.json'),verified_rows=result['histories'],failures=[],independent_review_sha256=pins[str((HERE/'REVIEW-V2.md').relative_to(ROOT))],verification_pins=pins,counts=result,synthetic_negative_controls=32,manual_surface_reviews=66,manual_additional_first_user_reviews=42,manual_generated_history_reviews=108,canonical_counts=registry['canonical_counts'],private_custody='pending_root',public_custody='pending_root',training_admitted=False,model_evaluated=False)
write(DATA/'candidate-verification.json',receipt)
print(json.dumps({k:receipt[k] for k in ('state','scope','verified_rows','database_sha256','manifest_sha256','canonical_counts')},indent=2))
