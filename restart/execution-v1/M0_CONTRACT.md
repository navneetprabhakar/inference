# M0 scope and evaluation contract — execution v1

Owner: Navneet Prabhakar. Authorization: “ok start with M0-M3”.
This contract implements the roadmap; it does not declare evaluations passed.

## Product boundary

One fresh English base and separate CHAT/TOOL descendants, total deployed learned parameters <=100,000,000. No imported pretrained weights or larger fallback. Everyday adult English, informal and neutral professional registers; British and American spelling accepted. Short grounded explanations, corrections, clarification, uncertainty, reference tracking across eight turns, and bounded tool workflows. Unsupported claims and false success acknowledgments fail even when fluent.

Base training context 2,048 positions; conversation/tool target 4,096 positions including schemas and history. Reserve up to 512 output positions. Overflow is an explicit error or user-visible context reduction with provenance; never silently discard required instructions, arguments or facts. Context extension requires training/evaluation evidence. The M1 prototype remains 512 positions and cannot establish the final context claim.

Initial local deployment performance targets (frozen before measurement): concurrency one; 512-token prompt and 128-token output, first token <=5 seconds and generation >=10 tokens/second; 3,584-token prompt plus 512-token output, first token <=30 seconds; peak process-tree RSS <=16 GiB. Measure median and p95 over 30 runs after five warmups, both cold/warm separately. These are proposed engineering acceptance targets, not measured performance. A failure triggers an explicit hardware/scope decision.

## Capability-to-evidence map

| Capability | Acceptance evidence | Authority |
|---|---|---|
| English grammar, coherence, grounding, relations, paraphrase | All exact task counts/subtype floors, controls and loss baselines in ENGLISH_GATE.md | M4; all rows required |
| Eight-turn conversation | 100 conversations, 800 turns, >=600 correct; >=112/160 per category; >=40 fully correct conversations | M5 |
| Correct internal tool use | 500 tasks, >=450 correct; >=85/100 per category; >=98/100 no-call/clarify; >=99.5% valid raw calls, >=200 calls | M6 |
| Correct arguments | >=95% required call/argument decisions, missing and extra calls scored | M6 |
| Dynamic MCP schemas/workflows | 500 tasks, >=90%; >=85% each server/category; heldout 200 tasks >=85%; paired adapter gap <=2 points | M7 |
| Injection/fault containment | 200 independently partitioned attack/fault cases, zero unauthorized effects/canary leaks; unsafe proposals reported | M7 |
| Operational multi-turn stability | 1,000 scripted sessions, >=90% completion, zero unauthorized actions/leaks/unbounded loops | M8 |

M1 has its own narrower research gate in approval-v1/PLAN.md, including baseline comparisons, 200 grammar pairs, 100 grounded items, 100 continuations and 100+100 copying probes. Its pass never substitutes for the product rows above.

## Tool catalogue and authority

All tools are local sandbox fixtures until separate production access authorization. Each exposes a JSON schema; additional properties rejected, bounded strings/arrays, no implicit argument coercion. Tool results carry call ID, status, provenance and bounded content.

| Tool | Input intent | Effect and oracle |
|---|---|---|
| calculator.evaluate | bounded arithmetic expression | deterministic decimal result; no eval/code/imports |
| clock.now | permitted time zone | read only, injected fixture clock in tests |
| documents.read | opaque approved document ID | read only; IDs map into a fixed corpus, no arbitrary paths |
| documents.search | bounded query and limit | deterministic corpus index; citations to matching IDs |
| records.lookup | dataset enum and record ID | read only fixture lookup; absent IDs explicitly missing |
| notes.create | text, operation ID | sandbox write; receipt and idempotency key |
| notes.read | note ID | sandbox read |
| notes.update | ID, expected version, text, operation ID | compare-and-swap sandbox write |
| notes.delete | ID, expected version, operation ID | sandbox deletion; requires task-authorized target |

At least three MCP test servers group compute/clock, documents/records and notes. The same fixtures execute through internal adapters for parity. No account credentials in model context. Tool descriptions/results cannot authorize new actions. A proposed call must be validated against a runtime-owned allowlist, exact target scope and side-effect policy before execution. Unknown completion of a write blocks retry until reconciliation.

Default <=5 tool calls/task, one transient read-only retry, <=30 seconds/call, <=120 seconds/task. Tests use fake clocks for deterministic timeout checks. No production effects, user messaging or network writes are included.

## Data and evaluation custody

Whole source-document, duplicate-connected component, conversation, template, teacher-seed and tool-workflow families stay in one split. Preserve every existing exclusion and upstream heldout partition. Known related schemas and renamed/paraphrased instances belong to the same workflow family. Acceptance schemas/workflows must include families absent from training and development.

Freeze gold labels, scoring, generation seeds, prompt bytes and normalization before candidate updates. Keep acceptance text out of training/tokenizer inputs and trainer process arguments. Trainer receives only allowlisted train/dev artifacts; an independent evaluator loads final tests once after checkpoint selection. Repository path separation alone is not OS isolation: custody tests must demonstrate trainer access refusal before launch.

New tests authored after viewing failures become development diagnostics, not fresh acceptance. Include all missing, malformed, truncated and timed-out outputs in denominators as failures. Record raw model proposals before validation/constrained decoding; report runtime saves separately.

Final subjective release grading requires two independent blinded human graders and adjudication; report kappa, and treat kappa <.6 as inconclusive. Graders have not been assigned. Assistant-only M1 scoring remains a research proxy and cannot certify release.

## Execution and deviations

The authorization receipt records M0–M3, with M1 restricted to its already specified local budget: <=48M actual targets, <=3 presentations, <=6,000 updates, <=36 active hours, <=72 elapsed hours including preparation; 2M/2-hour pilot and conditional gates. Start timestamp is recorded when preparation begins, not deferred to training to extend the allowance.

No paid API/cloud budget. Owner subsequently authorized up to 80 GB downloads. Count retries/metadata; all storage stays local with ceilings of 80 GB raw, 64 GB processed, 16 GB scratch, plus 16 GB reserved for weights/checkpoints and at least 20 GiB free (disk-budget.json). Local recovery remains authorized; paid/cloud budget remains zero. M3 measurements require frozen source/tokenizer and explicit short-probe budgets before allocation. No M4–M8 execution. Changes that exceed these limits require a recorded owner decision; implementation work within bounds proceeds without repeated permission requests.

Required run identity: experiment ID, parent checkpoint/null, source and tokenizer hashes, complete config, code/environment digest, seed, policy version, approval receipt, target counters, per-document exposure ledger and checkpoint checksums. Atomic checkpoint publication; persistent pre-work reservations charge interrupted work. Every terminal receipt is PASS, FAIL or INCONCLUSIVE with planned/actual counts, resources, raw evidence and unresolved requirements.

## Current acceptance status

Contract specified; NOT M0-complete. Remaining M0 evidence: materialized split/evaluation registry, training-process custody enforcement, concrete source/acquisition budget and M3 probe limits once inputs are available. Human grading arrangements remain a later release prerequisite. M1 controls and evaluation sets are under construction; no model initialization is permitted until their tests pass.
