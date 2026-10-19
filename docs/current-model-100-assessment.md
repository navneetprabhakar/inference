# Current model: 100-conversation assessment

Creator: Navneet Prabhakar

Date: 19 October 2026

- **Result: 0/100 successful conversations, 0/300 successful requested turns.** Direct five-dimension score: **7.6/100**. Credit comes only from grammatical fragments; understanding, relevance, instruction following and context/correction handling each score zero.
- **Model tested:** latest trained fitting-control branch, 80,765,440 parameters, step96. Model manifest `b67af6576b40fc42504db9672499f2a183bea18c2e0a59c9c5eb2b15ee5dc747`. This is not a newly trained checkpoint or the main foundation branch.
- **Execution:** 100 separate sessions, three actual user/assistant turns each; 128 new tokens per reply, greedy MLX decoding. Fresh context between sessions, exact generated assistant text retained within each. No system prompt, retrieval, repair, teacher, real tool execution or gradients.
- **Coverage:** ten conversations each for greetings/name memory, arithmetic, extraction, English editing, professional style, caveman style, casual conversation, basic knowledge, simulated tool JSON, and mild adult-language/workplace register changes.

## What failed

- **Severe reply collapse:** only29 distinct replies across300 turns. The same story-main-idea sentence appears98 times. Stock clarifications call clear English requests random letters; car-shopping advice and looping antonym lists replace unrelated answers.
- **Memory and corrections:** no corrected name, owner, quantity, day or city is returned as requested. Exact copying also fails.
- **Styles and tools:** neither professional/caveman transformations nor requested JSON tool calls succeed. Supplied simulated tool results are not interpreted correctly. No MCP interoperability claim follows from this test.
- **Termination:**254 replies end normally;46 hit the128-token ceiling. Normal stopping is separate from a correct answer.
- Example: “What color is the bag?” receives “The main idea is most important; however, there may be more than one main idea in a single story.”

## Evidence and interpretation

- [All 100 transcripts](current-model-100-transcripts.md) preserve every generated reply. Full token IDs, timing and context hashes remain in `data/current-model-100-conversations-v1/turns.jsonl`.
- `configs/current-model-100-conversations-v1.json` fixes the cases, per-turn success criteria, checkpoint and rubric before execution. `reports/current-model-100-conversations-assessment.json` records every conversation judgment and category score. The integrity report reconstructs all300 contexts and token-decoded replies and checks the readable transcript. Three negative controls reject rehashed altered histories, token/text mismatches and incomplete runs; the originals remain unchanged.
- Every prompt/reply pair was inspected; all29 distinct replies were read in full, with repeated replies reviewed through exact-text mappings. Judgments are delegated expert review, not human attestation. Structural checks do not establish semantic success.
- This is a development suite with ten parameterized cases per category, not100 randomly sampled real users or a population accuracy estimate. Fixed follow-ups are not adaptive interviews. Explicit sexual dialogue, CUDA and learned MCP operation are unassessed. Some templated prompts have minor article/plural inflections; failure also occurs on straightforward grammatical prompts and explicit copying.
- The earlier eight-turn10/100 score uses different prompts and a different generation cap;7.6/100 is not evidence of a newly caused regression. Weights are unchanged. The observed collapse does not by itself establish its training cause.

## Decision before further training

- Keep this checkpoint as a failed baseline; do not promote it as a conversational assistant.
- Protect these evaluation requests and responses from future training admission. Add their request identities to intake contamination controls before acquiring/admitting the next training population; this evaluation does not retroactively certify existing data isolation.
- Next learning work needs broader English training and held-out learning checks, followed by instruction/conversation learning. Repeating the small fitting control or adding product data cannot be assumed to fix this behavior.
- No new training, teacher call, paid resource or cloud spend occurred. The separately authorized USD50 main-training envelope retains all data/runtime/portability/cleanup gates. The full project remains incomplete.
