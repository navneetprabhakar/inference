"""Record direct response inspection and close the bounded SFT experiment; no model execution."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;RUN=ROOT/'attempt-3';PRIVATE=RUN/'private';PROJECT=ROOT.parents[1]
def read(p):return json.loads(p.read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n')
def main():
 r=read(RUN/'result.json');assert r['status']=='BOUNDED_TEST_COMPLETE_PENDING_RESPONSE_ASSESSMENT'
 before=read(PRIVATE/'before-responses.json');after=read(PRIVATE/'after-responses.json');assert len(before)==len(after)==24
 # Every complete paired response was directly read by the primary assistant before writing this assessment.
 reasons={
 'p01':'Fails owner extraction/correction; unrelated or repetitive invented events.',
 'p02':'Fails both arithmetic answers; unrelated or repeated numbers.',
 'p03':'Does not give the supplied room or corrected room; repeats meeting phrases.',
 'p04':'Does not accurately retain preferences; final response contradicts water-only correction.',
 'p05':'Final begins with relevant location but continues into invented bag/box story; not a fully correct response.',
 'p06':'Does not identify the stated ruler owner.',
 'p07':'Does not calculate the required total boxes.',
 'p08':'Does not calculate required change; invents ticket numbers.',
 'p09':'Fails exact supplied starting time and output constraint.',
 'p10':'Invents dialogue instead of acknowledging missing sender information.',
 'p11':'Fails capability/booking honesty answer and produces unrelated story text.',
 'p12':'Does not provide a polite rewrite; unrelated repetitive pencil story.',
 'p13':'Does not produce requested JSON.',
 'p14':'Does not apply stated badge rule or produce the count.',
 'p15':'Does not provide a coherent causal answer; final contradicts wet/dry state.',
 'p16':'Violates one-word answer and does not correctly present alphabetical ordering.',
 'p17':'Does not identify supplied key owner and invents a room/story.',
 'p18':'Does not resolve cup/guest constraint; unrelated repeated cup statements.',
 'p19':'Does not ask or name a useful missing trip detail.',
 'p20':'Does not summarize supplied cause/action and invents a talking bus.'}
 rows=[]
 for a,b in zip(before,after):
  assert (a['id'],a['turn'])==(b['id'],b['turn'])
  rows.append(dict(id=a['id'],turn=a['turn'],before_correct=False,after_correct=False,reason=reasons[a['id']]))
 save(PRIVATE/'response-assessment.json',dict(reviewer='Primary assistant directly inspected all 24 complete before/after pairs; no external or teacher grader',rubric='Whole response must answer supplied question accurately, follow explicit constraints, and avoid major contradiction or invented events; containing an expected keyword alone does not pass.',rows=rows,before_correct=0,after_correct=0,total=24,limits='Small authored, exposed diagnostic suite; not a broad capability benchmark.'))
 base=r['baseline'];chosen=r['selected_checkpoint'];devgain=1-chosen['development_assistant_nll']/base['development_assistant_nll'];testgain=1-r['final_test_assistant_nll']/base['test_assistant_nll'];reg=chosen['foundation_nll']/base['foundation_nll']-1
 decision=dict(status='BEHAVIORAL_SUCCESS_GATE_FAILED_STOP',training_updates_consumed=r['training_updates'],sft_supervised_targets_consumed=r['sft_supervised_target_exposures'],selected_epoch=chosen['epoch'],selected_updates_retained=chosen['updates'],selected_sft_supervised_targets_retained=chosen['supervised_targets'],discarded_update_count=r['training_updates']-chosen['updates'],discarded_sft_target_exposures=r['sft_supervised_target_exposures']-chosen['supervised_targets'],development_assistant_nll_reduction_fraction=devgain,test_assistant_nll_reduction_fraction=testgain,foundation_nll_increase_fraction=reg,probe_correct_before=0,probe_correct_after=0,probe_total=24,before_end_turn_token_emitted=sum(x['stop_token']==2 for x in before),after_end_turn_token_emitted=sum(x['stop_token']==2 for x in after),pass_gates=dict(numerical_correctness=True,development_loss_improvement=devgain>=.05,foundation_regression_within_5_percent=reg<=.05,response_correct_min_6=False,response_improvement_min_4=False),training_complete=True,training_paused=True,more_training_authorized=False,checkpoint_promoted=False,original_reference_unchanged=True,actual_parameters=15191712,aggregate_wall_seconds_including_setup_repairs=r['elapsed_seconds'],student_positions_all_attempts=r['total_positions'],setup_failures_before_work=2,source_checkpoint=read(RUN/'plan.json')['source_checkpoint'],selected_research_checkpoint=chosen['checkpoint'],selected_research_checkpoint_sha256=chosen['sha256'],response_audit='attempt-3/private/response-assessment.json',limitations=['This tiny 62-conversation experiment tests local learning and format transfer; it does not establish that SFT or sub-100M conversation models are infeasible.','Loss improvement is not conversational competence.','Training and checked responses use the same frozen segmented chat format; all emitted responses were inspected without trimming failed continuations.','Foundation-recovery D0 remains stopped; no foundation data admission or R1/R2 work resumed.'])
 save(ROOT/'decision.json',decision)
 save(ROOT/'execution-status.json',dict(status=decision['status'],all_training_finished=True,automatic_continuation=False,checkpoint_promoted=False,source_weights_unchanged=True))
 lines=['# Bounded conversation SFT diagnostic — behavioral gate failed','',
 'Owner authorized preparation, a carefully reviewed subset, formatting/masking correctness checks, and a short SFT experiment with before/after responses and foundation regression checks. This is a separate diagnostic on our own 15,191,712-parameter checkpoint; it does not resume the failed foundation-recovery experiment.','',
 '## Result','',
 '**No reliable conversation improvement: 0/24 fully correct before and 0/24 after.** Responses remain repetitive story-like continuations. No output emitted an EOS end-of-turn token; all 24 after responses reached the 48-token limit. A response beginning with a relevant location but continuing into fabricated events was retained intact and failed the whole-response rubric.','',
 '| Metric | Before | Selected checkpoint |','|---|---:|---:|',
 f"| Development assistant NLL | {base['development_assistant_nll']:.6f} | {chosen['development_assistant_nll']:.6f} ({devgain:.1%} lower) |",
 f"| Test assistant NLL | {base['test_assistant_nll']:.6f} | {r['final_test_assistant_nll']:.6f} ({testgain:.1%} lower) |",
 f"| Foundation narrative NLL | {base['foundation_nll']:.6f} | {chosen['foundation_nll']:.6f} ({reg:.1%} higher) |",
 '| Fully correct diagnostic responses | 0/24 | 0/24 |','',
 'Numerical correctness and loss-improvement gates passed; behavioral success gates failed. Training stopped at the fixed budget. No candidate was promoted, no extra epochs were run, and the original reference remains unchanged.','',
 '## Data, format and correctness','',
 'Frozen selection: 64 training plus 10 development plus 10 test conversations. All 84 were directly reviewed; two training records were held and not replaced. Final train: 62 conversations, 8,690 content tokens, 3,704 assistant-content tokens and 3,830 supervised targets including 126 EOS tokens per pass. Development/test contain 547/542 supervised targets. Whole task families remain split apart. All sequences fit the actual format within 256 next-token positions without truncation.','',
 'Format: one BOS, then each user message encoded as `User: text\\nAssistant:`, followed by separately encoded assistant content and EOS. Segment encoding is the authoritative format at both training and inference. Loss covers assistant content and EOS only; user/role-label targets and padding are zero-masked. Exact prompt-prefix equality was checked for every assistant turn.','',
 'Native MLX BF16 with FP32 masters/moments was checked against independent Torch FP32 masked loss and all parameter gradients: absolute NLL difference 0.002218, relative gradient L2 error 0.01919, cosine 0.9998165. Changing only zero-masked targets or right-padding inputs changed masked loss by exactly zero. Tolerances were frozen before inference; no numerical tolerance was relaxed.','',
 '## Budget and checkpoints','',
 'Fresh SFT AdamW state; original parameters/architecture/tokenizer preserved. Batch 8, max 3 passes/24 updates, LR 5e-5 with two-update warmup, norm clip 1. Hard training stops: nonfinite values, gradient norm above 100, foundation NLL >5% above baseline, development NLL >10% above baseline. The planned 45-minute clock and 2M-position ceiling include setup repairs.','',
 f"Consumed: {r['training_updates']} updates, {r['sft_supervised_target_exposures']:,} supervised target exposures, {r['total_positions']:,} student positions across correctness, training and evaluations, {r['elapsed_seconds']:.1f} seconds on the original aggregate clock. Peak reported MLX memory {r['memory']['peak_active_or_driver_bytes']/1024**3:.2f} GiB. No teacher calls or downloads.",'',
 f"Epoch 2 was selected solely by development NLL among checkpoints within the foundation-regression limit: {chosen['updates']} retained SFT updates and {chosen['supervised_targets']:,} retained SFT target exposures. Epoch 3's 8 updates/3,830 exposures remain charged but are not selected. Test NLL and final responses did not select the checkpoint.",'',
 'Research checkpoint: `attempt-3/epoch-2.pt`. Original source: `restart/foundation-resolution-v1/B/checkpoint.pt`, SHA256 `bf45241501cee600bd618677dc1a3ae666e6f50d9c628e29e7326ee9c87d338d`. Child checkpoints include fresh optimizer state, own weights, RNG state and separate foundation/SFT provenance. No weights are pushed to Git.','',
 '## Setup repairs and evidence','',
 'Two setup defects stopped before any inference positions or updates: missing upstream import path, then the wrong adapter return type. Both failed attempts and their stops are preserved. Attempt 3 corrected those dependencies; it reused the original clock and aggregate work/training caps. This was an infrastructure repair, not a retry of a failed numerical or scientific gate. See `attempt-2/repair-receipt.json` and `attempt-3/repair-receipt.json`.','',
 'Detailed local response evidence: `attempt-3/private/before-responses.json`, `attempt-3/private/after-responses.json`, `attempt-3/private/response-assessment.json`. Dataset/selection/review files remain private. Public receipts include data counts, numerical checks, epoch history, hashes and aggregate decisions.','',
 '## Interpretation','',
 'The update moved the model toward demonstration tokens but did not produce reliable instruction-following or learned stopping. Three passes over 62 conversations are too small to establish the limits of SFT or the under-100M objective. These results do not justify scaling this schedule automatically. Further work requires a separately scoped decision about foundational language quality and a focused format-learning diagnostic; this run is closed.']
 (ROOT/'README.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps(decision,indent=2))
if __name__=='__main__':main()
