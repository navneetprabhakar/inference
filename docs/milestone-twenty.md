# Bounded MCP Streamable HTTP

Creator: Navneet Prabhakar

Date: 19 October 2026

## Outcome

The application-owned MCP registry now supports an explicitly configured HTTP endpoint, JSON or SSE responses, static environment credentials and verified TLS. The existing student interface, pinned discovery, schema validation and result correlation remain shared with stdio. No model selects URLs, credentials, certificates or transport settings.

Local suite: **451 passed / 11 unavailable-CUDA skips**. Scripted controls exercise actual local SDK HTTP servers; random students remain negative controls. No learned conversation/tool skill, production authorization or full protocol conformance is accepted.

## Protocol and connection profile

The same pinned **MCP SDK 2.3.0** owns negotiation and protocol message semantics. Tests exercise current **2026-07-28** and forced legacy **2025-11-25**, each with JSON and SSE. The current protocol uses POST responses without the legacy session GET channel; the SDK supplies protocol/method metadata and declared argument headers. See the [current Streamable HTTP specification](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http) and [SDK transport documentation](https://py.sdk.modelcontextprotocol.io/client/transports/).

The bounded transport wraps the SDK's HTTP client boundary. It forwards only POST/GET/DELETE to the exact configured endpoint. A legacy GET channel and session DELETE remain supported. Current-protocol GET, Last-Event-ID resumption, redirects and repeated tool POST IDs are refused before forwarding. Low-level tool submission still bypasses high-level schema/input-required retries. Tests record one peer tool POST per attempted fault case, with zero redirect-target requests and zero resume requests. This does not establish exactly-once remote execution: a lost response leaves an unknown outcome.

| Default limit | Value |
| --- | --- |
| Single response / outbound JSON body | 131,072 bytes |
| Cumulative raw response bytes | 1,048,576 bytes |
| HTTP forwarding attempts | 256 |
| Response header bytes, after HTTP parser | 16,384 bytes |
| Connections / keep-alive connections | 4 / 2 |
| Startup / discovery / call deadline | 5 seconds each |

Limits have bounded configuration ranges. Response streams are counted before application buffering; JSON and completed SSE payloads pass the strict existing JSON-RPC parser. Duplicate keys, nonfinite/deep JSON, oversized or truncated events and compressed bodies fail explicitly. Compression is disabled rather than decoded outside the raw-byte accounting. Header limits apply after the underlying HTTP parser; this is not a universal hard memory/CPU guarantee. The registry adds a bounded shutdown deadline; the HTTP client releases its pool and response streams, while a separately owned remote server remains running.

## Credentials, endpoint and TLS

- HTTPS is required except explicit **numeric-loopback HTTP** opt-in for local development. URLs cannot embed userinfo, query credentials or fragments. Host configuration owns DNS/endpoint choice; this is not a general SSRF sandbox for untrusted configuration.
- `bearer_token_env` or `headers_env` reads explicitly named environment variables. Credential values cannot contain controls/non-ASCII and never enter model descriptors or connection reports. Host/protocol/framing header overrides are rejected; SDK-generated argument headers are tested separately. Avoid secrets in remote tool descriptions/results: the transport cannot make arbitrary server content non-sensitive.
- Proxy/environment authentication defaults are disabled. No OAuth discovery, browser sign-in, refresh, credential acquisition, 401 recovery or automatic credential forwarding to redirects occurs. A rejected credential closes the connection and requires explicit reopening with corrected host settings. Static token support is not production MCP authorization compliance.
- Certificate and hostname verification remain enabled. An optional CA file is captured once, loaded from those same bytes and hashed; later file mutation cannot change that configured trust context. Local HTTPS controls verify trusted success, untrusted-CA rejection and hostname rejection. Failed handshakes produce no HTTP requests at the fixture and therefore transmit no HTTP authorization header to it.
- HTTP counters describe forwarding attempts. `tool_requests_submitted` describes SDK submissions; independent fixture logs distinguish received requests from model/host intent. Neither proves arbitrary remote effects completed.

## Configuration and CLI

Use a host-created configuration such as this template; replace the example endpoint and environment-variable name locally. Never commit credential values.

```json
{
  "transport": "streamable_http",
  "url": "https://mcp.example.invalid/mcp",
  "bearer_token_env": "SLM_MCP_TOKEN",
  "namespace": "products",
  "selected": ["catalog.search"],
  "timeout": 5,
  "mode": "auto"
}
```

Optional fields include `headers_env`, `ca_file` and `transport_limits`. Relative CA file paths resolve against the configuration directory. Subprocess `command`/`cwd`/`env` settings cannot be mixed with HTTP settings. Existing stdio configurations remain supported.

```sh
python -m slm.mcp.cli discover --config MCP.json --output DISCOVERY.json
python -m slm.mcp.cli run --config MCP.json --model MODEL_DIR --tokenizer TOKENIZER_DIR --tokenizer-hash SHA256 --history HISTORY.json --backend mlx --output TRACE.json
python scripts/audit-http-mcp.py --output REPORT.json --artifacts PRIVATE_DIR
```

The library equivalent is `MCPRegistry(url=..., bearer_token_env=..., selected=[...])`. Model inference still uses `ToolModel` and `run_turn`. CLI reports include the final post-close connection audit. A real CLI negative test verifies no tool submission and no credential value written to the report.

## Evidence and acceptance limits

- Focused HTTP/stdio suite: **66 passed**. HTTP-only tests cover protocol headers, SDK argument-header mirroring, Origin rejection, environment-proxy isolation, static credentials, strict endpoints, CA pinning, JSON/SSE faults, CLI invocation and cleanup.
- Full local suite and source-hashed runtime audit: `reports/milestone-twenty-tests.xml` and `reports/milestone-twenty-http-audit.json`. Raw traces/peer logs remain ignored under `data/http-mcp-audit-v1/`.
- Seven scripted scenarios use independent semantic checks and generate **five actual peer tool calls**. No-tool and clarification controls submit none. Structured success is separate from English truth/style review.
- Actual random MLX student: independent mechanics tokenizer, **34,976 parameters**, seven tasks, **zero structured passes and zero tool submissions**. No model training occurs in the audit.
- Nine additional audit probes cover JSON, legacy JSON/SSE, trusted HTTPS, redirects, rejected call authorization, oversized SSE, disconnected SSE and timeout. Client closure is checked separately from fixture-owner shutdown, process reaping and listener closure. Test certificates/private keys are temporary and not retained in Git.

This verifies local interoperability against the pinned official SDK, not arbitrary remote-service deployment, OAuth, authorization policy, arbitrary media/schema extensions, full protocol certification or actual NVIDIA HTTP execution. No teacher, cloud or real-service calls occurred; source approvals remain zero. Earlier full-size trajectory failures and all production data/tokenizer/teacher/suite gates remain unchanged.

Next: batch actual NVIDIA validation of the newer dense, curriculum and typed-runtime paths within the existing validation-only ceiling, with finite execution and verified cleanup. Source review is already pending in the app; do not infer approval. Teacher remains **Codex CLI only**, without API fallback. CUDA planning allowances remain **USD 5 of USD 10**, with settled charges unknown. Real language pilots require approved training data and a selected tokenizer.
