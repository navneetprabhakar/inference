# Offline conversation teacher lifecycle

Creator: Navneet Prabhakar

Date: 18 October 2026

## Current transport update — 19 October 2026

This report preserves the historical API/offline milestone. The user subsequently authorized up to USD 1 for the proposed API pilot, then instructed “use codex cli, dont use API”. The API remains disabled. The active CLI-only workflow and first real demonstration are documented in [milestone twelve](milestone-twelve.md). Missing API keys are not a blocker for that path. CLI account usage is not an API-dollar budget; reviewed training use remains gated.

## Outcome

The teacher lifecycle now has a provider adapter, durable cache, conservative budget journal, versioned recipes, scenario lineage, structured/executable validators and a disabled live entry point. **No real teacher output, paid API request or approved training example was produced.** The required live teacher pilot, quality audit and student-benefit experiment remain incomplete.

## Provider verification

Official documentation confirms [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) as `gpt-6-luna` and [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna) as `gpt-5.6-luna`. Both initial choices are supported by the configuration/price-bound tests. These are documented API IDs; no live account access or immutable model-weight revision has been verified. The requested labels remain separate from provider IDs.

The adapter constructs a [Responses structured-output request](https://developers.openai.com/api/docs/guides/structured-outputs) with a strict JSON schema, explicit output bound, `store=false`, Standard/default service tier and no remote tools. It requests no hidden reasoning and defaults to supported `reasoning.effort=none`. One HTTP attempt is made, with a 60-second timeout and no redirects or automatic retries. Tests exercise this contract through a fake HTTP transport, not the service itself. Keys are read only from `OPENAI_API_KEY` at request time and are not stored in records.

The current workspace has no `OPENAI_API_KEY` environment value. Account access, output-training rights/terms, allowed categories and teacher spending authorization remain unresolved. The USD 10 CUDA authorization does not cover teacher calls. `configs/teacher-disabled.json` ships with live generation false, zero budget and no approval.

## Durable request and spending controls

- A canonical request includes scenario/family identity, parent lineage, task, independent style/content controls, context, factual oracle, schema, prompt version, provider/model ID, reasoning setting and output limit. Held-out scenarios, held-out derivatives and mismatched parent families are refused before transport. Lineage labels are caller assertions; they are not a substitute for reviewed-source intake or upstream partition verification.
- Request keys include the recipe and exact payload. SQLite commits raw responses, usage, checksums and accounted/reserved amounts. Cache hits survive restart and run the current validator again; changing a validator does not regenerate or rebill the response. Rejected/refused/incomplete responses also remain cached.
- One outstanding request is permitted. An interrupted or uncertain request keeps its reservation and cannot be replayed automatically. A timeout or invalid usage/model/tier response halts new requests. No automatic uncertainty reconciliation is provided: verify provider records before any future reconciliation feature releases a reservation.
- The same journal fixes its authorization, total spending estimate and request-count cap. Restart cannot silently increase/reset them. Cached reads do not consume another request. Concurrent reservation tests prove that two workers cannot both gain an outstanding slot. Deleting/replacing the journal or spending through another application is outside this local accounting boundary.
- Before a paid request, reserve the verified maximum model input window plus the requested maximum output, using conservative per-token rates. This avoids treating a character estimate as a billing bound. On a valid response, retain the upper-rate accounting for actual reported usage and release the unused reservation. Output usage includes non-visible generated tokens; see [token counting](https://developers.openai.com/api/docs/guides/token-counting).
- The [API pricing snapshot](https://developers.openai.com/api/docs/pricing) gives conservative Standard/global long-context input cache-write/output bounds of USD 0.25/0.75 per million tokens for GPT-6 Luna and USD 0.50/1.80 for GPT-5.6 Luna. At a 922,000-token input bound and 2,048-token output limit, reserve USD **0.232036** or **0.464686** per outstanding request respectively. These are deliberately conservative reservations, not predicted request costs or settled charges. Fast/regional processing, hosted tools and other providers require separate verified bounds.
- The current registration expires after 25 October 2026 and must be revalidated. Approval also requires current pricing, terms/category and account-access evidence. A provider deviation or wrong price assumption can still exceed an estimate: the journal is not a provider-enforced billing cap. Settled cost stays null.

## What validation does and does not establish

The scenario oracle checks exact typed factual metadata, expected action/arguments, control labels and a local integer-money multiplication tool result. The schema rejects extra fields; JSON parsing rejects duplicate keys and nonfinite values. Schema references are refused to prevent validation from fetching external documents.

**These checks do not verify the free-text reply, stylistic quality or actual content category.** A deliberate test supplies a false reply alongside correct metadata: it remains pending human review with free-text/style/content verification false and training eligibility false. Passing metadata is never reported as broad conversation quality or training approval.

Context is input only, including erroneous historical assistant turns in a student-correction scenario. A future training adapter must supervise only the validated generated continuation, rather than applying an all-assistant mask to the erroneous history. No teacher-to-training release adapter or structured tool-call serializer is supplied here. The existing review gate cannot be bypassed by these records.

## Evidence

- **30 focused teacher tests** cover both model price configurations, disabled/unapproved transport, request and spending caps, restart/cache integrity, concurrency, interruption/timeout, corrupted cache, held-out lineage, schema/typed arguments, mock execution, refusals, incomplete output, current-validator reuse, failed-result publication recovery and credential non-persistence.
- Full local suite: **139 passed, 5 CUDA skips**; see `reports/milestone-nine-tests.xml`. No new NVIDIA job was launched.
- Offline replay: **30 handcrafted fixture requests**, six task labels × five style labels, all in one scenario family. Repeating them gives 30 cache hits and zero additional fixture calls. Real teacher outputs, live HTTP calls and human/training approvals are all zero. These are plumbing fixtures, not a diverse dataset or measured style demonstrations. See `reports/milestone-nine-replay.json`.
- Raw fixture records and the journal stay under ignored `data/teacher/replay-audit-v1`. Provider readiness and cited bounds are in `reports/milestone-nine-provider-readiness.json`.

## Reproduce and next live step

Install `.[dev,mlx,tokenizer,teacher]` on the laptop. Reproduce the offline replay into fresh paths:

```sh
.venv/bin/python scripts/audit-teacher-replay.py --output data/teacher/new-replay --report data/teacher/new-replay-report.json
```

The live entry point is `python -m slm.teacher.run --config CONFIG --scenario SCENARIO --output OUTPUT`. The shipped configuration refuses execution before reading a scenario or credentials. Do not enable it until actual user budget authorization, local key provisioning, account access, terms/category review and a current quote are recorded. No credential should be placed in a config or result file.

Proposed first live check for review: GPT-6 Luna, at most 20 requests, at most 2,048 output tokens each, one outstanding call, no automatic retries, separate USD 1 maximum local budget. The request cap and journal budget must both be configured; reservation headroom may stop the run before 20 requests. Review the yield and language quality before requesting the planned larger teacher batch. This proposal grants no authorization.
