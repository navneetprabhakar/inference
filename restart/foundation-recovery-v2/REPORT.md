# Foundation recovery v2 — terminal preparation stop

- **Result: INCONCLUSIVE_STOP in R0 after 5.25 minutes.** This was an evaluation preparation defect I introduced, not a failed student training result.
- **Zero training updates, zero training targets and zero paid teacher requests.** D0, R1 and R2 never started. No source was selected; no new usable-data counts are claimed.
- The grammar bank contained `The two childs`. Static inspection also found that the sealed fact generator reused development stems in location and negation cases. Original sealed payloads remained unopened. Arithmetic/token-span tests had passed; they did not establish semantic validity or split independence.
- I interrupted the supervisor; its cleanup reaped the active worker. All model workers are gone. All frozen files and all three original checkpoint hashes still match.
- Work charged: **1,021,037 reserved student positions**, including partial interrupted evaluation. These are processed-work reservations, not training targets or usable corpus tokens. Partial generations and objective diagnostics remain local/auditable; they cannot select or promote a checkpoint.
- Completed step1745 native BF16 NLL was1.5271154 versus independent FP32 1.5269849, difference0.0001305 (within0.02). Step2889 native NLL1.4006886 is partial diagnostic evidence; its full receipt/parity was not completed. Cooldown3145 was not evaluated. No capability improvement is inferred.
- Peak phase process-tree RSS was0.709GiB. The last recorded global swap was below the original382.75MiB baseline; free disk remained about128.3GiB. No resource stop occurred.

## Correction prepared on CPU only

A separate [correction proposal](correction-proposal/proposal.json) preserves the original frozen attempt. Its proposed bank fixes the plural, separates sealed fact wording/vocabulary/situations, and passes new authoring checks:120unique grammar prefixes,100unique fact prefixes per split,zero normalized development/sealed fact-prefix duplicates,balanced answer locations and equal native suffix lengths. This remains research evaluation; independent human custody is not certified. Private sealed text and authoring sources remain outside Git.

The proposed replacement R0 has a45-minute cap,4M processed-position cap,10teacher requests and zero updates. Conditional D0/R1/R2 retain the approved thresholds and caps. The aborted1,021,037positions remain charged; the proposal explicitly updates the combined accounting. It has **not been approved or launched**.

The approved [PLAN.md](PLAN.md#hard-stops-and-execution-controls), line156, says: “Post-launch technical stops permit no model replay, tolerance relaxation, prompt rescue or extra updates.” A corrected model-executing attempt therefore requires a new explicit approval; the original clock/stop are not reset.
