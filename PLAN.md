# Current plan — 31 October 2026

## Objective and boundary

Build a random-initialized English conversation model below 1B parameters with reliable bounded tool use. The current candidate is 97.5M parameters. Work remains laptop-only; no cloud spending or paid teacher APIs. All existing runs are stopped for review. This plan does not authorize another run.

## Requirement versus evidence

| Requirement | Current evidence | Remaining gap |
|---|---|---|
| From-scratch base below 1B | 97,536,768 parameters; fresh tokenizer and weights | Met for current architecture |
| Useful English conversation | Chat quality review pending; 9.82% test repeated four-grams | Coherence, relevance, completeness and factuality unproven |
| Correct single tool execution and answer | 122/200 V3 test cases | 39% fail; templated fixtures only |
| Short tool workflows | 103/150 V3 test cases | 31.3% fail; limited routes |
| Clarification and failure handling | Accepted clarification 150/150; errors 100/100 | Template generalization and natural language coverage |
| Laptop stability | Sequential runs completed with 256MiB MLX cache cap | Keep resource guards; do not reintroduce concurrent GPU jobs |
| No paid compute | USD0 cloud/API spend | Electricity/time unmeasured |

## Next proposed experiment: decoding only

Research supports trying nucleus sampling, phrase-level control, and ultimately training against unwanted repetitions. Our completed sweep shows global penalty increases hurt tool chains. Research results are hypotheses for this model, not guaranteed improvements.

1. Review current chat outputs and label unwanted loops separately from required repetition, quotations and copied values.
2. Independently compare baseline against prose-only penalty 1.3, prose nucleus sampling (temperature 0.7/top-p 0.9, three seeds), and longer-phrase or sentence-repeat control.
3. Preserve deterministic tool decoding. Choose behavior from actual protocol state; never use evaluation category labels to choose a decoder. Include mixed prose/tool transitions and repeated JSON values.
4. Report repetition, blinded coherence/relevance/completeness, instruction compliance, EOS/caps/empty answers, strict tool scores, latency and memory. Keep raw outputs, including failures.
5. Select on development cases only; reserve newly authored independent cases for confirmation. Previously inspected test cases remain regression evidence.

Proposed target: at least 50% less unwanted repetition with no material blinded chat-quality loss and existing tool regression limits (at most 2 percentage points). These are development gates, not statistically established equivalence or release acceptance.

Planning estimate: 3–6 hours for implementation, checks and laptop evaluation, plus human review. No job is launched by this document. No training is part of this proposal.

## If decoding is insufficient

Consider a separately authorized, bounded prose-only unlikelihood or DITTO loss experiment with tool and language replay. Do not penalize required repetition or structural JSON tokens. Compare against an equal-budget normal SFT control. Audit answer endings and target masks before treating all repetition as a loss-function problem.

Contrastive search is a later option: candidate evaluation and hidden-state handling add implementation and inference costs. More pretraining, larger models and teacher–student training require separate evidence and approval; no defensible end-to-end quality ETA exists yet.

## Longer-term direction

Improve and validate the shared base before teacher–student work. Later independent domain forks may target NCERT/CBSE IIT/NEET preparation, broader computer science, and a stretch internal-system Defender assistant. These require their own licensed data, domain evaluations and, for remediation, execution permissions and sandboxed testing. They are not current model capabilities or active jobs.

## Cost basis

The completed 100M pilot took about 11h22m. The two V3 2M-slot repair arms took about 15.7 and 20.6 active training minutes, excluding evaluation. The penalty sweep took about 32 minutes with the baseline reused. These workloads differ and cannot be extrapolated interchangeably. Earlier rental-price and large-token estimates in dated research reports are historical assumptions, not current quotes or approved budgets.

## Research references

- [Nucleus sampling and text degeneration](https://arxiv.org/abs/1904.09751)
- [N-gram blocking implementation and limitations](https://github.com/huggingface/blog/blob/main/how-to-generate.md)
- [Contrastive search](https://arxiv.org/abs/2202.06417)
- [Unlikelihood training](https://arxiv.org/abs/1908.04319)
- [DITTO sentence-loop training](https://arxiv.org/abs/2206.02369)
