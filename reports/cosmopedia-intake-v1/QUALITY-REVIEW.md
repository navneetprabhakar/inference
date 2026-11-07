# Cosmopedia first-shard quality review

**Useful prose exists, but this shard is not ready to become a clean language corpus wholesale.** All64 frozen full generated texts were read. Individual judgments: **15retain,32review,17hold**. These are subjective document judgments, not population defect rates: the sample deliberately spreads length quartiles and audience/format cells instead of sampling documents proportionally.

`manual-quality-judgments.json` binds each rowID/textSHA and explains every decision. The raw sample remains unchanged in `data/cosmopedia-intake-v1/quality-sample.jsonl`. No new samples, exclusions, splits, corpus edits or admissions were made. No external factual verification was performed; uncertain specialist claims are marked review, not asserted false.

## Findings that matter for the next data decision

- **Eight of64 lack a complete usable ending/task:** five cut off mid-sentence/citation/code; one ends at a promised analysis heading; one recipe asks to continue before cooking; one Fibonacci story degenerates into repeated escaped underscores. The shortest quartile includes six of these cases. Selecting short text without checking completeness can preferentially retain generation failures.
- **Nine further holds have serious visible semantic/task defects.** Examples: row337525 teaches567−254=456; row46617 defines accuracy as consistency and precision as choosing the right twig size; row28595 calls5 the index ofsqrt5. These are direct textual errors, not merely unfamiliar advanced content. Row301815 calls a board with string-attached sticks a painting palette. Row215929 forces Shakespeare criticism into an unvalidated food-preservation recipe.
- **Audience labels are weak predictors of suitability.** Young-child rows include finite-difference seismology, radical algebra, chemical nucleation and abstract cultural imperialism; some simplify well, some destroy the concept. College/researcher labels often introduce fabricated-looking scholarship, unverified exact citations, medical/legal detail or missing earlier-course context.
- **32review is not32proven-bad.** Many are fluent complete texts with unresolved factual detail, overly broad claims, practical-instruction uncertainty or unsuitable complexity. Do not convert that category into a blanket source ban. Fictional characters, magic and sadness are not automatic errors. Distinguish fictional scenes from pedagogical assertions embedded inside them.
- **The shard is far broader than TinyStories, but stylistically repetitive.** Many texts use the same welcome/course/conclusion framing, first-person Reddit-style anecdotes, or alien/zero-experience procedural padding. Internal duplicate detection does not measure this semantic/style repetition.
- **Pretraining prose is not conversation/tool supervision.** Two retained Alice/Bob dialogues have meaningful follow-ups, but neither uses our user/assistant/tool protocol or executed observations. WikiHow instructions describing taps do not constitute verified tool calls. Do not infer assistant competence from the raw token yield.

## Useful lanes, with limits

- Retained coherent simple explanations include reflective writing(row150584), superheroes/found-family activities(row210601), and macrame dialogue(row236837). Earthquake simulation(row290934), coaching feedback(row333331) and media representation(row86120) have coherent explanatory structure but intermediate vocabulary, despite some young-child labels.
- Retained narrative examples include everyday purpose/dialogue(row328383), toy-rescue planning(row332620), recycling fable(row159473) and education-reform fiction(row225552). They provide richer discourse than slot drills; they do not establish factual or compositional generalization.
- Some coherent advanced surveys were retained as prose candidates, not recommendations for a simple-language-first mixture. The15retains must not be counted as15simple expository successes. Likewise selecting only those observed15for training would create a tiny review-conditioned set, not a source quality guarantee.
- The academic/clinical/legal/how-to lanes require a different standard from storylike or low-stakes conceptual prose. Exact citation strings and polished terminology are not proof. No specialist claim was newly fact-checked in this reading.

## Recommended next boundary

Before using this shard, prospectively specify a **new complete-document candidate policy** addressing obvious unfinished endings, unmatched fences, placeholder/degenerate runs and broad source-task suitability. Preserve the frozen raw intake and this sample. Report exclusions by reason, inspect a fresh independently frozen sample only if root authorizes it, and retain root custody/history/split protections. Do not claim punctuation filtering catches arithmetic or hallucinated definitions; it does not. Do not automatically reject every reviewed cohort or every fictional teaching text.

Intake reports376,289documents and275,579,989GPT2tokens including one prospectiveEOT/document, with541normalized duplicate groups. These are **raw inventory numbers**, not clean, novel, custody-cleared or admitted training tokens. The separate exhaustive verifier checks byte/row/token/sample integrity; its PASS would not change these semantic limitations.

This evidence supports evaluating a narrowly specified mixed-prose candidate rather than abandoning Cosmopedia outright or replacing all learning with31Mstories. It does not yet support a fixed number of clean Cosmopedia targets, a deployment ETA or a claim of conversational improvement.
