# Astra run result · 5 November 2026

**Stopped at the conversation gate.** The random-initialized 124M GPT-2 learned next-token prediction on the laptop. Both the pretraining base and the supervised endpoint passed **0 of 12** complete development conversations and **0 of 24** substantive turns. The sealed 100-case confirmation set has zero scored cases.

| Measured outcome | Result |
|---|---|
| Hardware | 1,018 end-to-end targets/s over 30 measured minutes, with save/restore. The final ten minutes averaged 1,024/s. |
| Candidate base | 2,457,600 distinct training targets, 600 optimizer steps, 39m 48s elapsed. Encyclopedia validation CE fell from 11.01 to 6.40. Story CE fell from 11.04 to 3.42. |
| Supervised diagnostic | 289 synthetic teaching conversations, two passes, 48,210 input tokens and 12,438 assistant targets. All 74 updates completed in the budget. Training and both evaluations together took 5m 12s. |
| Paired transfer | Copying 0/20, correction 0/20, and result grounding 0/20. Every one of the 120 individual answers missed its expected value. |
| Sequential conversations | After SFT, 7/12 sessions completed both turns in the required message format, up from 0/12. Both candidates earned 0/12 on answer correctness. The student dispatched zero tools in these sessions. |
| Promotion | Experimental checkpoint retained. Training ended at the failed development gate. The sealed set was used for overlap screening only. |

**Concrete failure.** In the reed-spacing probe, the recorded tool result was 108 in one trace and 109 in its paired trace. The supervised endpoint gave the valid answer frame `{"text":"6"}` both times. In another case, the user identified the overnight bus as Heron and asked which service they were taking. The endpoint answered “I've noted.” This failure occurred even though the hosted broker itself passed authorization, revocation and actual-result replay tests.

**Interpretation.** Supervision improved message termination and formatting. All 120 probe responses reached the end marker. Of those, 43 were valid answer frames and all 43 were wrong. The other 77 had invalid JSON or an invalid call schema. The base still repeated phrases, and supervised outputs frequently echoed acknowledgment patterns in the small teaching set. This single run cannot separate the effects of pretraining scale, teaching diversity, and the burden of learning JSON generation. Its evidence supports closing this candidate at the preregistered stop.

## Retained artifacts

- The immutable pre-SFT base is recorded in `pretraining.json` and the experimental endpoint in `conversation-results.json`. Full local weights and raw per-member output IDs remain under `runs/astra-candidate-01/` and `runs/astra-sft-01/`. The raw baseline and endpoint transcripts are `base-development.json` and `endpoint-development.json` in the SFT run.
- `probe-diagnosis.json` records parse failures, incorrect but well-formed answers, and repeated outputs. `conversation-results.json` includes all 12 blinded case assessments. The two independent assistant reviewers each scored six cases and both candidates against prewritten rubrics.
- `pilot.json`, `benchmark.json`, `candidate-budget.json` and `pretraining.json` contain the measured stage decisions. `retention.json` verifies the protected and resumable checkpoint hashes and confirms the device lock was released.
- Work stayed local at zero paid API or cloud cost. The run used synthetic offline adapters. Experimental code and sanitized evidence are on the local working branch.
