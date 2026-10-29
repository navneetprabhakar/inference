# G0 reassessment: preparation stopped; do not launch

The fixed campaign reached **STOP_DATA_ADMISSION** during its single prelaunch repair batch. G0 is not complete and no training or student inference was started. This is a data-preparation failure, not new evidence that the model can or cannot learn coherent conversation.

## Decisive evidence

The fresh broad-data audit found seven major extraction/domain defects in the first twelve fully read documents of the frozen 100-document sample. That already exceeds the maximum five; the other 88 were not reviewed and no population defect rate is claimed. Examples include assignment-only units, missing linked material, and academic reference prose assigned to everyday language. The initial seven judgments and hashes are in `broad/initial-semantic-review.json`.

One conservative repair quarantined assignment/link-dependent units and reassigned academic book strata to educational prose. This policy is a coarse filter, not certification that the remaining texts are correct or usable. Training-side candidate counts after repair:

| Domain | Candidate tokens | Required minimum |
|---|---:|---:|
| Everyday | 787,316 | 1,000,000 |
| Procedural | 2,892,926 | 1,000,000 |
| Educational/explanatory | 6,902,288 | 1,000,000 |

The everyday shortfall is 212,684 tokens. Total volume cannot compensate for the domain floor. **Admitted broad tokens remain zero.** A second 100-document semantic sample cannot fix insufficient supply, so that recheck was not run. No extra corpus, relabeling to meet quotas, or second repair was attempted. Original candidate and repaired inventories are retained separately.

## Prepared assets and remaining gates

| Asset | State |
|---|---|
| Fresh readiness benchmarks | Drafted: 60 continuations, 120 grounded choices with controls, 60 grammar contrasts. One repair fixed native BOS/joint suffix scoring, domain registers and sentence constraints; 1,560 candidate/control sequences and synthetic suffix checks pass. `benchmarks/repair_v2.json` records the evidence; independent full review is incomplete, so not admitted. |
| Natural development | Drafted: 120 conversations, 20 per function. Only 20 underlying event clusters; shared templates and structure/topic dependence limit breadth. Independent semantic review remains incomplete. |
| Final candidate | 240 conversations/710 turns, held by separate custodian. Independently reviewed; all four defect categories passed the one fixed repair recheck (`benchmarks/final_recheck_metadata.json`). **Unsealed**: overlap/admission clearance absent. Parent did not inspect private payload. See `final-custody/` public receipts. |
| Reviewer calibration | Both independent blind reviewers scored **24/24 clear anchors**, above the fixed 23/24 requirement. Twelve borderline cases excluded from clear-anchor accuracy; no student-output agreement claim. |
| Conversation training | 6,400 candidates/17,600 turns; quotas, native serialization, 256-context bound and two frozen 1,000-step schedules pass CPU checks. Only 80 actual records/220 turns received first independent semantic review, plus separate inspection of 40 frames and generator. Remaining 6,320 records and the 20% second review are unfinished. **Zero admitted conversations.** |
| Replay/overlap/execution | New replay admission, full cross-set overlap clearance, executable launch scorer and measured feasibility are unfinished. Preparation stopped before spending additional review budget on assets that cannot release this campaign. |

The training set is 40 source frames expanded across functions, structures and assignments; 6,400 records do not mean 6,400 independent scenarios. The final candidate similarly contains 40 clusters adapted across six functions. Count checks do not establish natural conversational diversity or semantic validity.

## Accounting and interpretation

No new student calls, optimizer updates, active student time or input positions. Carry-forward remains 5,636 updates, 24,847,840 positions and 1,732.4593 active seconds. The historical successor ledger and frozen campaign files were checked unchanged. Authoring/review agent usage is estimated rather than platform-metered; the 6M-token review ceiling cannot be certified from exact billing telemetry. No external teacher API was called. This accounting gap is not silently treated as a launch pass.

The campaign's explicit rule is: after the single prelaunch repair, if admission still fails, terminate preparation. Accordingly, G0 is closed as unsuccessful, not left running for another automatic adjustment. The current blocked recovery branch is not bypassed by assuming the unmeasured foundation will pass G1.

The next owner decision is whether to authorize a **new data-acquisition preparation version** under unchanged acceptance thresholds, or change project constraints. A sensible new version would source genuinely everyday standalone prose with provenance and margin above the supply floor, then complete semantic review and overlap/scorer checks before any model work. It must not reuse the exposed draft development set as an unseen final set or describe this unsuccessful preparation as launch-ready. No new campaign or acquisition is initiated here.
