# Local mocked CRUD diagnostic

Ten mock tools (`notes`, `tasks`, `contacts`, `inventory`, `events`, `bookmarks`, `tickets`, `preferences`, `documents`, `projects`), each supporting create/read/update/delete. Every tool uses an isolated Python dictionary. Values are opaque strings; domain validation (email formats, URLs, inventory counts) is intentionally not implemented. There is no database, network access or executable-code tool.

From the repository root:

```sh
.venv/bin/python -m unittest discover -s reports/ganesh-tool-crud-v1 -p test_harness.py
.venv/bin/python reports/ganesh-tool-crud-v1/harness.py --run --device mps
```

The run refuses to overwrite existing raw results. `suite.json` contains48 scenarios/54 intended user turns; exact expected calls and seeded states are evaluator-only. They are not inserted into the model prompt. Each scenario starts with fresh mock state; the two four-turn workflows retain state and raw history. Failure-blocked follow-ups remain in the denominator. Calls use strict native-frame JSON; the host never extracts calls from prose, fabricates model actions or repairs answers. At most two calls and one final action are allowed per turn; generation is greedy,128 tokens/action, without repetition penalties or truncation.

The adapter is experimental: production `forge-nanochat-v1` only supports calculate/convert. The diagnostic preserves native framing delimiters but supplies a new generic schema and structured observations. It does not modify the production serializer or serving selection. All ten tools are visible in the first prompt. The model must select the requested name and op; schema success is distinct from task success and grounded final text.

The explicit checkpoint is local Fit30, not an assertion that it is accepted or the serving default. Model payload and tokenizer are hash-validated by the existing loader. `run-config.json` binds checkpoint, harness and suite. `raw-results.jsonl` preserves token IDs, decoded output, parsed actions, actual mock observations and before/after state. `known_tool_control.py` separately probes the unchanged production calculate/convert broker to help distinguish novel-schema transfer from existing-tool failure. None of this is a protected release test or training admission.
