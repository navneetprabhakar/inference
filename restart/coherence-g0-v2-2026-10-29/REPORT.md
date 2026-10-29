# G0 preparation v2: stop before further review

**Not launch-ready. No student inference or training ran.** User authorized new data-acquisition preparation with unchanged acceptance thresholds, then delegated choosing a conservative review-accounting method. That did not increase the inherited6M-token ceiling.

## Accounting correction and stop

Local Codex session `token_count` events were discovered during this phase. They report14,895,730 input-plus-output tokens for the three G0 agents alone, including previous G0 work and this version. Cached input is included because the contract caps total input/output tokens. Root usage is excluded, so this is a lower bound, not a complete total. The logs contain164 usage events, but we have not certified that these equal164 distinct billable requests. The token ceiling is conclusively exceeded regardless.

Earlier manual estimates were inadequate: they counted visible payload more closely than repeated context. The previous claim that usage telemetry was unavailable is superseded by `review-usage-audit.json`. No final payload content was exposed by the audit; only session metadata and token counters were inspected. Further model review stops. This is an accounting failure in execution, not a model capability result. Any continuation requires an explicit additional budget with log-based preflight reservations; do not reinterpret the old ceiling as excluding cached tokens.

## Work preserved

- Independent complete review of60 continuation prompts,120 grounded choices and240 controls,60 grammar contrasts,120 development conversations/385turns. Two choices have multiple valid answers; seven development references are defective. Native continuation prompts and grammar contrasts passed the review's bounded scope. No old frozen files were edited. Details: `reviews/benchmark-semantic-review.json`.
- New source research found practical GitLab and Wikivoyage leads, but their usable volume is unproven. No admission claim.
- Downloaded ten pinned CommonPile StackExchange shards under the512MiB acquisition limit. Independent source audit reproduced an author-ID mapping defect. Those archives are quarantined, not training inputs. Details: `reviews/SOURCE_PROVENANCE_REVIEW.md`.
- Replaced that approach with new primary StackExchange API captures:2,722 question/accepted-answer pairs with component owner/license fields. The fixed extraction/domain filter retained1,293 candidates/768,143 native tokens before complete revision checks. No comments were included; explicit question/answer labels were added.
- Captured contributor/revision histories under the shared180-request/120MB cap.179 requests, including one interrupted request, were recorded.398 candidates/214,929 native tokens passed the implemented provenance checks.252 were held for revision license/contributor gaps and643 for current-body/revision mismatch. Those mismatches remain unresolved; no silent normalization or waiver. This is candidate volume before splitting, deduplication and semantic review, **not admitted supply**.
- Backoff handling, request-byte reservation and question/answer binding checks were corrected during acquisition. Raw response receipts and transformations are preserved. Source API work completed before the review-budget stop; no job remains running.

## Remaining work and next decision

Broad training admission remains zero. The frozen100-document semantic audit, full6400-conversation first review and20% second review, collected benchmark repairs, cross-set overlap clearance, replay admission and launch feasibility remain unfinished. The final candidate remains unsealed and was not opened by the parent.

The next decision is a separately approved additional review budget, carrying this overrun visibly forward. A reasonable bounded proposal is **up to4M additional total input/output tokens**, counted from explicit session-counter baselines with cached context included and reserved before every agent batch; no training authority. Use fresh narrowly scoped reviewers to avoid repeatedly resending long histories. Stop on any unresolved admission failure or exhaustion. Before spending it, reconcile root G0 usage and replace heuristic reviewer estimates with the local counters. This is a proposal, not authorization.

Prior student carry-forward remains5,636updates,24,847,840positions and1,732.4593active seconds. No student budget was reset or consumed.
