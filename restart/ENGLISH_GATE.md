# English gate v1 — frozen specification, not a capability claim

Owner: Navneet Prabhakar. Date: 2026-10-21. Status: DESIGN ONLY.
Every row below must pass. Good loss cannot compensate for failed language tests.
No model has been initialized or evaluated against this specification.

## Sets and custody

- Development set and sealed acceptance set have the same task counts but disjoint documents, authors/templates, entities and minimal-pair families. Development cases are reusable; acceptance is one final evaluation per frozen candidate. Never describe reused development/acceptance items as fresh.
- Existing local evaluation artifacts, old test outputs, official TinyStories validations, UltraChat upstream test, SQuAD dev, public prompts and historical review examples are protected/excluded from training, tokenizer fitting and mixture tuning. They are diagnostic material, not a fresh acceptance set.
- Before any approved training, materialize the complete new acceptance set, gold labels, family IDs, scoring code and baseline protocol; hash and freeze them. Independent custody outside training paths is required. The set does not exist yet: this document freezes task design and thresholds, not a fictitious sealed dataset. Public examples below belong only to development.
- For prose loss: freeze 1,000,000 target tokens per domain (narrative, real web prose, synthetic expository prose), selected by document family, with at least 500 families/domain and 2,000 total documents. If eligible heldout material cannot supply this, do not silently lower counts: revise the spec before training. Keep a separate development loss sample of the same size. Counts refer to the final accepted tokenizer.
- Do not author/change acceptance cases after examining model outputs. Model selection uses development only. A failed acceptance attempt stays recorded; a later attempt requires a new sealed set and a new approval, not repeated tuning against the old set.

## Tests and exact passing criteria

| Test | Size and scoring | Pass threshold |
|---|---|---|
| Tokenizer integrity | 10,000 fixed strings spanning English, punctuation, whitespace, names, numbers, Unicode, emoji and literal role/tool strings | Exact UTF-8 encode/decode roundtrip on 100%; zero unknowns, dropped bytes, content-to-control ID collisions or silent truncations. Unpaired surrogates must explicitly reject. |
| Tokenizer fitness | 4,000 family-heldout English documents, 1,000/domain: narrative, ordinary prose, technical prose, dialogue; whitespace-word denominator fixed | Median tokens/word <=1.6 and p95 <=2.5 in each domain; total UTF-8 bytes/content-token >=3.0. Compression alone cannot waive integrity. This is acceptance of a proposed tokenizer, not its measured result. |
| Computation correctness | 40 fixed toy/edge cases: causal masking, shifted targets, EOS/PAD loss masks, packed boundaries, tied embedding, save/reload, precision and continuation | 40/40. Future logit changes <=1e-5 under same backend FP32 save/reload; masked/future perturbations change allowed logits <=1e-5; reference loss difference <=1e-5; finite gradients; repeated identical-batch 20-update toy fit reduces loss >=50%. These future updates count in the approved feasibility budget. |
| Heldout next-token loss | 3M targets above. Compare same-tokenizer training-only add-alpha unigram and interpolated modified-Kneser-Ney 5-gram baselines; smoothing/interpolation selected on development only | Aggregate mean NLL <=90% of the better baseline's NLL; each domain <=95% of its better baseline. Paired bootstrap over document families, 10,000 resamples, 95% CI must exclude zero gain overall and per domain. Also report bits/UTF-8-byte; no cross-tokenizer raw-perplexity comparisons. |
| Grammar | 400 minimal-pair continuations: 100 each subject/verb agreement, tense/sequence, pronoun/case, determiner/number. Score conditional log probability of full continuations with equal-token-length alternatives; ties fail | >=360/400 correct; >=85/100 in every subtype. Balance correct-answer positions and lexical alternatives. No imperatives or chat roles. |
| Unseen paragraph continuation | 200 prefixes, 40–100 words, five equally sized domains: daily life, narrative, factual exposition, dialogue-in-prose, instructions-as-prose. Generate 80–120 words with fixed temperature .7, top-p .9, one seed/item; EOS below 40 words fails | >=160/200 fully acceptable; >=28/40 in each domain. Rubric below. Also report deterministic greedy outputs on the same prefixes as diagnostics; no best-of sampling. |
| Passage-grounded comprehension | 300 short unseen passages, 100 each explicit fact, local inference, absent-information/contradiction. Four completion alternatives, balanced answer locations, equal-token-length alternatives. No outside facts needed | >=225/300; >=70/100 each subtype. Ties fail. Report shuffled/empty-passage control; intact passages must improve accuracy by >=15 percentage points over each control. |
| Basic relations | 500 items, 100 each negation, reference resolution, before/after, spatial/ordering, ownership/simple relations. Four alternatives, chance 25%, full-continuation scoring | >=400/500; >=75/100 in every subtype. Ties fail. No arithmetic beyond short sequences and comparisons. |
| Paraphrase and family robustness | 200 pairs (400 prompts): 50 each grammar, comprehension, reference, relations; new templates/entities and source families, human checked equivalent labels | Both variants correct on >=150/200 pairs and >=35/50 per category. Identical wrong choices do not count as consistent success. |
| Degeneration | Same 200 sampled paragraph outputs, tokenization fixed; count repeated 4-word grams and repeated sentences; independent greedy diagnostics retained | <=10/200 outputs have >20% repeated 4-gram occurrences after the first occurrence; <=4/200 contain any sentence repeated >=3 times. These outputs also count against paragraph success. |
| Memorization | 200 training-prefix probes, one prefix/family (first 32 content tokens; next 64 tokens withheld from prompt); 200 matched heldout-prefix controls. Evaluate fixed greedy output; exclude common formulaic boilerplate under a frozen rule | <=10/200 training probes exactly reproduce the full next 64 tokens AND train/control exact-copy-rate difference <=5 percentage points. Report longest exact matches, not only rates. |
| Leakage | Full accepted corpus vs all evaluation sets and their known ancestors, exact normalized hashes, family graph and near similarity | Zero cross-split exact duplicates, zero known same-family edges, zero confirmed near-duplicate pairs at 5-word-shingle Jaccard >=.8. Quarantine connected families; any newly discovered leak invalidates affected acceptance results. Audit 100 random nearest cross-split candidate pairs manually; 0 confirmed leakage. Document candidate-retrieval recall limitations. |

Baseline implementations must be verified on toy distributions before training. No numeric initial/random-model baseline is required during this design session. Future random-init loss is a correctness diagnostic only.

## Human grading rubric

For every paragraph, two blinded human graders independently score grammar, topical continuity, reference/entity consistency, causal/temporal consistency and local coherence, each 0/1/2:

- 0: major failure that changes meaning or makes the continuation hard to follow.
- 1: understandable with a minor error, awkward transition, or weak connection.
- 2: clear, consistent and natural for the prefix's register.

Fully acceptable means total >=8/10, no dimension 0, no contradiction of a stated premise, no incoherent sentence and no degeneration failure. Early EOS/empty/failed generation counts as failure. A human adjudicates disagreements without seeing candidate identity; unresolved cases fail. Publish both original grades, adjudication, agreement rate and Cohen's kappa. If kappa <.6, the gate is inconclusive until rubric ambiguity is resolved on development examples and the acceptance grading repeated blind. No teacher rewrites, repaired outputs, selected continuations or substituted answers.

Report overall and per-category denominators, exact counts, Wilson 95% intervals for accuracies, family-bootstrap intervals for loss, raw logits/scores for alternatives, prompt bytes, candidate hashes, decoding settings/seeds and **every raw generation**. Thresholds use observed counts plus the stated loss CI rule; intervals do not replace specified count thresholds. Record all missing/error cases as failures.

## Public development examples

- Agreement: `The key to the cabinets` → ` is missing.` vs ` are missing.` Verify token-length equality after the tokenizer is frozen; otherwise replace the pair before sealing.
- Negation: `Riya put the red cup in the box. The blue cup stayed outside. The cup that was not in the box was` → ` blue.` vs other color alternatives.
- Reference: `Maya lent Noor a book. Noor returned it on Friday. The person who returned the book was` → ` Noor.`
- Sequence: `The bell rang after the door opened. The earlier event was` → ` the door opening.`
- Grounding: `Asha left a note saying the bus would arrive at six. She waited under the clock. According to the note, the arrival time was` → ` six.` Include a changed-time counterfactual and a missing-time variant.
- Paragraph: `Ishan found a wet umbrella beside the classroom door. Its handle carried a label with Tara's name. He had seen Tara leave without it ten minutes earlier.` Continue the prose; do not ask an untrained base model to obey a chat instruction.

Alternative scoring sums only continuation log probabilities given the passage/prefix. Equal-token-length choices and counterbalanced lexical contrasts prevent simple length/answer-position bias. The full context is provided once, inside the model's window. Question/answer formatting is introduced only through natural textual continuations that also occur in prose; no role tokens or instruction obedience are prerequisites. Factual correctness here means consistency with the supplied passage, not encyclopedic knowledge.

## Later stages

- Conversation is prohibited until every English row passes. A failed gate means stop and diagnose; it does not authorize expanding a budget or silently lowering thresholds.
- Separate future conversation gate: freeze 100 unseen conversations of exactly 8 scored user turns (800 turns), covering 20 conversations each everyday exchange, passage-grounded QA, multi-turn reference, constrained response and uncertainty/clarification. >=600/800 turns must be fully correct; >=112/160 per category. Fully correct requires every applicable content, grounding, context and explicit instruction criterion to pass; partial credit does not count. Report 0–8 correct turns and whole-conversation success (all 8 fully correct) separately. Proposed additional floor: >=40/100 whole conversations. Forge's stated 75% turn target is retained; the whole-conversation floor is a proposed design choice, not a previously approved target.
- Tool training starts only after conversation passes. Its future gate needs separate frozen argument/schema correctness, tool selection, side-effect authorization and result-grounding cases; do not reuse English/conversation success as evidence for tool safety or correctness. No conversation/tool training or data creation is authorized now.
