# CLI conversation teacher pilot

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

The active conversation teacher uses **Codex CLI with saved ChatGPT sign-in**, following the instruction “use codex cli, dont use API”. One real SFW correction demonstration was generated with **GPT-5.6 Luna**, then read from the durable cache three times without another generation. The demonstration passes structured checks but is **not approved for training**. The separate USD 1 API pilot authorization was recorded and then superseded operationally by the CLI-only instruction; no API spending was enabled.

Gradient accumulation was identified as the next independent trainer task, then deferred while implementing this requested transport change. It is still unimplemented.

## Transport contract

- Uses installed `codex-cli 0.144.4`; other versions fail until their contract is reviewed. This is a tested-version pin, not a claim that the installed CLI is current.
- Runs `codex exec` with stdin, a strict output schema, an ephemeral session, a temporary working directory, read-only sandbox and user configuration disabled. Prompt text is passed without shell interpolation. The prompt/version/scenario/schema, CLI version and controls bind the cache identity; the full submitted-prompt hash is recorded. Changing hardcoded prompt semantics requires a prompt-version change. CLI-injected system context is not captured.
- Forces ChatGPT authentication and verifies `codex login status`. API key environment variables are excluded and there is no API fallback. Existing account authentication is reused without reading/copying its credential cache. No automatic credit purchase or usage reset is supplied.
- Disables shell execution, code-mode host, applications/plugins, MCP configuration, browsing/search, images, hooks, memories and delegation through explicit flags. Any observed non-message/non-reasoning item rejects the result. These flags and a read-only sandbox are not a separate hostile-code container or proof that all possible future CLI capabilities are absent.
- Configures a model explicitly. The refreshed local catalog listed `gpt-5.6-luna`, which was selected from the original two allowed teacher choices. Events attest usage/completion, **not an immutable served-model identity**; `resolved_model` remains null.
- Rejects held-out scenarios and non-SFW categories before launch. Input is limited to 64 KiB; final response to 16 KiB; stdout/stderr are watched at 512/128 KiB. A 120-second watchdog terminates the process group on timeout. These polling limits may briefly overshoot between checks.
- The observed output-token gate is **post-response**, not a server generation limit. It conservatively sums reported output and reasoning-output counters when available; their overlap is not assumed. The current CLI interface does not provide this adapter with the API's hard output-token limit or an enforceable dollar cap.

The official [non-interactive documentation](https://developers.openai.com/codex/noninteractive) describes structured output, JSON events, ephemeral runs and saved authentication. [Authentication documentation](https://developers.openai.com/codex/auth) distinguishes ChatGPT subscription access from API billing. This implementation was tested against local help and behavior; neither page proves this account's output-training rights or settled costs.

## Cache, accounting and failed launches

`configs/teacher-cli-pilot.json` is the current explicitly enabled pilot entry point. `configs/teacher-disabled.json` remains disabled and the API adapter remains unused.

The SQLite journal fixes the authorization identity and counts launch slots. One outstanding request is allowed. Timeouts, nonzero exits, malformed events, unexpected tools or uncertain usage halt new requests; they are not retried automatically. Cached responses are hash checked and revalidated without consuming another slot. The final result directory is published atomically; publication failure can reuse a completed cached result.

Two early CLI launches exited with code 1 before any usable output was retained. An offline diagnostic reproduced an invalid built-in provider override, which was removed. The first launch's original stderr was lost; the second launch's root cause is not established. Neither is claimed a free or unbilled request. Future nonzero exits preserve bounded private diagnostics and a hash/error report.

The first journal remains halted with one consumed uncertain slot. The second retains one failed slot, explicitly reconciled from the observed terminal process exit, plus the successful slot. Reconciliation marks a key **abandoned**, never replayable, and does not release its count or claimed usage. It accepts only a zero-monetary CLI journal; paid API reservations cannot use it. The helper requires actual terminal-process evidence and is not called automatically by generation or cache reads.

The current journal has a maximum of **19** slots; together with the first frozen slot this preserves the proposed **20-launch** ceiling. Three slots have been consumed across both journals: two failed launches and one successful generation. This is a launch counter; built-in CLI HTTP retries are outside its accounting. Do not unhalt the historical journal or create another pilot journal to bypass the combined limit.

All monetary journal entries are zero because this transport does not make Platform API calls. **That does not mean account usage is free or bounded to USD 1.** ChatGPT subscription/credit effects and settled CLI cost remain unknown. No credit purchase, reset, cloud job or public-data training occurred.

## Evidence and limits

- Full suite: **187 passed, 6 CUDA skips**. Twenty-one CLI-focused tests cover saved-auth/no-key behavior, strict schema/stdin, version checks, output/usage limits, unexpected tool events, cache revalidation, request caps, uncertainty, terminal reconciliation, timeout/exit/oversize failures, provenance, local diagnostics and atomic publication recovery.
- The real demonstration handles a correction from three cups to two at 1,250 minor currency units each. Its response gives **2,500**. Exact typed facts, action/control metadata and the executable oracle agree. This sample is an ordinary fixture family, not representative conversation coverage.
- CLI usage: **11,088 input tokens**, **116 output tokens**, **35 reasoning-output tokens**. Counters are retained separately; input includes CLI overhead, which dominates this tiny demonstration. Measure useful output per account token before scaling. No exact rate/cost conversion is inferred.
- Three subsequent cache reads kept the journal unchanged and retained the same response hash. The latest read also checks the current usage/provenance contract.
- Human approvals, reviewed teacher training examples and student updates on teacher data remain **zero**. Structured metadata checks do not establish prose, style or content quality.

Machine-readable evidence: `reports/milestone-twelve-cli-pilot.json` and `reports/milestone-twelve-tests.xml`. Private scenarios, outputs, cache and logs remain in ignored `data/teacher/cli-pilot-v1` and `data/teacher/cli-pilot-v2`.

## Reproduction and next steps

Read the current journal before any new call. A fresh **output directory** for the existing scenario reads its cache:

```sh
.venv/bin/python -m slm.teacher.cli --config configs/teacher-cli-pilot.json --scenario data/teacher/cli-pilot-v1/scenario.json --output data/teacher/cli-pilot-v2/new-cache-read
```

The ignored scenario is produced by `fixture_scenario('correction', 'professional')`, with `scenario_id=cli-pilot-order-correction-professional-v1` and `family_id=cli-pilot-order-total-v1`. Keep the parent/held-out checks intact. Do not replace or delete the journals to reproduce a live call.

Next: implement supervised-token-weighted gradient accumulation, audit a broader bounded teacher sample, confirm account-specific training rights, and build a reviewed continuation-only teacher-to-training adapter. Public-source review, production tokenizer, accepted full-size training portability, sustained language pilots, runtime/MCP and ESCI remain open.
