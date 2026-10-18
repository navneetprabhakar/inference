# Broader CLI conversation-teacher pilot

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

Six additional real **SFW Codex CLI generations** exercise correction, clarification and tool-action demonstrations in professional and caveman styles. Each passes the existing strict schema, fact/action, mock-execution and control-label checks. All six remain **pending human review and ineligible for training**. This is a small transport/data-quality pilot, not broad conversation/style validation or student learning.

Each candidate was subsequently read from cache: **six cache hits, zero extra generations**. Combined historical/current generation-launch slots: **9 of 20**, including two retained failed slots. No historical journal was reset, unhalted or replaced. The active journal has seven completed generations and one abandoned slot; the frozen first journal retains its one uncertain slot.

Validation: **51 teacher-focused tests passed**. Model/runtime code is unchanged; the latest full suite remains milestone twenty-three's **468 passed / 12 CUDA skips**. No student updates, public-data approvals, cloud jobs or Platform API teacher calls occurred in this pilot.

## Scope and request controls

- Requested model **`gpt-5.6-luna`**, installed CLI **0.144.4**, saved ChatGPT authentication. The CLI contract does not report a resolved model identity; that field remains null rather than inferred.
- Six synthetic-input cases, **one family**, three tasks and two styles. All variants stay in the train-designated family and pass the existing held-out guards. This is not proof of semantic isolation from every evaluation template.
- Synthetic scenario: notebooks at 875 minor units. Correction changes four notebooks to three; intended total 2625. Clarification lacks quantity. Tool action uses the existing teacher-only `multiply_amount` mock; the validator independently computes 2625. These are not live product prices or actual MCP service calls.
- One generation at a time, existing 120-second watchdog, response/usage checks, disabled tools/delegation, read-only temporary workspace and no API-key fallback. No new provider or model target was substituted.
- The existing [official non-interactive documentation](https://developers.openai.com/codex/noninteractive) describes saved authentication and schema-constrained final output. Actual access and behaviour here are evidenced by the six local result records; documentation does not establish this account's training-use rights or costs.

## Important quality finding

The professional tool candidate's reply announces an intended calculation, while the caveman counterpart reports the numeric total. Both have identical structured action/result facts and pass the current automated checks. The single `reply` field currently has an underspecified role: pre-tool intent versus post-tool answer.

Do not treat this pair as reviewed meaning-preserving final answers. Literal presence of `2625` is reported only as a descriptive observation, not a general semantic grader. Free-text truth, style, content and training-use rights remain unverified. The other four replies also require actual review; reading them during technical inspection does not grant human approval.

Before extending generation or admitting teacher data:

1. Define a versioned reply contract with explicit final/post-result semantics, preserving the old prompt/cache identity for historical records.
2. Implement a reviewed **continuation-only** bridge. The ordinary SFT serializer currently supervises every assistant message; historical assistant input, especially wrong student answers, must not become teacher supervision. The reader already refuses `student_correction` without that adapter.
3. Normalize teacher mock actions into registered host tool schemas/typed transcripts, execute the appropriate local oracle, and review the composed transcript. Do not teach the runtime to call an unregistered mock name or assume JSON metadata is an executed host trajectory.

These are concrete remaining integration requirements, not a reason to waive source, policy or rights reviews.

## Accounting and retained evidence

| New pilot counter | Observed |
| --- | --- |
| Generation launches | 6 |
| Cache rechecks | 6 |
| Input tokens | 66,539 |
| Cached-input tokens | 0 |
| Output tokens | 708 |
| Reasoning-output counter | 220 |
| Human/training approvals | 0 |

Counter overlap is not established; output and reasoning counters are reported separately. CLI-internal HTTP retries are not counted by the local generation-launch ceiling. There is no adapter-enforced USD cap or hard server generation-token cap. No credit purchase or reset was performed, and settled CLI cost remains unknown. Shared account weekly remaining usage was 17% before and 16% after; other activity is concurrent, so that difference is not attributed to this pilot. No account identifiers, balances or credentials are committed.

Private artifacts under `data/teacher/broader-pilot-v1/`: six scenarios, result records, cache-replay records, plan, `review.json` and readable `REVIEW.md`. The Markdown review was queued in the app's file panel; successful visible opening is not claimed. It includes exact contexts/candidates and independent expected facts. The review file is a candidate worksheet, not an implemented training-release authorization format.

`reports/milestone-twenty-four-cli-pilot.json` records hashes, per-case structured outcomes/usage, journal states, scope and the reply-role finding. `reports/milestone-twenty-four-teacher-tests.xml` records regression checks. To revalidate an unchanged cached request, invoke `python -m slm.teacher.cli` with the same config/scenario and a fresh output path. Do not delete journals/cache entries or alter controls to repeat a billed generation.

Public source approvals, portability-policy choice, teacher terms/quality and evaluation-suite reviews remain pending. CUDA allowances stay **USD 7 of USD 10**, settled cloud charges unknown. Teacher remains CLI-only; the separate historical API path stays disabled.
