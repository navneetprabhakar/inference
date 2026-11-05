# Learned slot-dialogue acts

**The second CPU classifier passed its internal selective-classification gates.** It has **36,118 learned coefficients** across two softmax heads. One proposes an initial calculator operation or conversion. The other distinguishes supplying a missing argument, revising a previous argument, cancelling the request and changing subjects. It does not parse operands, grant permission, execute tools, or select a product release.

| Form-held-out test | Accepted correct / accepted | Precision | Accepted / total | Coverage |
|---|---:|---:|---:|---:|
| V1 opener | 91 / 91 | 100% | 91 / 200 | 45.5% |
| V1 pending act | 32 / 43 | 74.4% | 43 / 110 | 39.1% |
| V2 opener | 79 / 79 | 100% | 79 / 142 | 55.6% |
| V2 pending act | 68 / 74 | 91.9% | 74 / 104 | 71.2% |

V1 and V2 use separate form-held-out tests. Their rates should not be interpreted as a head-to-head estimate on one dataset. Each V2 class has eight distinct challenge forms. The form-weighted V2 precision/coverage figures are 100%/60.4% for opening and 96%/78.1% for pending turns. Both modes had to exceed 80% precision and 45% coverage under both weighting methods. The V1 coverage and precision shortfalls prevented promotion.

## Behavior and scope

The public API is `slot_dialogue_head.classify(text, pending=False)`. Low confidence, small class margin, or low known-token fraction returns `None`. A confident opener `none` also returns `None`, while a confident pending `unrelated` remains explicit for the host. `model_size()` loads verified fitted tensors and returns their total scalar count. Missing or corrupt model/evaluation/protocol pins fail closed. The host remains responsible for call authorization, session state, argument parsing and validation.

The V2 trainer separates role-informing pending-language features from a lower-weight channel encoding slot presence, local normalized context and slot shape. Training examples were weighted equally across acts and across forms within each act. No reference model or service supplied labels. All original utterances, hash receipts, excluded indices and thresholds are preserved in these reports.

Of 38 held-out revisions, the model accepted 21 and identified 15 correctly. All six accepted errors were variants of “Use [new value] in place of [old value],” which the classifier treated as supplying a value. It abstained on many ordinary opening requests, including a brief addition paraphrase in startup smoke. Reported held-out precision is conditional on acceptance and cannot guarantee safe action in the host.

## Provenance and files

- V1 source SHA-256 `1e06c5d1f3781145a25b7d5ea82390758335b376544d693049b5c9694320cf98`; 12 training-side indices removed after protected-set screening. It retains the failed result and 26,176-coefficient experimental fit. The second stage uses its allowed training forms but never its held-out examples as supervision.
- V2 source SHA-256 `a910118a7b7b048b3e77d1622887d5e1a06a59259152217e7daf5cbd6df1d4d4`; all 1,009 new rows passed both custodian text screens. The resulting training pool comprises 1,024 opening and 1,034 pending rows after duplicate removal. Openings and pending acts have separate nonoverlapping training and test language forms. This is a small authored test and does not establish external product accuracy.
- The V2 accepted weight hash is `707d1ffef0d52681921d51c8fc16aece042cfb84ed515ca91bd2604c2abe4970`. `v2/accepted-pin.json` binds the artifact to the immutable protocol and evaluation hashes. Each fit used one CPU thread and completed in under a second. No GPU, paid service or external product test was used in fitting.
