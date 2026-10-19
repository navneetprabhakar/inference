# Evaluation isolation and bounded intake implementation

Creator: Navneet Prabhakar

Date: 19 October 2026

Subsequent implementation: [the completed bounded candidate intake](cosmopedia-candidate-intake.md) publishes49,000 actual rows. The metadata-only results and next-step statements below describe this prerequisite milestone.

## Completed

- **Expanded exclusions:**364 distinct normalized requests and119 actual generated replies,483 distinct texts from1,851 source records. Sources include the original500-case/seven-tool fixtures, four earlier actual interviews, the100-conversation protocol/transcript,48 fresh-session diagnostic responses, and30 same-prompt branch-comparison generations.
- `configs/future-intake-evaluation-exclusions-v1.json` pins the portable inventory by an external hash. `EvaluationExclusions` checks original prompt and body, returns typed matches and preserves payload hashes. It refuses changed files, symlinks, invalid entries and missing/nontext fields. No old190-request fallback is acceptable for the next intake.
- Full normalized text sequences are matched despite case/punctuation/whitespace variation. This does not detect arbitrary paraphrases, partial excerpts or unseen task-family variants. Short canonical labels such as0/blue are not globally banned; complete requests protect their contexts. Some generated replies reproduce training text, so the inventory is a conservative future exclusion, not retrospective independence proof.
- Every registered source record matches its entry. All1,176 retained raw source records are independently rescanned:1,048 FineWeb,64 Cosmopedia,64 Wikipedia; zero exact exclusion hits. This is only the retained finite population and does not establish corpus admission or statistical independence.
- The first private build omitted the48 earlier fresh-session replies. Before further candidate intake, v2 corrects coverage and preserves v1's source/plan/output privately. The final committed build plan is `configs/evaluation-exclusions-build-v2.json`; no old result is silently reattributed.

## Durable accounting

- `IntakeLedger` commits request/body/row/output reservations before work through synchronous SQLite transactions. Pending and failed charges persist; success does not refund the conservative reservation. Duplicate operation keys refuse automatic replay.
- The exact contract, resolved job path and original deadline survive reopen. A lost database/job identity cannot silently create a new allowance; concurrent owners are refused. Mutating the caller's contract does not enlarge stored limits.
- These are **per-job global counters**, not authorization for another job or an all-project spending ledger. New jobs must explicitly preserve relevant prior accounting. Disk/RSS enforcement and the process supervisor belong to the caller; protocol headers and redirect hops are outside response-body counters.
- The metadata runner uses a separate parent-process timeout, so a worker blocked in a request does not depend on polling its own clock. This demonstrates the mechanism for the probe; the full50K-job lifecycle/resume/cache integration remains unimplemented.

## Actual pinned metadata result

- A fresh revision-pinned API inventory contains104 Cosmopedia-v2 Parquet files. The existing fixed hash priority chooses `cosmopedia-v2/train-00022-of-00104.parquet`, size1,175,277,891 bytes. No whole shard is downloaded.
- Four actual requests transfer**3,005,408 body bytes**. Conservative precharges are3,233,339 body bytes, including the inventory's maximum body allowance and one possible overread byte per request. Every request completes; source/plan/retained-byte hashes reconcile with the persistent database.
- The retained footer describes376,289 rows across377 groups:376 groups of1,000 and one of289. All377 fit the unchanged declared row/compressed/decoded metadata bounds. The fixed hash selection chooses group227:1,000 rows,3,135,099 compressed interval bytes,5,403,136 declared decoded bytes.
- This is compatibility evidence for **one file**, not the remaining103. Actual Arrow size, schema/content and language still need checking when decoding. **Zero data rows are decoded** in this probe; metadata compatibility is not training eligibility.

## Verification and next work

- **41 focused tests pass:**13 existing range-reader,10 existing prose-screen,10 new exclusion and8 new ledger checks. The earlier20-test receipt overlaps and is not added to41.
- Actual checking reopens all retained sources, matches every interview/diagnostic output, rescans1,176 raw records, tests request/response injection in prompt/body, reconciles four request charges and reconstructs377 groups from retained metadata. No network or model-generation replay is used for that check.
- Evidence: `reports/evaluation-exclusions-actual.json`, `reports/cosmopedia-intake-metadata.json`, `reports/intake-isolation-and-metadata-check.json`, and the41-test receipt. Private artifacts retain the full inventories, scans, byte ranges and SQLite records.
- Next implement the complete finite intake worker: durable cache/recovery, all selected-file metadata checks, row/output/work accounting, independent deadline, exact seed extraction, original prompt/body exclusion, language/privacy screening and ancestral heldout/near-overlap controls. Freeze the actual whole-job contract before bulk execution; do not restart/reset this probe or silently expand its caps.
- The previous source policies and frozen numerical/training implementations are unchanged. No corpus admission, gradient, teacher call, paid resource or cloud spend occurs. The model remains an inadequate conversational baseline and the full project remains incomplete.
