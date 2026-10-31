# Experiment history and evidence — 31 October 2026

Only the restarted project is active. Older project files remain on the archive branch and in the sibling archive directory. Reports below are historical evidence; current operating policy is in the top-level documents.

| Stage | Outcome | Evidence |
|---|---|---|
| Local benchmark and 100M pilot | Complete; random initialization, 100M tokens | [Pilot evaluation](../reports/evaluation-v1/REPORT.md) |
| Broader pretraining | Stopped at 200M total; no 300M run | [200M evaluation](../reports/continuation-v1/200m/REPORT.md) |
| Original SFT V1 | Superseded due to padding/data/scoring issues | reports/sft-v1/ and original configs retained |
| Revised SFT V2 | Two 100M-base 5M-slot arms completed; two planned 200M-base arms unstarted | [Comparison](../reports/sft-v3/COMPARISON.html) |
| Memory investigation | Sequential jobs, 256MiB cache cap fixed production cache growth | reports/sft-v2/memory-investigation/ |
| V3 data/evaluation fixes | Frozen masks, diversified fixtures, stricter execution scoring | [Readiness](../reports/sft-v3/READINESS.html) |
| V3 weighted repair | Two 2M-slot arms complete; LR 3e-5 at 2M selected | [Results and actual outputs](../reports/sft-v3/experiment/REPORT.html) |
| Repetition penalty sweep | Complete; 1.2 retained under guards; no weight changes | [Results and actual outputs](../reports/sft-v3/penalty-sweep-v1/REPORT.html) |

The selected model lineage is random initialization → 100M pretraining → V2 LR 3e-5 / 5M processed slots → V3 LR 3e-5 / 2M processed slots. Do not call it a 200M-base model or sum SFT processed slots as pretraining target tokens.

V3 dev selection chose repair-lr3-2m with score 0.736667 and all declared guards passing. The selected checkpoint and two reference checkpoints were then evaluated on the same 1,000-case test release. Human chat review remains pending; blind-review exports are provided alongside reports.

Snapshot configs retain their original launch status. Runtime campaign JSON files are local-only and may retain historical child PIDs after completion. Completed reports plus verified process state establish completion, not a config status string.

Do not edit raw generations to improve presentation. They contain model errors, malformed output and occasional trailing whitespace. This is intentional evidence. Preserve old failed runs for diagnosis while using README.md for the current measured position.
