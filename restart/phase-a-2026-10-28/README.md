# Phase A — preparation and inference reassessment

Status: **prepared, inference and blinded agent review complete; benchmark gaps remain, no training release**.

Update 29 October: [review adjudication](REVIEW_ADJUDICATION.md) records 20/24 agreement and revised grades of 13 Accept, 2 Borderline, 9 Fail. This separate model-agent review is not human validation.

Read the [reassessment](REASSESSMENT.md), [acceptance contract](CONTRACT.md), [data card](DATA_CARD.md) and [verification receipt](receipt.json). For independent grading, open the [blind packet](BLIND_REVIEW.md) before the labelled [acceptance examples](ACCEPTANCE_EXAMPLES.md).

- 24 acceptance anchors: 12 acceptable, 6 borderline, 6 failed.
- Two matched curricula of 3,200 conversations each; eight balanced prerequisite tasks.
- 1,024-case fact × wording matrix and 256 counterfactual cases (128 pairs).
- 76,424 mechanical assertions passed on the revised candidate data.
- 832 inference responses; 332,898 model positions; 53.35 active model seconds; zero optimizer updates.
- Four source checkpoints and 24 unique frozen input files verified unchanged. Neither historical nor prospective final-test cases were used for model inference.

Use `private/prepared-v2/` for candidate curriculum preparation. Its [manifest](prepared-v2-freeze.json) records candidate provenance, not training authorization. Original v1 data and the two scored probe packets remain frozen. The 240 natural final candidates need broader dialogue frames and independent review; their worst-case generated-history context does not universally fit the current contract.

Code: `build.py` / `natural.py` build the original candidate; `prepare_v2.py` adds shared multiattribute worlds; `checks_v2.py` and `supplemental_checks.py` validate preparation. `infer.py` and `followup.py` are completed inference-only runs and must not be rerun casually. The cumulative ledger is `followup-ledger.json`; previous budget events are preserved.

Next: apply the review adjudication, validate the wording taxonomy, broaden natural cases with real return-to-earlier-state questions, and settle context headroom. Then reassess the bounded diversity/replay experiment and its backward-pass budget before any training.
