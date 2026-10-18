# Application-managed MCP stdio integration

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

The typed student runtime now uses an application-owned MCP registry through actual stdio server processes. It discovers tools, maps remote names to model-safe aliases, validates arguments/results, preserves call correlation and closes the connection after failure. The model never selects executables, credentials or transport details.

Local suite: **420 passed / 11 unavailable-CUDA skips**. Seven scripted scenarios pass through the official SDK server process with **five independently recorded peer tool calls**. The actual random student fails all seven scenarios and submits zero tools. This is MCP infrastructure evidence, not learned tool/conversation capability or production acceptance.

## Protocol and dependency evidence

The implementation pins **`mcp==2.3.0`** and checks that version before launch. The current SDK's client/session APIs handle protocol negotiation and message semantics; the application supplies a bounded stdio transport and an explicit registry policy. See the [official SDK client](https://py.sdk.modelcontextprotocol.io/client/) and [transport documentation](https://py.sdk.modelcontextprotocol.io/client/transports/).

Actual negotiation is recorded separately: default auto mode uses **2026-07-28** with the fixture SDK server; forced legacy mode uses **2025-11-25**. These tests use the same installed SDK server, not every historical or third-party implementation. Current protocol references: [SDK version negotiation](https://py.sdk.modelcontextprotocol.io/protocol-versions/), [tools](https://modelcontextprotocol.io/specification/2026-07-28/server/tools), [stdio](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/stdio).

`requirements-mcp-reference.lock` records all **28 observed transitive dependency pins**, including the cryptography extra, on macOS arm64/Python 3.12. SDK installation added dependencies without replacing existing model-runtime packages. The lock is separate from model/CUDA locks; platform markers and wheels must be resolved on another host. No SDK code is vendored.

## Connection, discovery and dispatch

- Host configuration supplies executable/argv, optional environment/cwd, namespace, selected remote names and limits. There is no shell-string parsing or model-generated process command. The child receives the SDK's limited inherited environment plus explicitly configured values. A real child probe verifies a mock parent API key is absent and an explicitly supplied fixture variable is present. No raw environment values appear in model descriptors or audit connection metadata.
- One persistent lifecycle task owns the SDK context on a dedicated event-loop thread. The synchronous registry serializes calls into that connection; MLX/PyTorch inference remains independent of transport management.
- Discovery supports bounded pagination, rejects duplicate names/cursor loops, and pins the complete advertised catalog. Remote names such as `fixture.arithmetic` become stable aliases like `mcp_fixture_<name hash>`, fitting the existing student ID contract. Namespace ownership belongs to the host; remote server display names are not used as unique identities.
- Before every dispatch, re-list the catalog without cache and compare its hash. Changes invalidate the connection before another tool submission; there is no silent refresh into a changed model context. Unsupported/missing selected tools fail explicitly.
- Input/output schemas use a bounded JSON Schema 2020-12 profile, including local JSON-pointer references. External references, schema IDs and dynamic references are refused; validators cannot retrieve external schemas. This is not support for every possible schema dialect or extension.
- The adapter deliberately calls the SDK's **low-level session**. The high-level API can perform schema-refresh or input-required retries; this path performs neither. Sampling/elicitation/roots callbacks are not enabled. Unsupported input-required responses fail and close the connection after one submission, without generating teacher calls or requesting credentials.

Discovery defaults: at most **16 tools, 16 pages, 65,536 descriptor bytes**; startup/discovery deadline **five seconds**. Limits are explicit/configurable within bounded ranges. The model's selected schema context remains capped at 16,384 UTF-8 bytes and must fit the actual tokenizer/context window; no tool/history is silently truncated.

## Results and failure accounting

Successful structured content is normalized into the existing correlated tool-result envelope. Text-only results remain text blocks in a data object. Structured non-object values are wrapped in `value`; explicit null is distinguished from absent structured content when represented by the SDK. Returned media, floating values outside the current integer-only student contract and oversized unsupported payloads become explicit host errors. No resource link is fetched and no numeric value is silently coerced. Where structured content exists, it is the application-selected representation; a result hash retains the original SDK result identity. Text quality and claims are still separate review obligations.

Tool `isError` responses remain correlated tool errors. Broken connections, timeouts, invalid output schemas, unsupported input-required results and transport violations invalidate the connection; no automatic replay occurs. A call without a valid result has an **unknown outcome**: a timeout does not prove that a remote operation did not execute.

Reports distinguish:

| Field | Meaning |
| --- | --- |
| `call_attempts` | Host call-attempt budget consumed, including schema-invalid calls |
| `handler_dispatches` | Registry handler entered, including catalog preflight failures |
| `executed_calls` | Local handler entries, or MCP SDK tool submissions for this turn; not proof of remote completion |
| `tool_requests_submitted` | Connection-wide SDK tool submissions |
| `tool_results_received` | Connection-wide validated tool results |
| `unknown_tool_outcomes` | Submitted calls lacking a validated result; conservatively retained after failures |

For example, a changed catalog can produce one handler dispatch but zero new tool submissions. Server-side fixture logs independently verify the positive audit's five actual requests. There is no exactly-once or idempotent-retry guarantee for arbitrary remote operations.

## Bounded transport and cleanup

The POSIX transport parses UTF-8 newline-delimited JSON-RPC into official SDK messages. It rejects duplicate keys, malformed/deep/nonfinite JSON and oversized/unterminated lines. Defaults: **131,072 bytes per line, 1,048,576 received bytes and 256 received messages per connection**. Memory streams do not prebuffer an unlimited queue. Stderr is drained with byte count/hash only; its raw contents are not retained or inserted into prompts.

On shutdown, close stdin, allow a bounded exit period, then signal the process group with SIGTERM/SIGKILL if necessary. Pipe closure/waits are bounded and protected during cancellation. The audit verifies each parent is reaped and absent. A child that deliberately ignores SIGTERM and holds pipes open is terminated by SIGKILL; its observed process state is recorded. Reaping an adopted zombie belongs to the OS. Processes that deliberately escape their process group are outside this cleanup guarantee; this transport is not a sandbox.

Tests also cover startup hangs, malformed/flooded stdout, pagination limits, output schema failure, server disconnect, text-only results, tool errors, unsupported media/floats/large results, catalog mutation, credential boundary, CLI runs and closure of the event-loop thread. Tests do not prove hard CPU bounds for arbitrary server-supplied schema validators or interoperability with every MCP server.

## Actual audit and usage

Evidence: `reports/milestone-nineteen-mcp-audit.json`, `milestone-nineteen-tests.xml`, pinned source/dependency hashes and ignored raw artifacts under `data/mcp-audit-v1/`.

- Seven scripted tasks: five tool cases, separate no-tool and clarification; **7/7 structured passes**, five actual peer requests, no automatic repair, no free-text/style approval.
- Random MLX student: **34,976 parameters**, independent random-word tokenizer, 4K mechanics window; **0/7 structured passes**, seven invalid decisions, zero tool submissions. Not an 81M inference or language-training result.
- Independent lifecycle probes: actual legacy call, hanging call without retry, catalog change before a second submission, oversized startup stdout and stubborn descendant cleanup. All parent processes are verified absent.
- No model training, teacher generation, real-service invocation or new cloud job occurs in this audit. Tests include the existing synthetic training mechanics. Public data/source approvals remain zero; all earlier numerical failures remain failed.

Library entry point: `with MCPRegistry([sys.executable, '-m', 'slm.mcp.fixture_server'], selected=['fixture.arithmetic']) as registry`, then use `run_turn` with a `ToolModel`. Supply a real host-owned executable/argv for another stdio server. Configured server code is not isolated or automatically authorized by tool annotations; production action policy remains an application concern.

The CLI takes a bounded JSON configuration with `transport: stdio`, `command` (argv array), and optional `namespace`, `selected`, `timeout`, `mode`, `cwd`, `env` and limits. Use an executable from an environment with the required SDK/server dependencies. Credentials belong in host configuration/environment, never model history or committed sample configuration.

```sh
python -m slm.mcp.cli discover --config MCP.json --output DISCOVERY.json
python -m slm.mcp.cli run --config MCP.json --model MODEL_DIR --tokenizer TOKENIZER_DIR --tokenizer-hash SHA256 --history HISTORY.json --backend mlx --output TRACE.json
python scripts/audit-mcp.py --output REPORT.json --artifacts PRIVATE_DIR
```

Fresh output paths are required. CLI results include the final post-close MCP audit. Candidate holdout guards now ignore a leading host/system message when checking exact task histories, so adding discovery schemas or changing a style header cannot relabel protected tasks as training data; this still does not establish semantic/paraphrase isolation.

Next: Streamable HTTP/authorization boundaries and actual NVIDIA validation of the newer typed/curriculum paths. HTTP, arbitrary remote-service authorization, broader schemas/media, multiround interactions and learned tool skill remain open. Source/tokenizer/teacher/suite reviews and real language pilots remain required. CUDA planning allowances stay **USD 5 of USD 10**, settled charges unknown; teacher transport remains CLI-only.
