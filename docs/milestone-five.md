# Bootstrap review and training release contract

Creator: Navneet Prabhakar

Date: 18 October 2026

## Result

A manual bootstrap review path now connects immutable audit snapshots to checked canonical training records. This is a foundation for small reviewed batches; it is not the eventual production-scale source approval or automated quality system.

- Deterministic review packets contain full examples, source records, record hashes and the parent dataset manifest hash. Selection rotates through source/partition buckets.
- Generated decisions are pending. Reviewer identity is blank and human attestation is false. Preparation never approves a source or example.
- Publication requires explicit source terms/category decisions, per-example English/privacy/quality decisions, content category, upstream partition and partition evidence. The named reviewer must be Navneet Prabhakar.
- The packet must match the exact input snapshot. Content, source revision, license provenance, family identity and original partition cannot be edited as part of approval; corrections require a separately derived example and future lineage handling.
- Original held-outs cannot become training records. A reviewed upstream test/validation assignment protects its entire existing split group, even when that reviewed item is rejected.
- A published release keeps original source provenance immutable and stores review evidence separately. It annotates approved records with English/content labels and review hashes, then publishes through temporary-directory rename. Existing outputs are refused and interrupted publication is cleaned up.
- `training_examples(path)` verifies checksums and reconstructs the expected approved records from review evidence before yielding **only train records**. It never yields review-packet text or validation/test shards and rejects sample-only snapshots.
- These checks establish integrity and explicit attestations. They cannot establish whether someone actually performed a review, prove an annotation correct, or settle licensing obligations. Review files are not cryptographic signatures.

## Actual state

The public-data packet is `data/reviews/bootstrap-review.json`: 40 examples, four source reviews, **zero approvals**. It is bound to the 901-example audit snapshot. Both an attempted unreviewed publication and attempted sample-only training read were refused, without creating a release. No public-data training, teacher calls or new cloud spending occurred.

The packet contains full, potentially sensitive/unreviewed text and evaluation examples. It stays outside Git and must not be used wholesale as tokenizer input or teacher training-data prompts. Only a verified approved train iterator may feed future production consumers.

Tests use synthetic fixture source records and synthetic review decisions. They do not constitute public-source clearance or human review. Full suite: **63 passed, 2 CUDA checks skipped locally**. Evidence: `reports/milestone-five-tests.xml` and `reports/milestone-five-review-gates.json`.

## Use

Create a fresh pending packet:

```sh
.venv/bin/python -m slm.data.review prepare --dataset data/audit-offline-final/curated --output data/reviews/new-review.json --limit 40
```

Review the full records and source evidence. In `source_reviews`, supply source decisions, terms review, allowed categories and an evidence note. In each example's `decision`, approve/reject/preserve pending status; approved records also require verified English/privacy/quality, content category, upstream partition and evidence. Leave unsupported or unresolved cases pending/rejected. Do not edit `record`, its hash, source records or the dataset manifest hash. Set reviewer identity and human attestation only after the actual review.

After a completed review, publish to a new directory:

```sh
.venv/bin/python -m slm.data.review release --dataset data/audit-offline-final/curated --review data/reviews/new-review.json --output data/reviewed/bootstrap
```

Consume approved training records through the checked reader:

```python
from slm.data.review import training_examples
for example in training_examples('data/reviewed/bootstrap'):
    messages = example['messages']
```

A release may contain only approved held-out records; the training iterator then yields nothing. Future tokenizer/training entry points must reject an empty training stream. They must use this checked path or an equally verified future bulk-release contract, rather than globbing every JSONL file or flipping manifest flags.

## Remaining work

- Actual human review and source/category decisions; no approvals have been inferred.
- Upstream official partition mapping, particularly for OASST complete-tree exports. A human-supplied partition field is a bootstrap attestation, not an automated upstream mapping implementation.
- Calibrated English, privacy and quality detectors; audited false-rejection rates for informal language.
- Production-scale releases using automated evidence plus stratified human audits. This manual per-record bootstrap path is not a requirement to hand-review every future corpus record.
- Reviewed corrections/derivations, production tokenizer candidates, token inventories and masks, and training integration.
- Independent full-size numerical and memory checks can proceed while review is pending; no public-data training should start from the current sample-only snapshot.
