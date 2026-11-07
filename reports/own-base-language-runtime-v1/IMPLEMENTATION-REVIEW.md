# Torch continuation implementation ready for root review

New code only; no production activation/spec or training launch. Frozen base/optimizer/SFT runtimes and protected artifacts are unchanged. This is the Torch fallback path; it does not imply MLX migration.

## Implemented

- `own_base_language_data.py`: compact deterministic mixed-source row schedule, finite explicit passes, exact source-position unique/repeat counts, atomic update proposals, independently reconstructable cursors and variable-length validation manifests/aggregates.
- `own_base_language_streams.py`: read-only memory maps and document-span assembly from a new canonical packed-manifest contract. It requires actual final training admission, independently checked packed tokens/exclusion absence, root quality policy and exact underlying custody pins. It verifies file hashes/vocabulary, EOTs, contiguous nonoverlapping indexes, cross-source family/text split separation and original candidate-ID exclusions. No packing or source repair.
- `own_base_language_control.py`: narrow derived campaign controller, preserving accepted checkpoint/rollback/reservation behavior with newly explicit finite goals/attempt/evaluation/active/calendar limits. No inheritance of the old100M/36h maximum. Training and evaluation attempts remain charged across interruption; budget exhaustion before the committed goal is not completion.
- `own_base_language_continue.py`: full selected-parent weights/moments/steps/groups/RNG restoration; same8192target update, constant explicitly declared LR, single clipping/AdamW step, target-normalized accumulation, full state checkpoint/resume, source-stratified FP32held-out evaluation and confirmed regression handling. Production accepts existing124Marchitecture and exact GPT2assets; a larger model needs a separate reviewed path.
- `own_base_language_launch.py`: one explicit lease per invocation, inherited watchdog ticket, heartbeat/deadline/owned-child termination, checksum-bound outer wall accounting and original calendar deadline. Supervisor reserves the whole lease before spawning; parent crash leaves that conservative charge. Reaped workers settle actual elapsed wall. No automatic restart or implicit deadline refresh.

## Actual receipt adapters

Custody originals retain their real states: legacy language `cleared`; public language/Cosmopedia `screened_not_admitted`; narrative `PASS_projection_root_custody_union_bound_not_admitted`. A combined Cosmopedia receipt covers both scopes. Narrative binds the actual underlying legacy/public/projection/quality receipts and unions exclusions; no fabricated PASS wrapper or duplicate custody run is required. A metadata-only check of the real narrative receipts passed and produced1,585union exclusion IDs without opening private cases or admitting data.

The production hardware adapter accepts the actual completed optimizer-screen report for its512/B2/accum8/TorchBF16workload, then the existing parent verifier validates those report/endpoint receipts. It does not demand a made-up hardware PASS record.1024remains ineligible until a separately reviewed actual-evidence adapter is added. Short sequential MLX parity does not establish a Torch1024or productionMLXhardware admission.

The packed-manifest/admission contract is new, but must describe real existing candidate/quality/custody/packing evidence. It is not permissible to generate affirmative placeholders to satisfy the loader. Root's pending narrative/explanatory packers need a metadata adapter plus independent verification into this contract before a production spec exists.

## Exact external behavior gate

Source CE is not conversation/context coverage. Production specification must pin an external evaluator protocol with the unchanged `original-web-256`, `context-pairs-32`, and `raw-continuations-32` series and explicit attempted-target/active/calendar budgets. At baseline and every source-evaluation milestone, the trainer saves its accepted checkpoint and writes `milestone-T-request.json`, binding that checkpoint receipt and external protocol. It enters `paused-milestone` before further updates or final completion.

A root-owned evaluator runs separately against that pinned committed checkpoint, preserves raw outputs and its own accounting receipts, and root writes `milestone-T-decision.json` with:

- state `root_reviewed_external_milestone`;
- decision `continue` or `stop`;
- exact request SHA and protocol SHA;
- `result_receipts` as exact absolute path/SHA pins to real evaluation artifacts.

The trainer verifies all pins and immutable request contents before continuing. It does not interpret evaluator score schemas or manufacture judgments; root reviews the raw transfer results under the frozen protocol. Missing review pauses; an altered request/checkpoint fails closed. Explicit resume is required, and the original campaign/calendar/attempt budgets remain. External evaluation is independently budgeted; its time is not misreported as optimizer throughput.

## CPU evidence

-9data-helper tests, including brute-force exposure equivalence over multiple passes.
-10trainer/control tests: full moment/RNG load; uninterrupted versus interrupted/resumed parameter, moment, cursor, RNG and evaluation-history equality; inflight reservation nonrefund; exhausted attempts not success; evaluation replay charges; immutable-budget/STOP/tamper rejection; failed checkpoint publication retains accepted checkpoint; exact baseline/endpoint external gates.
-4stream tests: separate/combined actual custody schema shapes; row assembly; token hash corruption; missing scopes; candidate mismatch; excluded original IDs and malformed ranges even after fresh fixture pins; unadmitted refusal; original receipts not rewritten.
-3watchdog tests: original-calendar/remaining-lease arithmetic, checksum/tamper rejection, and actual owned nonreturning subprocess termination. This exercises tiny CPU fixtures, not GPU work.

## Remaining before production

Root code review, real canonical stream/admission adapters and independent proofs, actual finite exposure/mixture/pass/time/evaluation allocations, a frozen external-transfer protocol/evaluator invocation, final runtime/environment pins and a concrete reviewed launch spec. No default budget, selected corpus yield, quality pass or useful-model ETA is implied. Production GPU resume and resource behavior have not been exercised by these CPU fixtures.

Canonical projection proof now uses the explicit `PASS_canonical_manifest_projection` state with underlying packing proof/manifest pins and mapping_scope. The reader checks actual original narrative/explanatory proof states and their manifest hash bindings; it does not relabel projection as independent retokenization.
