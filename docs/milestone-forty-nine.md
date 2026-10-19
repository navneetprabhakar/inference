# Measured optimizer choice and selected continuation

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

Continue the **3e-4** chain from its actual step-256 checkpoint. Both optimizer screens completed exactly **256 updates / 262,144 positions** from canonical random initialization. The lower rate wins on the frozen equal-source foundation NLL, with an advantage of **0.1424 nats**. This is a single-seed local optimizer choice, not a universal learning-rate recommendation or conversation-capability result.

| Frozen validation NLL, lower is better | 3e-4 | 1e-3 |
| --- | ---: | ---: |
| Primary: equal-source full-foundation NLL | **6.884507** | 7.026882 |
| Secondary: equal-source assistant-target NLL | **6.908135** | 7.023889 |
| OASST foundation NLL | **6.597144** | 6.760799 |
| Dolly foundation NLL | **7.171871** | 7.292965 |

Both scores use the same **64 frozen groups / 32 per source**, with complete conversations up to 1,024 positions and at least 16 assistant targets. No validation refitting, truncation, test-set model scoring or teacher repair. The primary difference exceeds the predeclared 0.01-nat lower-rate tie allowance; the secondary metric does not determine selection. No significance claim across seeds or the full source population is inferred.

## Actual controls and runtime

Independent actual-run checks confirm that the two logical plans differ only in `recipe.lr`. Data/schedule, tokenizer, initialization seed, architecture, numerical conventions, optimizer settings apart from rate, limits and source-code hashes are identical. Both start without a resume checkpoint. Their first pre-update losses match exactly at **9.741898536682129**. This is a first-loss control, not an independent initial-tensor equality or trajectory-parity audit.

Both terminal checkpoints were fully verified before scoring: exact plan/state counters, complete event coverage, source-bound validation selection, model/optimizer payload integrity and finite losses. Cached selection then rechecks the scored checkpoint bytes and recomputes metric aggregation before choosing the resume state.

| Observed short-run resource metric | 3e-4 | 1e-3 |
| --- | ---: | ---: |
| Total invocation seconds | 313.52 | 342.23 |
| Actual update seconds | 253.84 | 277.14 |
| Preflight seconds | 50.51 | 56.18 |
| Checkpoint seconds | 8.16 | 7.85 |
| Process peak RSS, bytes | 6,011,273,216 | 6,096,076,800 |
| MLX allocator peak, bytes | 4,027,989,136 | 4,027,989,136 |

Allocator memory overlaps process RSS on unified memory; do not add them. These are short local observations with ordinary background activity, not controlled rate-dependent performance differences or sustained main-run/inference latency measurements. The first training launch is tied to source commit `d4d41609b13532b276e3bad906553cfa582cecca`; both actual plans bind the same training implementation.

## Remaining work and physical accounting

- Already executed: **524,288 positions** across two separate screen models.
- Selected-chain target: **10,223,491 positions / 9,984 updates**, including the selected screen's existing 262,144 positions.
- Remaining selected continuation: **9,961,347 positions / 9,728 updates**.
- Planned total physical training: **10,485,635 positions**, within the 10,485,760 ceiling, including the discarded trial.

The continuation launcher reconstructs the saved decision from both complete scored screens, checks historical reservations, takes the shared exclusive execution lock and writes one persistent remaining-work reservation. It resumes only the selected checkpoint under the **unchanged 3e-4 logical plan**; it does not initialize again or reset warmup/moments/cursor. A failed invocation retains its reservation and requires reconciliation. No extra screen, replay update or automatic fresh restart is authorized by this frozen experiment.

On this Mac, run the continuation through `caffeinate -i` to hold an idle-sleep assertion only while the process is alive. The actual machine reports AC power and a fully charged battery before launch. No permanent power setting changes.

The terminal scorer is implemented and tested before main continuation. It requires complete exhaustion of the selected schedule, the exact selected resume identity, initial/final/invocation counts, physical-budget reconciliation, event coverage, unchanged source-bound groups and verified terminal state. It then reconstructs canonical initial weights and compares frozen foundation and assistant-target NLL, using the predeclared source-stratified paired bootstrap. A partial/fresh/wrong-plan run cannot be scored as complete.

After terminal verification and loss evaluation, conduct the required actual multi-turn conversation, preserve raw answers/history and publish direct scoring. Do not substitute NLL for the conversation assessment. The second iteration is not complete at this decision point; its longer foundation continuation and separate conversation-SFT admission remain open. The previous completed iteration's conversation score remains 0/100.

## Verification and artifacts

**26 focused checks passed**, covering cached source/metric/state identity, changed payloads, partial/resumed screens, missing trial, altered budget, persistent continuation reservations, declared bootstrap and incomplete/fresh/wrong-checkpoint terminal rejection. These use synthetic fixtures for refusal paths; actual full-size screen execution and both 64-group scores provide separate real-model evidence. Earlier 163 passed / three skips is historical, not a rerun here.

- [Actual first-screen score](../reports/iteration-two-lr-0003-score.json)
- [Actual second-screen score](../reports/iteration-two-lr-0010-score.json)
- [Independent controls and runtime receipt](../reports/milestone-forty-nine-controls.json)
- [Frozen-rule selection and resume identity](../reports/milestone-forty-nine-optimizer-selection.json)

No new teacher launch, Platform API call, cloud job, purchase/reset or spending authorization. Teacher reservations remain 17/20; conservative CUDA allowances USD 7/10, settled costs unknown. Learned MLX/CUDA quality, production/source/teacher rights, broader conversation styles/content, tool/MCP capability and later ESCI remain open. Full goal active/incomplete.

```sh
# Already completed: terminal screens, scoring and frozen-rule selection.
.venv/bin/python scripts/check-iteration-two-controls.py
.venv/bin/python scripts/select-iteration-two.py

# Execute the selected continuation once. Existing reservation/output is refused.
caffeinate -i .venv/bin/python scripts/continue-iteration-two.py

# Only after the selected continuation reaches its verified terminal schedule.
.venv/bin/python -m slm.eval.iteration_two_terminal \
  --root data/iteration-two-experiment-v1 \
  --selection reports/milestone-forty-nine-optimizer-selection.json \
  --freeze reports/milestone-forty-eight-experiment-freeze.json \
  --output reports/iteration-two-terminal-score.json
```
