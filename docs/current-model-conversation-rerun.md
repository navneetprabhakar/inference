# Fresh conversation reassessment: no improvement

Creator: Navneet Prabhakar

Date: 19 October 2026

- **No conversational improvement is observed.** A fresh execution of all100 three-turn conversations produces exactly the same300 token sequences, texts, raw histories and stop decisions as the previous assessment.
- **0/100 conversations succeed;0/300 requested tasks succeed.** The same rubric score is **7.6/100**, entirely from limited grammatical coherence. Understanding, relevance, instruction following and correction/context handling remain zero.
- Recent jobs have prepared and grouped data. They have not updated student weights. The local near-duplicate job continues separately; no new training or GCP resource is running under this assessment.

## Exact comparison

| Measure | Previous run | Fresh run |
| --- | ---: | ---: |
| Successful conversations | 0/100 | 0/100 |
| Successful requested turns | 0/300 | 0/300 |
| Rubric score | 7.6/100 | 7.6/100 |
| Distinct replies | 29 | 29 |
| Normal stops | 254 | 254 |
| Replies reaching128-token cap | 46 | 46 |
| Generated tokens, including stops | 14,115 | 14,115 |

This tests the latest trained fitting-control checkpoint, model manifest `b67af6576b40fc42504db9672499f2a183bea18c2e0a59c9c5eb2b15ee5dc747`, with the same16KBPE, MLX greedy decoding,128-token reply cap and original fixed protocol. Each conversation starts with empty history; actual generated assistant text is retained within its three turns. No cached reply file, teacher, retrieval, repair, real tool execution or gradients are used for generation.

Fresh raw outputs/session/completion receipts are retained separately in `data/current-model-100-conversations-rerun-v1`. The [existing readable transcripts](current-model-100-transcripts.md) also reproduce every fresh reply exactly; no duplicate transcript is substituted for actual execution.

## Directly visible failures

- User: “Correction: my name is Arun. Reply with only my corrected name.” Model: “Sorry, I still do not understand your request. It seems like a collection of random letters. Can you try again?”
- User: “Mira has a blue bag. What color is the bag? Return only the color.” Model gives the same unrelated story-main-idea sentence as before.
- An explicit weather-tool schema and requested city produce a stock clarification instead of the requested JSON.

All29distinct fresh replies were reread. Collapse remains dominated by stock clarifications, unrelated story/car advice and looping antonym lists. The original review of each prompt/response pair remains applicable because all300 requests, contexts, generated tokens and decoded texts match. Conversation-level judgments are bound to the new raw row hashes and their original judgment hashes. This score mapping is disclosed; it is not a new blind independent grade or an unseen benchmark.

## Validation and decision

- The unchanged full-history/token-decoding checker reconstructs all300 fresh turns and verifies their model/tokenizer bindings, generated IDs, stops and readable text. Comparison checks all300 histories/texts/token sequences before allowing prior grades to map to the new rows.
- Five focused negative-control tests pass: a nonterminal run, incomplete turns, altered text, altered token IDs and altered history each refuse grade transfer. Original evidence remains unchanged.
- This rerun introduces no new evaluation text beyond the already protected suite/replies. Existing exclusion inventory remains applicable. Exact reproducibility does not demonstrate broad English, tool/MCP capability or any training improvement.
- Keep this checkpoint as a failed baseline. Continue the corrected plan from the separate own foundation checkpoint; do not continue the overfit control branch. The next actual training phase still requires finished grouping, finite admission and executable learning/portability/resource contracts.
- Report future data engineering and model-quality results separately. A new checkpoint must pass measured language-learning gates and then conversation/SFT gates before capability progress is claimed. Repeated calls to unchanged weights cannot establish improvement from data preparation.

Evidence: `reports/current-model-conversation-rerun-assessment.json`, its integrity report, `reports/conversation-rerun-comparison-tests.xml` and frozen rerun configuration/wrapper. No student update, teacher call or cloud spend occurred. Full objective remains active and incomplete.
