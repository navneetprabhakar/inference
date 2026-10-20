# Local grounded conversation correction

Creator: Navneet Prabhakar

The owner requires continued local training toward at least75%correct requested turns on unseen100three-turn conversations, with full-session success separate. GCP authentication/execution remains forbidden. The first SFT attempt is rejected:0/300correct turns on both its existing regression and harder source-heldout diagnostic, with language retention failures. All failed work/checkpoints and physical charges remain preserved.

This new experiment tests a narrower prerequisite: answer human-written questions from a supplied passage across three turns. It cannot certify broad English conversation merely by passing grounded QA. No teacher, retrieval, repair, public service or cloud execution is involved.

## Source and review

Pinned SQuAD1.1 revision`eee5fdbf62f8613a7812b03419e6b29617b74fd1` retains all original passages, human questions and answer offsets. The [source page](https://rajpurkar.github.io/SQuAD-explorer/) labels the dataset CC BY-SA4.0; the code license is separate. Dataset/research attribution: Pranav Rajpurkar, Jian Zhang, Konstantin Lopyrev and Percy Liang, [SQuAD:100,000+ Questions for Machine Comprehension of Text](https://nlp.stanford.edu/pubs/rajpurkar2016squad.pdf),2016; original passages are Wikipedia-derived. This is an explicit bounded private research admission, not distribution/licensing clearance. Source assertions remain supplied historical context, not independently certified current facts.

The complete original QA article/context grouping is reused. Whole prior evaluation sequences and all44,429earlier Smol intake dialogues, plus68older protected Smol rows, are checked against the QA context index. Thirty-four article components are withheld by prior-source/evaluation protection. Two hundred whole article components are frozen for100development and100reserved conversations before train review or gradients; reserved capture remains disabled. Other paragraphs in each heldout article component never train.

Three original question IDs per unique paragraph are selected by fixed hash before screening. The first request supplies the complete passage; later requests refer back to it. Each training unit contains the full three-turn dialogue, with original short answer spans as targets. There are no separately replayed question variants or truncated passages. All qualifying language windows are checked. Exact/full17-of20shingle protection is not a semantic/paraphrase-family guarantee.

Direct review reads64complete train-article dialogues/all192question-answer pairs:52considerations and12exclusions,18.75%nonapproval under the unchanged25%ceiling. Observed defects include contradictory chronology, country/city confusion, wrong quantities, incomplete technical answers and mislabeled temporal questions. Whole negative article components are withheld. Most other paragraphs remain unread; category`unreviewed`, human attestation false, no SFW claim.

## Frozen finite experiment

-4,096unique paragraph dialogues from192article components;12,288assistant replies per pass. All original contexts/questions/answer spans and4,096numeric role masks independently reconstruct.
- Explicitly reallocate128whole previously untouched language-retention families,64general/64narrative. Verify all57,698replay next-token pairs. Preserve the original pool; new sidecar leaves2,561untouched families. Old overlapping replay pools are not used.
- Exactly two finite passes of each QA/replay batch:2,595,406physical positions/286,562supervised targets, at most520optimizer updates. QA contributes59.73%of supervised targets; replay contributes40.27%. Every consumed physical position, including prose and discarded work, counts under conditionalSFT.
- Start from preserved corrected90step model`882e2891c1ed815765ddd562322b0bc6a4b6da5ab90bcf3388b1dbce64a5a912`, explicit fresh AdamW moments/counters. LR0.00003,65,536position warmup, accumulation16; original FP32, dense-onehot embedding, loss, betas, epsilon, clipping and decay remain unchanged.
- Bind201inputs in`configs/grounded-conversation-run-v1.json`, SHA`18e846202a789430fa31beca9a8df4d3b4bae2165a5d95f9c725992b9720a766`. Sum three distinct sealed raw gradient ledgers once:1,776,439prior positions;270,359already consumed conditionalSFT positions leave19,729,641. Planned cumulative recovery physical positions4,371,845.
- Local supervisor parent43488/child43493/session21964; owned caffeinate session72146ends with parent. Separate four-hour local deadline2026-10-20T16:25:37.105726Z. Original cloud reservation/deletion clocks remain unchanged. No automatic retry, exposure/budget refund or deadline reset.
- Check the unchanged500document language-retention gate every64updates and at terminal. Stop if either general or narrative regresses by more than0.1nat. Source exhaustion also stops training; never wrap implicitly. The replay selection is balanced by family count, not encoded positions:44,268general/13,431narrative encoded positions before the initial one-position shift. Its unequal source weight is an explicit limitation to inspect at the per-source guard.

Capture100initial grounded conversations before gradients, then100terminal grounded conversations and100existing-regression conversations. Each has three turns using its own actual student history. Grounded capture has64new tokens/reply; existing regression retains128. Publish all900actual replies and all user messages, directly grade semantic correctness, retain exact-match/F1 only as auxiliary measures. Source answer labels are fallible; report defects rather than repairing or silently dropping cases. No loss/preprocessing/test result is a conversation improvement claim.

Validation before launch:13focused reader/grouping/carried-budget tests pass; actual independent full-source/numeric/exposure audit passes. Training has terminated normally at finite two-pass exhaustion: 520 updates, 2,595,406 physical positions and 286,562 supervised targets. All charges are complete and all 201 pinned inputs remain unchanged. The exact terminal model is `24e92fbd56a81653958f211f7e9d26680b172a37d2b1a06bb76617c73fb2c393`. General language improves 0.006891 nats while narrative regresses 0.023723 nats; both satisfy the unchanged 0.1 per-source retention ceiling. The old mean-improvement test remains false and is not relabeled a retention failure. Reference NLL 6.518747→4.684432 is an objective measurement, not conversation acceptance. The training parent, child and owned caffeinate have exited. Full75%conversation target and full project remain unfinished.

## Separate everyday English development comparison

While the grounded run is active, freeze100authored everyday scenarios/300requests:20each comprehension, editing, practical writing, context updates and instructions. They require no specialist knowledge. All cases and order are preserved. A pre-capture review clarifies five third-turn self-check criteria so judgments describe actual earlier student replies, even when those replies failed. Originalv1 remains intact; v2protocolSHA925bd5c76ac688a05eef85a60f5de4d361e06b9444d866d227d7417afcf2cb7a. No case is removed based on a model score.

After the original900reply run is terminal/audited, a separate bounded source/terminal comparison can capture600additional replies on these same100scenarios, preserving the original local absolute deadline. No new gradients or source/terminal weight changes occur. Literal scenario first-request/complete-sequence17-of20near checks pass against prior prose/Smol/QA indices; The complete containment audit passes across329,395,187bytes/25,339original foundation train rows,104,483finite prose rows,1,226old SFT rows and4,096current QA rows:zero whole-request or short-context hits. The initial audit refuses three short requests before scanning; retainedv4uses complete contexts without relaxing the original minimum. Generic English skills recur; no semantic-family or random-population certification. This is new development evidence, not a fresh final test. All 1,500 combined actual replies and direct judgments must remain available. The original100regression and100harderSmoldiagnostic failures are not replaced or hidden.

## Interpreting the repeated failures

The preserved foundation already fails the paired100-conversation suite. Its selected chain has10,223,491training positions for80,765,440parameters; the corrected source adds719,648. The older12-row control fits train loss4.158→0.174and reproduces5/12final references, while validation loss worsens4.881→5.853and the actual eight-turn conversation still fails. See [the retained fitting control](milestone-sixty-six.md). These observations favor insufficient foundational exposure/distribution and missing robust answer conditioning; they do not isolate a single cause or universally validate all implementation details.

As research context, [Hoffmann et al.,2022](https://arxiv.org/abs/2203.15556) studied models from70Mparameters upward using5–500Btraining tokens. That is a different compute/loss study, not a minimum-token theorem or a75%conversation guarantee for this project. The current100Mnew-position budget and prepared68.6Mlanguage phase remain finite research envelopes. Neither is a defensible promise of a conversational score. Preserve the actual observed task scores as the decision evidence.


## Actual terminal results and decision

All five captures are complete: **1,500 actual user/reply pairs**, with reconstructed histories, exact token decodes and lossless Markdown/HTML publication. The same assistant directly read every reply and recorded unblinded semantic judgments; human attestation is false. Later turns are judged independently against actual history. No teacher, tool, retrieval or repaired answer substitutes for the student.

| Development protocol | Corrected source | After grounded/replay training | Complete sessions after training |
|---|---:|---:|---:|
| Original regression, 100 three-turn conversations | 0/300 | 0/300 | 0/100 |
| Human passage QA, 100 three-turn conversations | 0/300 | 3/300 (1%) | 0/100 |
| New everyday English, 100 three-turn conversations | 0/300 | 1/300 (0.33%) | 0/100 |

The older foundation also scored 0/300 on the original regression, as documented in the [paired foundation/corrected comparison](paired-local-conversation-diagnosis.md). It was not silently assigned a score on the different new everyday protocol. The first rejected SFT also remains 0/300 on its original regression and separate harder diagnostic. No model is promoted. The 75% target requires at least 225/300 correct turns on unseen acceptance families; current development evidence is far below that threshold.

[All 1,500 raw message/reply pairs](grounded-conversation-run-v1-transcripts.md), [direct score comparison](../reports/grounded-conversation-run-v1-direct-comparison.json), [capture reconstruction](../reports/grounded-conversation-run-v1-integrity.json), and [state/budget audit](../reports/grounded-conversation-run-v1-state-audit.json) are published. Ten split judgment files contain all 1,500 per-turn decisions, including the initial source QA; each direct-summary report links its two parts. The original mutable review worksheet provisionally accepted four QA answers; final full-passage adjudication records three fully correct and one partial. The Bermuda answer “the United States” omits the supplied Southern region. Both worksheets and the reason for the amendment remain preserved.

Actual latest everyday conversation 1:

| User message | Actual trained student reply |
|---|---|
| The cafe opens at noon on Sundays. On weekdays it opens at eight. Today is Sunday. When does it open today? | six |
| It is now ten in the morning. Is it open yet? | slate |
| Explain why in one short sentence. | six |

The one correct everyday reply is conversation 85, turn 3: “How many sentences did I originally request?” → “two”. Both earlier turns fail, but they do not automatically invalidate that correct current answer. No complete session succeeds. QA positives are 42.3, 64.1 and 67.1; auxiliary normalized exact match/F1 are separate from direct semantic correctness. Fallible source questions and annotations remain visible, without after-score filtering.

The clearest observed change is termination. On passage QA, length-capped replies drop 300→2 and 298 replies end with message-end; correctness is still only 3/300. On everyday English, capped replies drop 271→116, while only one requested turn succeeds. These format changes do not establish useful conversational improvement.

A separate forward-only diagnostic, with zero gradients and original human answer prefixes, separates answer-content from stop-token reference loss. Content NLL changes 7.168866→5.957622; structural NLL changes 4.697573→0.578549. Both improve numerically, with much stronger stop-token improvement; this is not causal proof or student-history task success. [Diagnostic](../reports/grounded-loss-components-v1.json). The actual 3/300 and 1/300 free-generation scores govern acceptance.

The training and capture parents and their owned caffeinate processes have exited; no local learner remains live. Current cumulative new recovery physical positions are **4,371,845** across four distinct raw ledgers. Conditional SFT has consumed 2,865,765 positions, leaving **17,134,235** under its unchanged 20M cap. Language remains 0/78M. Failed/discarded work remains charged; no pass, budget or existing clock resets. Latest future-intake exclusions retain all earlier protections and add all actual captures, QA heldout passages/references and core requests: 5,769 distinct normalized texts plus 981 complete short-text contexts. This literal protection is not a semantic-family certificate.

The repeated SFT results reject the current approach as a route demonstrated to reach 75%. Leading hypotheses are insufficient foundational language exposure and weak prompt/answer conditioning; objective/source mismatch and fallible data also contribute. The evidence does not prove that spending the remaining budget, using GCP or merely increasing training duration will reach the target. Stop repeating this exhausted QA source and retain the failed model for diagnosis.

The next proposed route is broader language learning followed by independently admitted conversation conditioning. [The local-only route proposal](../configs/local-language-recovery-route-proposal-v1.json) records **no authorization and no launch permission**. It proposes at most the existing finite 68,609,856 language positions, at most two physical passes per family and a separately authorized 24-hour local ceiling, approximately 19 training hours by rough observed throughput. Latest exclusions and all four raw ledgers must be reconciled before a new local plan or gradients; the old cloud main plan cannot run unchanged. A subsequent SFT stage remains conditional on new admission and its remaining 17,134,235-position cap. No 75% promise is made.

There is a genuine owner-input boundary: the earlier frozen main policy requires actual paired CUDA proof before the fresh main optimizer. GCP authentication/execution remains forbidden. The proposal therefore asks for an explicit exception to that prerequisite for an isolated local-only branch, with local state/inference validation and no portability claim. Original cloud contracts, deletion time and completed local clocks remain unchanged. Until that exception is given, no main training is launched. The project and the requested 75% result remain unfinished.
