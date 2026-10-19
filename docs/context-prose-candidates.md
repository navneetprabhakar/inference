# Context prose candidates

Creator: Navneet Prabhakar

## Purpose

Build a source-bound foundation-data candidate from the supplied reference passages in Dolly. The first delegated review found unreliable answer targets; this derivative excludes every question and answer and keeps only the exact context substring. It does not repair or fact-check a reference passage, establish conversation capability, or admit training data.

## Frozen extraction

`configs/context-prose-candidate-v1.json` is fixed before inspecting extraction yields. The parent manifest is pinned. A row must have exactly one `\n\nContext:\n` delimiter in a two-message conversation, a canonical unchanged reference substring, 80–2,000 words, at least 95% Latin letters, at least five distinct common English function words, and at most one URL. Conservative topic, visible privacy-pattern, markup/navigation and repeated-line attention flags exclude the whole passage. These are research eligibility proxies, not calibrated language/privacy/SFW classifiers. Excluded topics are not a global content prohibition. No target is rewritten, translated, truncated or generated.

Each derived row records its original example/record hash, exact substring offset/hash, policy hash, original split group and inherited partition. Language/content/quality/privacy remain unreviewed. The inherited local split becomes a minimum partition constraint during new grouping; it is not asserted to be a publisher-provided split. Original source/license provenance and attribution remain attached.

## Grouping and audit

Extraction can turn different conversations into the same prose passage. Consequently the derivative runs through exact/near grouping again with all original frozen heldouts present. Heldout precedence is preserved both by inherited partition and new syntactic grouping. Original frozen conversations remain heldout reference records and are never foundation candidates. Global semantic contamination freedom is not established.

The pinned offline language/quality audit then scores complete message windows and samples whole groups. Scores do not automatically approve the candidate population. The training reader must continue refusing this sample-only artifact. Actual measurements and next admission boundary are recorded in [milestone thirty-eight](milestone-thirty-eight.md).

## Local reproduction

```sh
.venv/bin/python scripts/prepare-context-prose.py
```

Requires the existing hash-pinned complete-source snapshot and offline detector. Publishes only into a new `data/context-prose-candidates-v1` output; existing artifacts are refused rather than overwritten. No downloads, teacher calls, model updates or cloud launches. Root-extraction and grouping have their own retained artifacts. A failed attempt must be inspected before any separately named retry; do not restart merely because a process observation timed out.
