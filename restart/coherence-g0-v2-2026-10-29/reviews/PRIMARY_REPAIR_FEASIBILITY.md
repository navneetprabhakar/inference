# Primary API acquisition: feasible candidate path, conditional admission

**A new primary-content capture is technically feasible. Attaching current owners to archived flattened text is not a sound repair.** The archive should remain quarantined. Primary response bytes, component IDs, owners and component licenses can bind newly fetched text to its current provenance; they cannot retroactively establish the authorship of different archived revisions.

## Bounded API probe

The API documents optional nested [answers and comments on questions](https://api.stackexchange.com/docs/types/question), [comments on answers](https://api.stackexchange.com/docs/types/answer), and component `content_license`/`owner` fields. [Revision objects](https://api.stackexchange.com/docs/types/revision) include revision GUID, user, timestamp, body and content license; [post revision requests](https://api.stackexchange.com/docs/revisions-by-ids) accept up to 100 post IDs, with pagination still required.

Created one explicit read filter and fetched three already-identified exclusive-4.0 question threads plus the revisions for their nine questions/answers. The probe returned all six expected answers and matching reported comment counts; this does not guarantee completeness for larger threads. Answers and comments had licenses. Question `content_license` was absent in these custom-filter responses even though explicitly included; the gate must reject missing license fields or obtain matching licensed revision evidence, never infer a license merely from creation date. Root's separate `withbody` question responses do carry the field, so use the actual returned values.

The nine-post revision query returned 14 events: 13 licensed content revisions and one unlicensed vote event without body. The latter is not itself missing licensed prose. One edited question revision had no stable user ID; preserve any available display attribution and document unresolved contributors. Do not fabricate IDs or treat every non-content moderation event as an author. Evidence is in `evidence/repair-*.json`.

## Root's new primary.py design

Reviewed `acquisition/primary.py` while acquisition was running. It collects current questions and their accepted answers as candidates, excludes comments, keeps raw API responses and hashes, and requires CC-BY-SA-4.0 and owner display name/link for both components. This avoids the archive's broken author mapping and mixed-thread license problem. Explicit question/answer labels avoid pretending two voices are a continuous author. Accepted answers are selection signals, not factual validation.

At inspection time three completed pair files contained 1,473 pairs. None had a mismatched accepted-answer or question binding; all carried bodies and licenses. However 1,202 question components and 771 answer components had edit timestamps, and **none exposed `last_editor` in the captured response**. Only 176 pairs had neither component marked edited. This is an intermediate snapshot, not final supply or admission counts.

Before admission:

1. Enforce the binding checks in code: answer ID equals the question's accepted-answer ID; answer.question_id equals question.question_id; site agrees. Retain component bodies, source URLs, owner identity, current license, acquisition time and hashes. Normalize/preserve transformation notices when rendering HTML to prose.
2. Resolve contributor provenance for edited components. Current owner identifies the submitter, not necessarily every contributor to current text. Fetch and retain relevant licensed content revision contributors and revision IDs, or prospectively restrict candidates to an independently justified unedited subset. A missing `last_edit_date` alone is a useful filter, not exhaustive proof that no grace-period or deleted contribution exists. Do not claim complete historical attribution solely from the current owner field. Whether linking revision history satisfies a particular legal attribution obligation is outside this technical review.
3. Reject unresolved missing owner/license/body/binding cases. Respect incomplete pagination and missing/deleted posts; no silent assumption that requested IDs all returned. License equality should remain fail-closed. Excluding comments is allowed for this new primary unit because their text is also excluded; it is not a way to relabel a flattened archived thread.
4. Preserve same-question/source-family splits; apply extraction and domain audits and all fixed token floors after filtering. Do not count technical capture success as provenance admission or corpus sufficiency.

Two execution-limit defects were reported immediately to root: `sleep(min(backoff,60))` does not honor longer server backoff; respect the entire instructed interval, using interruptible/chunked waits if needed. The total-byte guard tests current usage before a request without reserving its maximum response, so it can overshoot the stated cap; reserve before each request and account failed/error response bytes. The [API throttle documentation](https://api.stackexchange.com/docs/throttle) requires honoring the returned backoff. These are acquisition-control issues separate from license eligibility.

## Direct answer on source-link-only attribution

**Archived text plus a canonical current question URL alone does not meet the existing evidence requirement after a demonstrated mapping failure.** The URL helps identify a thread, but cannot identify which question/answer/comment revisions contributed the archived bytes, their authors, or each component's license. Adding current owners without exact text/revision alignment would falsely imply repaired provenance. Do not weaken this to meet a supply target.

A bounded raw-dump reconstruction could in principle recover original component IDs, ContentLicense, PostHistory.UserId and Users identities, but it requires the matching dump and verifiable correspondence to the archived extraction. No matching dump download or size feasibility was established here. Prefer an independently admitted new primary capture when feasible; do not describe that replacement as repaired attribution of the archive.

This addendum authorizes nothing, admits no tokens, and offers no legal certification. No final benchmark or model weights were accessed. The diagnostic probe used three small API operations after initial review (filter creation, three threads, nine-post revisions), with no mass acquisition by this reviewer. The root's broader acquisition is separately budgeted.
