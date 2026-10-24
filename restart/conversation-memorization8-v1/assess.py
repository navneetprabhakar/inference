"""Verify and summarize the closed eight-conversation memorization test; no model execution."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parents[1]
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def main():
 r=read(ROOT/'result.json');assert r['status']=='MEMORIZATION_PASS'
 plan=read(ROOT/'plan.json');data=read(ROOT/'data-receipt.json');last=r['last_checkpoint']
 before=read(ROOT/'private/step-000-responses.json');after=read(ROOT/'private/step-025-responses.json')
 assert r['updates']==25 and r['supervised_target_exposures']==25*data['supervised_targets_per_update']==1100
 assert len(before)==len(after)==10 and len({x['id'] for x in after})==8
 assert all(x['exact_token_match'] and x['eos_emitted'] and x['stop_token']==2 and x['response']==x['expected'] for x in after)
 assert last['greedy']['exact_conversations']==8 and last['teacher_forced']['correct_tokens']==last['teacher_forced']['supervised_tokens']==44
 assert last['foundation_nll_increase_fraction']<=.05 and r['elapsed_seconds']<900 and r['total_positions']<=2000000
 for name,digest in plan['sources'].items():assert hashlib.sha256((PROJECT/name).read_bytes()).hexdigest()==digest
 assert hashlib.sha256((PROJECT/plan['source_checkpoint']).read_bytes()).hexdigest()==plan['source_sha256']
 assert hashlib.sha256((PROJECT/last['checkpoint']).read_bytes()).hexdigest()==last['checkpoint_sha256']
 correctness=read(ROOT/'correctness.json');assert correctness['status']=='PASS' and correctness['masked_label_change_loss_difference']==correctness['padding_input_change_loss_difference']==0
 decision=dict(status='MEMORIZATION_PASS_TRAINING_CLOSED',conversations_exact_before=0,conversations_exact_after=8,conversations=8,assistant_turns_exact_before=0,assistant_turns_exact_after=10,eos_turns_before=0,eos_turns_after=10,assistant_turns=10,source_parameters=15191712,source_unchanged=True,training_updates=25,training_supervised_target_exposures=1100,student_positions=r['total_positions'],elapsed_seconds=r['elapsed_seconds'],foundation_nll_before=r['baseline']['foundation_nll'],foundation_nll_after=last['foundation_nll'],foundation_nll_increase_fraction=last['foundation_nll_increase_fraction'],numerical_correctness_pass=True,free_generation_review='Primary assistant read all ten final responses; each matches its expected answer and emits EOS. Multi-turn tests use previous generated answers, not gold substitutions.',greedy_protocol='Fixed 24-new-token maximum, argmax over full vocabulary, stop only BOS/EOS, no answer injection, no rerolls or forced output tokens.',training_stopped_early=True,training_paused=True,checkpoint_promoted=False,automatic_continuation=False,generalization_measured=False,next_decision='A separately bounded short-answer-first SFT experiment with fresh held-out prompts; retain the distinction between memorization and generalization.')
 save(ROOT/'decision.json',decision)
 save(ROOT/'execution-status.json',dict(status=decision['status'],training_finished=True,automatic_continuation=False,checkpoint_promoted=False,source_unchanged=True))
 lines=['# Eight-conversation memorization test — passed','',
 '**Passed at update 25 and stopped early.** All eight training conversations exactly reproduce all ten assistant answers, including both correction follow-ups, and all ten assistant turns emit EOS. Baseline: zero exact conversations, zero exact assistant turns and zero EOS endings.','',
 'This is a deliberate training-set memorization check. It establishes that this model/trainer/format can fit these examples and learn stopping under the guardrail. It does not measure unseen generalization, independent conversation quality, or internal/MCP tool use.','',
 '## Measured results','',
 '| Metric | Before | Update 25 |','|---|---:|---:|','| Exact full conversations | 0/8 | 8/8 |','| Exact assistant turns | 0/10 | 10/10 |','| EOS-ending turns | 0/10 | 10/10 |','| Teacher-forced correct target tokens | 8/44 | 44/44 |',
 f"| Training assistant/EOS NLL | {r['baseline']['teacher_forced']['assistant_nll']:.6f} | {last['teacher_forced']['assistant_nll']:.6f} |",
 f"| Fixed foundation narrative NLL | {r['baseline']['foundation_nll']:.6f} | {last['foundation_nll']:.6f} (+{last['foundation_nll_increase_fraction']:.2%}) |",'',
 f"Consumed: 25 updates, 1,100 assistant/EOS target exposures, {r['total_positions']:,} student positions including correctness/evaluations, {r['elapsed_seconds']:.2f} seconds of execution. Peak reported MLX memory {r['memory']['peak_active_or_driver_bytes']/1024**3:.2f} GiB. Original bounds were 15 minutes, 200 updates, 2M positions, 40k supervised targets, checkpoint/evaluation every 25 updates. Success ended execution at the first checkpoint.",'',
 '## Training and safeguards','',
 'Source: unchanged own foundation checkpoint at `restart/foundation-resolution-v1/B/checkpoint.pt`, SHA256 `bf45241501cee600bd618677dc1a3ae666e6f50d9c628e29e7326ee9c87d338d`. Architecture remains 15,191,712 parameters and the native 32k tokenizer is unchanged. The earlier failed SFT child was not used.','',
 'Eight directly reviewed self-authored training examples cover direct answers, a greeting, corrections, clarification and uncertainty; see `examples.json`. Ten assistant turns contain 44 supervised targets, including ten EOS targets, per update. No new teacher calls or downloads.','',
 'Uses the prior verified segmented chat format and assistant/EOS-only loss. Fresh AdamW state, BF16 compute with FP32 parameters/moments, LR5e-5 with five-update warmup, batch8, context256 and gradient clipping1. Hard stops: narrative NLL >5% above baseline, nonfinite quantities, gradient norm above100, zero first parameter update, resource or work limits. No guardrail was relaxed.','',
 f"Independent Torch FP32 versus native BF16 preflight: masked NLL difference {correctness['absolute_nll_difference']:.6f}, relative gradient L2 {correctness['gradient_relative_L2']:.6f}, gradient cosine {correctness['gradient_cosine']:.7f}. Changing masked target labels or right-padding inputs changed loss by zero. First-update parameter L2 change was {r['first_update_parameter_delta_L2']:.6f}; final change from the source was {last['parameter_delta_L2']:.6f}.",'',
 'Free generation uses full-vocabulary greedy decoding with max24 new tokens and only BOS/EOS stopping. Previous turns in the correction conversations use generated responses. Expected answers are used only for scoring; no gold answer is inserted into the next-turn history. The primary assistant directly inspected all ten final outputs.','',
 '## Artifacts and next decision','',
 'Research child checkpoint: `epoch-25.pt`; its optimizer step is25 and its SFT exposure count is1,100. The source checkpoint remains unchanged and no child was promoted. All workers have exited; training is paused.','',
 'Complete local response evidence is in `private/step-000-responses.json` and `private/step-025-responses.json`. Checkpoint weights, optimizer state and encoded arrays remain local. Code, the intentionally public eight-example training set, counts, hashes and aggregate decisions are versioned.','',
 'Next scientific question: whether a short-answer-first curriculum transfers to fresh held-out conversations. This test changed example complexity, repetitions per example and EOS frequency relative to the previous 62-conversation run; it does not isolate which factor explains the difference. Larger SFT and foundation recovery were not resumed.']
 (ROOT/'README.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(decision,indent=2))
if __name__=='__main__':main()
