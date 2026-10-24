"""Integrity audit of read-only diagnostics and transitive input receipts; no model work."""
import json,hashlib,math,ast
from pathlib import Path
R=Path(__file__).resolve().parent;P=R.parents[1];V=R/'private'
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4194304),b''):h.update(b)
 return h.hexdigest()
for path,digest in read(R/'freeze.json')['files'].items():assert sha(P/path)==digest,path
matched=read(P/'restart/matched-improvement-reassessment-v1/result.json');broad=read(P/'restart/broader-curriculum-v1/result.json')
for label in ['short_answer','broader_candidate']:
 assert sha(P/f'restart/matched-improvement-reassessment-v1/private/{label}-responses.json')==matched['models'][label]['raw_responses_sha256']
assert sha(P/'restart/broader-curriculum-v1/private/parent-retention-responses.json')==broad['baseline']['retention']['responses_sha256']
assert sha(P/'restart/broader-curriculum-v1/private/broad-retention-100-responses.json')==broad['history'][0]['retention']['responses_sha256']
for path in ['restart/factual-binding-v1/private/test-encoded.json','restart/foundation-resolution-v1/B/checkpoint.pt','restart/foundation-recovery-v2-corrected/common.py']:
 prior=read(P/('restart/factual-binding-v1/freeze.json' if 'test-encoded' in path or 'foundation-resolution' in path else 'restart/broader-curriculum-v1/freeze.json'))
 assert sha(P/path)==prior['files'][path]
result=read(R/'result.json');summary=read(R/'summary.json');fit=read(R/'training-fit.json');frozenfit=read(R/'training-fit-freeze.json')
assert sha(R/'training_fit.py')==frozenfit['script_sha256'] and sha(V/'training-fit-bank.json')==frozenfit['bank_sha256']
assert result['training_updates']==result['optimizer_updates']==fit['training_updates']==fit['optimizer_updates']==0
for filename in ['diagnostics.py','training_fit.py']:
 tree=ast.parse((R/filename).read_text());assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr in ['step_fn','apply_gradients','checkpoint'] for n in ast.walk(tree))
for label in ['short_answer','broader_candidate']:
 rows=read(V/(label+'-forward.json'));assert len(rows)==760
 for row in rows:
  n=len(row['gold_ids']);assert all(len(row[k])==n for k in ['argmax_ids','gold_ranks','gold_probabilities','eos_probabilities','the_probabilities'])
  assert all(0<=p<=1.00001 and math.isfinite(p) for p in row['gold_probabilities'])
 assert summary['models'][label]['old_training']['all_reference_targets_argmax_correct']==480
 raw=read(V/(label+'-seen-fit-responses.json'));assert len(raw)==32
 assert sha(V/(label+'-seen-fit-responses.json'))==fit['models'][label]['raw_responses_sha256']
 assert sum(r['exact_normalized'] for r in raw)==fit['models'][label]['exact_answers']
 assert fit['models'][label]['new_training_updates']==result['models'][label]['new_training_updates']==0
# 2 * 760 padded forward examples, plus 4*(2 old+6 new+8 replay) gradient batches per model, charged at three input equivalents.
assert result['analysis_positions']==2*760*256+2*4*(2+6+8)*256*3==487424
assert fit['aggregate_analysis_positions']==result['analysis_positions']+fit['additional_positions']==494773
assert fit['aggregate_elapsed_seconds']<900 and fit['aggregate_analysis_positions']<2000000
inv=read(R/'inventory.json');assert abs(inv['mean_old_objective_coefficient']+inv['mean_new_objective_coefficient']-.5)<1e-12
assert sum(x['targets'] for x in inv['by_consumed_family'].values())==4699
lineage=read(R/'lineage.json');assert lineage['checkpoints']['broader_candidate']['cumulative_sft_targets']==14299
teacher=read(R/'teacher-bank-readiness.json');assert teacher['current_native_serialization_fit']==757 and teacher['fit_assistant_eos_targets']==45792 and teacher['training_admitted']==0
assert sha(P/'restart/sol-conversation-data-1000-v1/private/train-candidates.jsonl')==teacher['source_sha256']
assert read(R/'setup-failure.json')['analysis_positions']==0
receipt=dict(status='READ_ONLY_AUDIT_INTEGRITY_PASS_NOT_CAPABILITY_GATE',all_model_and_frozen_input_hashes_verified=True,transitive_previous_output_and_retention_hashes_verified=True,optimizer_updates=0,training_updates=0,gradient_evaluations=24,forward_diagnostic_examples=1520,seen_training_generations=64,analysis_positions=487424,aggregate_positions=494773,historical_training_stop_unchanged=True,no_optimizer_step_or_checkpoint_call_in_audit_sources=True,teacher_bank_admitted=0,teacher_bank_format_fit=757,setup_failure_preserved_with_zero_model_work=True,original_audit_clock_preserved=True,promotion=False,proposal_executed=False)
(R/'audit.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
