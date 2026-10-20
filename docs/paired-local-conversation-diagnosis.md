# Local foundation versus corrected conversation assessment

Creator: Navneet Prabhakar

Date: 20 October 2026

## Decision

**No demonstrated conversation improvement.** Both endpoints fail all300requested turns across100three-turn conversations. The corrected checkpoint changes output patterns and increases repetition. Its heldout prose-loss improvement is real but does not establish an assistant. GCP authentication/execution remains on hold.

The owner subsequently requests continued conversation training toward70–75%correctness. The working target is **at least75%correct requested turns on unseen conversations**, with complete three-turn session success reported separately. Existing full-project gates and resource limits remain binding. This result is the failed baseline for that work, not completion of the training objective.

## Measured results

| Measure | Own foundation | Corrected local checkpoint |
|---|---:|---:|
| Successful conversations |0/100|0/100|
| Successful requested turns |0/300|0/300|
| Original five-dimension direct rubric /100 |4.95|5.00|
| Replies reaching128-token ceiling |167/300|256/300|
| Replies with the same normalized word8-gram appearing at least3times |130/300|258/300|
| Distinct exact replies |240|229|
| Actual generated tokens |25,263|35,875|

The0.05rubric difference is one additional unit of subjective coherence credit across100cases, **not meaningful capability improvement**. Understanding, relevance, instruction following and context/correction dimensions score zero under the requested tasks; isolated grammatical fragments earn the residual coherence credit. All ten categories have zero successful turns. Repetition counts are descriptive, not automated semantic judgments.

Foundation model manifest: `a55daf69c568081f68606848bd27a8be6de5c2a3642d2a01c648e7ac99d96792`. Corrected model manifest: `882e2891c1ed815765ddd562322b0bc6a4b6da5ab90bcf3388b1dbce64a5a912`. The corrected endpoint has33common+57resumed MLXupdates/719,648new prediction positions on the selected foundation lineage. Prior discarded trials remain counted separately; this assessment executes zero gradients.

These are newly measured foundation/corrected results. The older7.6/100score belongs to a different collapsed fitting-control branch and must not be substituted for either endpoint.

## All actual messages and responses

- [All100paired conversations in ten readable parts](balanced-versus-foundation-transcripts.md):600unedited actual replies.
- Local searchable side-by-side HTML: `data/balanced-versus-foundation-assessment-v1/comparison.html`.
- Original JSONL/session/model identities: `data/balanced-versus-foundation-assessment-v1/{foundation,corrected}`.
- Per-conversation direct judgments: `reports/paired-foundation-direct-assessment-v1.json` and `reports/paired-corrected-direct-assessment-v1.json`.

Example, conversation72: the original question is “How many days are in a week? Give a brief answer.” The next actual user turn asks “Can you answer the previous question in fewer than six words?” The full foundation reply is “The answer is a very interesting question.” The full corrected reply is “Yes, I can help you make a new friend.” followed by a newline. Both fail to answer seven.

## Why it fails: evidence and limits

1. **The foundation already fails.** It cannot reliably greet, extract a supplied color, copy an explicitly supplied answer or recall a day. New prose continuation did not create the original failure. Severe undertraining and the original narrow dialogue distribution remain leading explanations: the foundation selected chain saw10,223,491positions for80,765,440parameters. This comparison does not isolate the optimal architecture, learning rate or required training exposure.
2. **The correction trained text continuation, not conversation.** A complete read-only audit of all706selected corrected batches/719,648targets finds2,167EOS targets and zero user, assistant or message-end targets. This is normal plain-prose pretraining framing, not a discovered serialization bug. It explains why a prose-loss gate cannot certify user-to-assistant answering. The later conversation phase was conditional and has not happened.
3. **Observable distribution drift without task gains.** Foundation word/definition/generic-advice loops often become corrected children's-story/color/identity loops. The correction's balanced sources include narrative prose. This is consistent with adapting surface distribution, but selected families/order/weights also changed, so do not attribute the result exclusively to stories or claim an isolated forgetting experiment.
4. **Free generation degenerates.** Corrected replies double the measured repetition incidence and hit the generation ceiling more often. Generic politeness or a word associated with the input does not count as completing the request. Simply allowing longer replies is not a demonstrated fix.
5. **A targeted cache check agrees.** Uncached full-prefix greedy decoding exactly matches all20sampled cached prefixes, up to16tokens each: one first-turn prompt per category/model. Every600recorded user history, token decode, prompt length and stop reason passes reconstruction. This weakens a cache-only explanation for these early failures; it is not a complete numerical-gradient/backend audit.
6. **Conversation supervision is still insufficient.** The earlier180considered teacher candidates have2,890supervised targets across20template families and are not a broad admitted SFT population. Existing failed950-dialogue and12-dialogue experiments cannot justify another tiny memorization loop. The new80teacher-call allowance remains unused.

## Required training changes

- **Replace automatic promotion by prose loss with separate capability gates:** plain-English continuation, grounded instruction following, then multi-turn context/corrections. Measure free-generated outputs at each gate. Retain existing loss/retention thresholds; add relevant behavioral evidence rather than weakening them.
- **Prepare a broad conversation curriculum suited to a small model:** short, complete user/assistant exchanges; direct answers; everyday dialogue; transformations and grounded text comprehension; varied situations rather than parameter changes to a few templates. Train actual assistant targets with correct role/message-end framing and full preceding user context. Preserve a disjoint language-retention pool.
- **Use genuinely new data and unseen evaluation families.** Do not train on this100-case suite, its generated replies or reworded/parameter-swapped copies. Preserve upstream validation and source-family splits. The repeated visible suite remains a regression test; freeze separate acceptance cases before training.
- **Use the authorized teacher for breadth and feedback only through the bounded serial CLI route, with source/account/category evidence and admission intact.** Do not present teacher quality as student improvement. Public small-model-oriented conversation sources are candidates, not automatically admitted rows.
- **Run bounded local iterations with predeclared exposure, optimizer transition and semantic validation.** Retain each failed checkpoint; select by unseen generated task correctness, not training loss. The75%target is an acceptance condition, not a promise that this81Mmodel reaches it inside the current budget.
- **Keep original resource limits:**100Mnewphysicalpositions includingdiscarded work;2Mpreliminary/78Mlanguage/20MconditionalSFT reservations; no hidden replay or budget resets. No GCP while the owner hold is active. The prepared68.6Mprose run is not a demonstrated conversation solution and must not launch automatically.

## Validation and limitations

Two complete actual MLXruns:100independent sessions each, three turns per session, greedy decoding,128newtokens per reply, no system prompt, no truncation/teacher/retrieval/repair/tool execution. Each endpoint receives its own previous generated replies; later histories therefore differ legitimately. All600raw replies are published and read during direct expert review, using lossless exact-repeat rendering and verified mappings for identical replies. Human attestation is false; judgments are unblinded.

All600Markdown/HTMLreplies and300displayed paired user messages are re-read and exactly matched to raw captures. Model/protocol/runtime inputs are hashed before/after. Zero new gradients, teacher calls or cloud commands occur. The suite has ten parameterized cases in each category; it is not a random population benchmark, fresh final test or causal isolation of one recipe variable.
