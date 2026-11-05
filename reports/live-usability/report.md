# Live local assistant usability screen

The running assistant completed 1/16 conversations and answered 9/34 turns successfully. Multiplication followed by doubling was the only complete conversation. The five ordinary conversation sessions passed 0/10 turns.

The local frontend API served the experimental assistant-preview runtime on CPU, checkpoint SHA-256 c83f9792200747cf20c9f93ff92087fa0dba45d7c54a9af7581454f019e53609. Each synthetic session started fresh. The suite and rubric were hashed before the first request, then replayed serially once. The assessment uses the visible answer and actual execution trace. A bare number was accepted when the prompt and successful conversion trace established the unit. The greeting in session 01 received credit for responding socially.

| Session | Turns passed | Whole conversation |
|---|---:|---|
| 01 introduction | 1/2 | Fail |
| 02 correction | 1/3 | Fail |
| 03 social continuity | 1/3 | Fail |
| 04 addition | 1/2 | Fail |
| 05 division error | 1/2 | Fail |
| 06 permission | 0/2 | Fail |
| 07 multiplication | 2/2 | Pass |
| 08 length | 1/2 | Fail |
| 09 temperature | 0/2 | Fail |
| 10 incompatible units | 0/2 | Fail |
| 11 unit permission | 1/2 | Fail |
| 12 supportive conversation | 0/2 | Fail |
| 13 ordinary editing | 0/2 | Fail |
| 14 everyday planning | 0/2 | Fail |
| 15 ordinary explanation | 0/2 | Fail |
| 16 ordinary choice | 0/2 | Fail |

Answer-path counts: `gpt2/dialogue` 24, `host/session-memory` 2, `host/observed-number` 5, `host/reference-abstention` 2, `host/observed-error` 1.

Actual tool executions: 6. No disabled-permission turn executed a tool. Five turns reported a routing failure without an answer. Frames proposing a call are distinct from executions. The tool trace identified its source as “offline fixture”. Division by zero produced an actual tool error. The incompatible-unit request produced a blocked proposal and no tool error.

Exact prompts, answers, frames, frame origins, calls, execution outcomes and individual judgments appear in results.json. Only trace timestamps were removed. This small authored screen measures this running configuration and carries no release-target inference.
