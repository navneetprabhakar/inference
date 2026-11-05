# Fresh scoped usability smoke

**The experimental CPU preview passed 6/15 complete sessions and 17/34 turns.** It handled all three session-memory scenarios. None of the five everyday-prose sessions passed. Correct tool results were displayed faithfully even when the router chose incorrect arguments.

| Scope | Complete sessions | Passing turns |
|---|---:|---:|
| Explicit session name memory | 3/3 | 9/9 |
| Everyday prose, correction and constrained repetition | 0/5 | 0/10 |
| Single-tool requests with follow-ups | 2/3 | 4/6 |
| Dependent calls with follow-ups | 1/2 | 4/5 |
| Tool boundaries and capability questions | 0/2 | 0/4 |
| **Total** | **6/15** | **17/34** |

## Observed defects

- Five everyday turns failed to yield a valid response frame. The five remaining everyday answers were irrelevant. “Flinen” was returned for the workshop’s start time and repeated when uppercase was requested. A correction from a wicker basket to a blue tub produced repetitive prose about the United States.
- Six of eight required call positions had the requested tool and arguments. All eight dispatched calls succeeded. For a request to subtract nine from 46, the calculator received 9 minus 46 and returned −37. For 19 minus 4, it received 4 minus 4 and returned zero. Both displayed answers matched the faulty calls.
- The cross-turn chain used the observed 39 in a multiplication by four and recalled 156. The within-turn chain added 26 and 10, divided the observed 36 by six and displayed six. Its subsequent “repeat just the second result” request triggered an unnecessary clarification. Repetition also failed after the reversed subtraction.
- The disabled-tool turn made no call but produced unrelated prose instead of the requested expression. Both unknown-tide-capability questions got “Zelen” without a call. No prohibited execution or invented completed physical action was observed.

## Attribution and method

The nine successful memory turns were labeled `host/session-memory`. Of 15 responses traced to `gpt2/dialogue`, two passed, both short follow-ups after successful tool calls. The remaining passes came from five host-rendered tool results and one learned readback with host rendering.

The 15 synthetic sessions and all 34 turn rubrics were frozen before the first HTTP request. Each session received a new server-side history. Prompts were sent serially once to the refreshed `assistant-preview` runtime on loopback port 8767. The SHA-256 was `c83f9792200747cf20c9f93ff92087fa0dba45d7c54a9af7581454f019e53609`. An assistant reviewer applied the preregistered criteria to the returned answers, frames and actual traces. These measurements apply to the scoped product smoke.

The artifacts are `suite.json`, `protocol.json`, `transcripts.json` and `scores.json`. The earlier usability report was preserved.
