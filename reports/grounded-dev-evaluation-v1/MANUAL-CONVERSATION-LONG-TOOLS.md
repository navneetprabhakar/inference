# Grounded candidate: conversation and long-tool review

**Still unusable; no functional improvement on these unchanged corpora.** All49turns were read against original prompts/rubrics, raw frames and actual traces. Separate JSON overlay resolves24pending turn judgments as failures; raw results remain unchanged. This is one unblinded assistant review, not a blinded independent experiment.

| Measure | Prior SFT | Grounded SFT |
|---|---:|---:|
| Conversation full sessions / turns passed |0/12;0/25|0/12;0/25|
| Long-tool full sessions / turns passed |0/8;0/24|0/8;0/24|
| Conversation protocol-valid turns |20/25|24/25|
| Long-tool correct first calls |6/16|0/16|
| Long-tool actual executed calls |14|7|
| Long-tool protocol-failed turns, including closed sessions |3/24|7/24|

- **Relevance and grammar:** generic rewrite boilerplate has been replaced by fragments from the grounded curriculum: permissions, facilities, delivery, donated fabric and second operands. Several sentences are grammatical but answer another task; others splice incompatible clauses or repeat extensively. An invitation-shaped answer retains fabric-sorting content instead of the requested activity/day. This is surface-pattern acquisition, not demonstrated prompt understanding.
- **Facts, correction and clarification:** six exact-answer turns all fail; no successful supplied-fact recall, correction, usable rewrite/draft or coherent followup. The model asks for choice criteria already supplied and for a second operand in an ordinary book-labeling conversation. A partial uncertainty phrase about an unknown opening time cites irrelevant arrival, so it fails the unchanged rubric.
- **Observation honesty:** two conversation answers claim tool returns despite no calls. Long-tool outputs misread253.79166666666666 as737.79166666666666 or759.79166666666666,40774 as40759, and0.025283553875236297 as0.7182833333875236. Subsequent no-call answers repeat invented numbers.
- **Chaining:** none of16requested two-call turns performs both calls; no session reaches four. Calls use unrelated operands/operations. One answer exactly copies an unrelated result; two report the division-by-zero error they actually caused; one later proposal reuses the previous observed left operand. These are isolated subskills and do not meet complete-task rubrics. No automatic fidelity rate is inferred from the zero automated-readback denominator.
- **Session state:** all eight correction-without-recalculation turns fail, including three unavailable answers after protocol closure. No forbidden/unknown successful calls occur, but that does not establish relevance or correctness.

Do not deploy or simply repeat the narrow template curriculum. The next bounded diagnostic should distinguish inability to fit representative training programs from poor transfer to unused constructions, then assess prompt conditioning, slot binding and base-language competence. These outputs do not identify a unique causal explanation. Keep all unchanged development cases excluded from training; do not relax gates. Any longer language-learning intervention needs a concrete data/compute budget and actual behavioral comparison.
