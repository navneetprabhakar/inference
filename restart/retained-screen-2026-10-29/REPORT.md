# Four-arm retained research screen — 29 October 2026

**Screen completed. No automatic promotion.** All four endpoints are retained as research artifacts; neither a natural-conversation acceptance test nor a final test was run.

## Endpoint comparison

| Arm | Wording | Replay | D correct | D rate | State conversations | Native NLL | NLL change | Acquisition gates |
|---|---|---:|---:|---:|---:|---:|---:|---|
|0|canonical|0.5|104/352|29.5%|4/32|2.1938|+63.3%|FAIL|
|1|diverse|0.5|183/352|52.0%|4/32|2.1706|+61.6%|FAIL|
|2|canonical|0.0|113/352|32.1%|12/32|12.1864|+807.4%|FAIL|
|3|diverse|0.0|129/352|36.6%|3/32|16.8541|+1154.9%|FAIL|

D means unseen fact combinations and reserved instruction wording, relative to the prepared curriculum. These are synthetic prerequisite cases, not general conversation. Native NLL is compared with the shared source baseline 1.343035.

## Matched wording contrasts

- Replay 0.5: diverse versus canonical, 104 gains and 25 losses across 352 D turns; difference +22.4 percentage points. Descriptive cluster-bootstrap interval [+16.8, +28.1] points.
- Replay 0.0: diverse versus canonical, 56 gains and 40 losses across 352 D turns; difference +4.5 percentage points. Descriptive cluster-bootstrap interval [+0.0, +9.4] points.

The interval resamples scenario clusters within tasks. It does not estimate variation across training seeds or independent linguistic families. This is one seed and four reserved wording strings per task. No causal generalization beyond this controlled packet is justified.

## Task failures

|Task|Canonical + replay|Diverse + replay|Canonical, no replay|Diverse, no replay|
|---|---:|---:|---:|---:|
|clarification|18.8%|75.0%|0.0%|50.0%|
|distractor|25.0%|6.2%|34.4%|18.8%|
|format|15.6%|15.6%|43.8%|15.6%|
|location|12.5%|12.5%|18.8%|6.2%|
|missing|53.1%|59.4%|46.9%|50.0%|
|name|15.6%|28.1%|3.1%|9.4%|
|state|45.8%|70.8%|67.7%|67.7%|
|time|28.1%|87.5%|3.1%|0.0%|

Thresholds were fixed before launch: D overall >=90%, each task >=80%, whole state conversations >=80%, and both-correct counterfactual groups >=80%. These are operational prerequisite gates, not external standards. No borderline or unrecognized output was silently upgraded. Raw unmatched clarification outputs remain flagged for review.

## Accounting

Cumulative totals, including all prior calibration: 4,612 optimizer applications; 14,753,542 input positions; 221,052 assistant/EOS targets; 4,722,688 narrative targets; 19.43 active-model minutes. The screen itself added exactly4,000 updates; calibration contributed612. Limits were4,612 updates,50M positions,1M assistant targets,10M narrative targets and150 total active minutes.

The successor ledger imported the calibration charge once and preserved its source ledger unchanged. All four arms started from identical original foundation parameters, fresh optimizer and the same seed. No checkpoint from the disposable calibration was used as a retained source. Checkpoint I/O was timed; scheduled evaluations used generated history and normal EOS. Checkpoints were saved every25 updates; this changes only durability frequency, not training arithmetic or data.

## Decision boundaries

Acquisition-qualified arms: none. The original source behavior baseline remains0/80, so behavioral preservation is INCONCLUSIVE rather than passed. Native narrative retention is a limited distribution-specific proxy. The historical+5% line did not stop branches or promote them.

The predeclared same-replay pair rule suggests arms [0, 1] for potential confirmation. This is an analytical selection, not approval to run more seeds or a claim that either model is acceptable. All arms and their failures remain reported. Read the [final reassessment](REASSESSMENT.md) alongside these results before further training.

[Machine-readable assessment](assessment.json) · [Execution result](result.json) · [Calibration carry-forward](carry-forward.json)
