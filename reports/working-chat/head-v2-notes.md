# Follow-on tool head v2

**Accepted for separate product evaluation.** On the 439 previously reserved internal tool histories, v2 gained 217 strict first proposals and lost zero compared with v1. Both heads missed 244 of the 475 required first proposals. The benchmark scores tool behavior only.

| Internal measure | v1 | v2 |
|---|---:|---:|
| Required first operational intent | 63/475 | 330/475 |
| Strict first proposal, including ordered arguments | 14/475 | 231/475 |
| Complete tool-call sequence per user turn | 160/621 | 371/621 |
| Complete tool-call sequences across the history | 22/439 | 208/439 |
| Exact later proposals given the same authentic prior result | 0/46 | 33/46 |
| Exact later proposals given an overridden fixture result | 0/11 | 8/11 |
| Numeric result recall routed correctly | 28/60 | 60/60 |
| False dispatches on separate ordinary prompts | 0/128 | 0/128 |
| Prohibited executions | 0 | 0 |

First-proposal gains came from addition (7→16/59), subtraction (0→39/89), multiplication (7→27/82), division (0→28/56) and conversion (0→121/189). The strict score counts operand order for all arithmetic operations. Allowing reversal for addition and multiplication gave the same totals on this panel.

**Training and custody.** The fit used all 5,383 eligible varied-tool histories and 1,985 separately screened ordinary histories. Both heads received identical internal cases with the preexisting history digest. A prescore check found 18 ordinary first prompts duplicated across different histories in an initial fit. That fit was archived without evaluation. The revised split removed all matching prompts from fitting before either head was scored, and the 128 ordinary test prompts were unique. The cutoff and gate criteria are in `head-v2-protocol.json` and `head-v2-split-amendment.json`.

**Runtime.** The learned head distinguishes an initial decision from the decision after a successful call. It ranks typed current and previous user spans, prior arguments and the broker’s observed numeric result. The broker enforces permissions and the two-call turn ceiling. The optional product retains its existing extractive reader, GPT-2 and host result renderer. The head has 1,256,364 learned parameters and an 8,304,053-byte artifact. The combined GPT-2 and head count is 125,696,172, with the selected reader counted separately.

Use `followon_product_chat.Chat(model, tokenizer, guard)` to opt into the accepted head. Its constructor verifies the pin and acceptance evidence. A CPU integration check injected 36 into a first calculator call, divided the observed 36 by four, reported nine, and recalled nine without another dispatch. Local paired traces and that integration record are in `runs/working-head-v2/`.
