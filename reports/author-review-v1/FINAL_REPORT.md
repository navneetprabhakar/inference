# Author-only corpus review — final report

## Outcome

- Immutable source verified: 2,500 records, SHA-256 `f4e2fdc22bd92ea083cc2b97f4684315681306186802855ca996fdc468081c7b`.
- Codex CLI assistant review ledger validated record-by-record: 870 keep, 1,475 repair, 155 exclude, 0 unreviewed.
- The 24 earlier sampled records were rechecked: 7 keep, 15 repair, 2 exclude.
- Derived candidate: 2,345 records, SHA-256 `3c30fc0934544dfa929e3ed3aafc30a7fa6cfd45bc746c42f353689110a3b6ac`.

The reviewer was the externally selected `gpt-5.6-terra` Codex CLI invocation. This is assistant review, not independent human review or independently server-attested model provenance. The old `state_5.sqlite` message was an unnecessary nested-CLI initialization check, not a blocker for this invocation.

## Validation

- Immutable-source checks pass, but they do not validate edited repair messages.
- Candidate-level tokenization now uses the actual student tokenizer for all 2,345 retained rows, including all 1,475 repairs. It found one context overflow: `local-author-v1-02099` is 961 tokens; its final EOS and role mask are otherwise correct. This blocks a pass gate until an evidence-preserving disposition is made.
- Ledger/source identity passes, but the repair-preservation audit found one repair that changed, removed, or reordered a user turn. It is a gate blocker; no automatic rewrite was made.
- Source/ledger identity is audited, but explicit source dataset/license labels are absent on many local-author records. The audit reports this provenance gap rather than fabricating labels.
- A separate v3 assistant-authored (not independent benchmark) suite contains 120 development and 120 frozen confirmation cases. The legacy 12-case confirmation suite remains untouched and uninspected. V3 confirmation is not used for selection.

Tool scoring requires the full ordered call sequence, exact tool name, exact argument object, executable fixture completion, and exact final answer. Prose scoring uses predeclared factual/constraint/continuity rubrics and separately records repetition, output length, and stop reason, avoiding reference-length truncation scoring.

## Development-only decoding comparison

The frozen artifact exists and matches `93bb235b29c8bdff5efe4e14bac223b92b5bc70fecc3023a22d8ed2d9b6fd781`. The prepared comparison is baseline penalty 1.2 versus prose-only penalty 1.3, with tool decoding unchanged at 1.2. It uses development only and never reads confirmation.

It **completed once** on the authorized parent host, using development only; confirmation remained unopened. Manual semantic review found prose 2 pass / 9 partial / 77 fail at 1.2 and 2 / 8 / 78 at prose-only 1.3; machine diagnostic 7/88 is not semantic accuracy. Tool outputs are identical between arms apart from timing: strict full success is 1/32, semantic passes 2/32. Prose repetition improved from 11.75% to 4.56% and cap hits 20 to 15, but correctness remains unacceptable. See `reports/author-review-v1/development-decoding-v2/OUTPUT_REVIEW.md`.

## Limits and stop condition

The review projection is not approved for training or inference selection. No training, cloud compute, paid API, dependency change, source-corpus alteration, STOP-file removal, commit, or push occurred. Stop here for parent-host gate review.
