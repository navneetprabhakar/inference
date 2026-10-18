# Local tool runtime and typed SFT framing

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

Five local synthetic tools now connect typed student decisions to bounded host execution, correlated results and a second student response. A dedicated serializer and verified token-shard path support supervised tool conversations. Syntax, exact action semantics, executable results and free-text quality remain separate.

Local suite: **385 passed / 11 unavailable-CUDA skips**. Seven scripted controls pass; seven actual random-student controls fail without executing a tool. **No learned tool competence, MCP transport or production data acceptance is claimed.**

## Five registered tools

| Tool | Inputs | Local fixture behavior |
| --- | --- | --- |
| `catalog_search` | Query, fixture price cap, excluded brands, result limit | All query words match title/category; filter, then sort by fixture price/ID |
| `product_lookup` | Exact product ID | One synthetic product or explicit not-found result |
| `product_compare` | Two or three distinct IDs | Ordered synthetic products; no invented missing fields |
| `arithmetic` | Add/subtract/multiply and two bounded integers | Exact integer result; no expression evaluation or float coercion |
| `document_lookup` | Exact document ID | Synthetic document body or explicit not-found result |

Schemas declare required fields, bounds and additional-field rejection. The host clones discovery descriptors, pins their hash and checks both arguments and successful output schemas. Booleans cannot replace integer arguments; floats, nonfinite numbers, duplicate JSON keys and integers outside the portable exact range are refused.

Catalog amounts are explicitly `fixture_price_minor` in `fixture_minor_units`, with synthetic provenance. They are not live prices, availability or ESCI-derived facts. These pure local handlers make no network calls and perform no product/customer mutations.

## Decision and execution contract

The wire format has three typed decisions:

```json
{"kind":"call","id":"c1","name":"arithmetic","arguments":{"operation":"multiply","left":1250,"right":2}}
{"kind":"answer","text":"The synthetic total is 2500 minor units.","facts":{"total_minor":2500}}
{"kind":"clarify","question":"How many tickets?","missing":["quantity"]}
```

- A call is framed by reserved `tool_call_start`/`tool_call_end` IDs. Answers and clarifications are ordinary JSON content. Raw text resembling control tokens never acquires structural IDs.
- Tool replies include matching call ID/name, success flag and exactly data or error. Histories reject orphan results, mismatched/duplicate IDs, unresolved calls and invalid role transitions.
- Default execution: **one call attempt, two model decisions, at most 128 generated tokens per decision and 2,048 result bytes**. Explicit bounds allow at most three calls/four decisions, 512 generated tokens and 8,192 result bytes. Dependent-call capability is not accepted by this milestone.
- Call attempts include schema-invalid/unsupported calls. A budget or repeated-ID refusal never executes a handler. Handler/output errors remain explicit. Oversized results become bounded errors; no partial result is silently treated as complete.
- The host reserves history space for the declared call/result budget before execution; overflow is refused without truncation.
- No automatic repair or retry occurs. Reports retain raw malformed output where generation produced it, protocol validity, argument validity, execution count, errors and final decision. Nonfinite generation or context overflow can fail before a raw sequence is available.
- Available input schemas are injected by the host. They are removed from returned caller history so later turns do not accumulate duplicate discovery text. Completed final decisions are appended to history; IDs remain correlated on subsequent turns. Failed runs can leave a user/tool-ended pending history for an explicitly controlled continuation; the library does not authorize a fresh retry budget automatically.
- Tool/document text stays data. One hostile document fixture contains instructions; a scripted control proves the host does not dispatch text as code. This does **not** establish learned resistance to prompt injection.

The model receives recent history and selected tool schemas, never the scenario's expected action or answer. The host owns discovery, validation, budgets and execution. Correct `facts` metadata can still contradict the English response: a dedicated test demonstrates this, and free-text meaning/style remain unverified rather than being credited automatically.

## Training and compatibility

`task: tool_dialogue` uses plain role/content string envelopes, with canonical JSON inside assistant/tool content. This keeps provenance/review tooling intact while selecting the dedicated serializer. The curator validates complete call/result order. Privacy redactions that would edit a typed transcript are rejected for manual rewrite rather than silently changing JSON facts or fields.

Assistant decision content, call delimiters and assistant termination are supervised. User/system/tool content and all role headers are masked. The same BPE namespace and model architecture are used; no vocabulary migration or added reserved IDs are needed.

Typed artifacts use **token-shard version 2**, `message_format: tool-decisions-v1`, objective `sft`. Their reader reconstructs messages and reserializes them to verify canonical content, call/result correlation, framing, shifts and masks. Plain/prose token-shard version 1 remains supported, including historical files without format metadata. Training checkpoint versions 1/2/3 are unchanged.

One artifact cannot silently mix plain and typed formats. Prepare separate components with `--message-format plain-dialogue-v1` or `--message-format tool-decisions-v1`, then combine them through the existing SFT mixture/curriculum machinery. Without a filter, a homogeneous source is detected automatically; mixed input fails before publication. Structured tool dialogue is refused for the foundation objective.

Two-logical-update synthetic SFT tests match independent masked cross-entropy and preserve exact own-resume state on each tested backend. These are mechanics tests, not language/tool learning pilots. The existing CLI teacher output still needs reviewed conversion into this format; its pending example is not made training-eligible by this work.

## Verification and retained failure

| Evidence | Scope |
| --- | --- |
| Seven scripted positives | Five tool choices plus separate no-tool and clarification cases. Correct first action, exact arguments, successful execution, independent explicit expected result data and final metadata. Scripted answers are not student predictions. |
| Wrong quantity | Schema-valid arithmetic executes, but exact arguments/result/final metadata fail. Successful execution alone is not semantic success. |
| Wrong product data | A schema-valid incorrect handler result fails the independent expected-data oracle even when final answer metadata matches its target. |
| Actual random student | 34,976 parameters, MLX, 4,096-position mechanics window, independent random-word tokenizer. All seven scenarios end `invalid_decision`; zero executed calls and zero structured passes. No training updates occur in this audit. |
| Raw decoder | Scripted-logit complete call frames pass on MLX and PyTorch CPU without masking logits. CUDA variant skips locally. This tests transport/framing, not learned output quality. |
| Failure/state paths | Malformed JSON/frames, wrong arguments, unknown tools, call/step/result limits, duplicate IDs, tool faults, invalid outputs, hostile document data, continued history, filtered formats and corrupted masks/boundaries. |

Initial full-suite result: **2 failed, 380 passed, 10 skipped**, retained in `reports/milestone-eighteen-initial-tests.xml`. New shard provenance hashes changed deterministic batch order and exposed hard-coded curriculum fixture assumptions about tail sizes. The fixture now explicitly selects different accumulation sizes that guarantee short tails, computes stage boundaries from declared counts and guarantees stage-local warmup coverage. Exact state/metric comparisons, independent LR checks and numerical tolerances were retained. This was not a waived numerical gate.

Final evidence: `reports/milestone-eighteen-tests.xml`, `milestone-eighteen-tools-audit.json`, current source hashes and raw control traces under ignored `data/local-tools-audit-v4/`. The audit's seven scenario families are unreviewed, explicitly held out and blocked by reserved IDs/exact contexts from teacher requests and train ingestion. No statistical release success rate follows from these fixtures.

## Running and remaining work

Install the tokenizer and tools extras. Discover local schemas or run a checkpoint with a JSON history:

```sh
python -m slm.inference.tools list --output TOOLS.json
python -m slm.inference.tools run --model MODEL_DIR --tokenizer TOKENIZER_DIR --tokenizer-hash SHA256 --history HISTORY.json --backend mlx --output TRACE.json
python -m slm.data.tokenized --release REVIEWED --tokenizer TOKENIZER_DIR --output TOOL_SHARDS --objective sft --message-format tool-decisions-v1
```

Measure the real tokenizer's schema overhead before choosing the context budget: the current five-tool input descriptor is 2,301 UTF-8 bytes and can exceed a 2K token window with a tiny byte-heavy tokenizer. Overflow is refused, not truncated. The 4K random-tiny control does not extend or validate the 81M model's context contract.

`run_turn` and `ToolModel.generate_decision` expose the same library path. `scripts/audit-tools.py --output REPORT --artifacts PRIVATE_DIR` reproduces the local controls. Fresh output paths are required; checkpoints/raw data stay outside Git.

Next: application-owned MCP transport and discovery mapping, followed by executable end-to-end checks and timeout/error handling. Actual NVIDIA typed runtime, production tokenizer/source approvals, reviewed teacher demonstrations, real language/tool pilots and mature-content/style acceptance remain open. Prior numerical trajectory failures remain failed. No cloud/teacher calls occurred; CUDA planning allowances stay USD 5 of USD 10, settled charges unknown. Teacher transport remains CLI-only.
