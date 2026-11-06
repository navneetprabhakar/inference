# Session-length coverage limit

Root inspected all custody-eligible original tool histories after alignment. Both train and exposed development contain at most two user turns and two tool calls per session. This is narrower than the runtime's explicit two calls per turn / four calls per session capacity.

| Split | No-call one-turn | One call, one turn | One call, two turns | Two calls, one turn | Two calls, two turns |
|---|---:|---:|---:|---:|---:|
| Train | 64 | 3,102 | 1,474 | 160 | 534 |
| Exposed development | 12 | 238 | 118 | 11 | 43 |

The packed tool targets have no exposure above predicted position 767. Chat targets do cover higher positions, but that does not prove long tool-session behavior. CPU runtime fixtures show that at least one natural four-call session fits the fixed context; they do not establish model capability.

A small separate prospective session extension is being designed. Existing candidates, masks, context and reply reservation remain frozen. Longer sessions must preserve complete histories, actual observations and fixed reply headroom; an overlength session is refused as a whole. This gap must be addressed in development evaluation regardless of whether an extension is admitted for training. The existing short-session diagnostic cannot establish the full delivery contract by itself.
