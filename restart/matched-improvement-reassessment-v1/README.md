# Matched reassessment: improvement and regressions, decision deferred

**The broader candidate has made measurable progress.** That progress coexists with regressions and limited transfer to unfamiliar values and phrasing. The earlier positive report and later harder-conversation report remain valid evidence about different scopes; neither is discarded. This assessment makes no checkpoint acceptance/rejection decision.

The previous summary was too categorical in moving from poor fresh-conversation results to an overall model conclusion. That test changed vocabulary, wording and conversation demands together and included quantities outside the immediately preceding controlled curriculum. It showed a transfer gap; it did not isolate net learning progress. This assessment compares the same new items across all three checkpoints.

## Main comparison

120 matched cases per checkpoint: 104 single-turn tasks and 16 three-turn conversations, yielding 152 generated answers each. Original foundation, short-answer child and broader candidate used identical user banks, native chat serialization and full-vocabulary greedy decoding. All 456 generated answers were directly reviewed by the primary agent.

| Descriptive measure | Original foundation | Short-answer child | Broader candidate |
| --- | ---: | ---: | ---: |
| Exact complete reference answers, normalized for case/punctuation | 0/152 | **25/152** | **56/152** |
| Semantically correct content/task response, format scored separately | 0/152 | **33/152** | **66/152** |
| EOS endings | 0/152 | 152/152 | 152/152 |
| Fully factually correct three-turn conversations | 0/16 | **1/16** | **6/16** |

These totals describe this balanced diagnostic bank, not population factual accuracy or an independent benchmark. The semantic total includes one correctly fulfilled clarification task and must not be labelled a pure world-knowledge score. The original foundation had not undergone the chat-format training; its comparison measures the combined effect of instruction conditioning and task learning, not isolated changes to base English knowledge.

On identical items, the broader candidate gained **43 exact answers and lost 12**, a net gain of 31. Semantic-content scoring found **39 gains and six losses**, a net gain of 33. This is a within-bank descriptive comparison, without a significance or causal-generalization claim. Improvement remains visible under strict scoring and does not depend on lenient semantic judgments.

## Where progress is measurable

| Task | Short-answer child | Broader candidate | Scoring |
| --- | ---: | ---: | --- |
| Full location copying | 0/16 | **9/16** | Exact complete phrase |
| Full location content | 0/16 | **11/16** | Correct relation and unambiguous referent |
| Complete factual sentences | 0/16 | **8/16** | Exact sentence |
| Missing-owner abstention | 0/8 | **8/8** | Correct Unknown answer |
| Clarification | 0/8 | **1/8** | Relevant grammatical question |
| History answers across all three turns | 17/48 | **31/48** | Factual content |
| Corrected-fact recall after distraction | 1/16 | **6/16** | Factual content |

Sentence realization is an instruction/format gain as well as a small content gain: the short-answer child conveyed correct color values on 8/16 sentence tasks but never formed the requested full sentence. The broader candidate conveyed correct color content on 10/16 and formed the exact sentence on eight. Those gains should not be erased by a stricter output-format score or inflated into general factual competence.

Two location answers identified the correct unique cabinet and spatial relation while omitting its color adjective; one repeated the noun. They count for factual content but fail exact full-phrase/fluency requirements. Complete identity components without the full name, or a landmark without the spatial relation, are partial only and do not count as complete factual answers. Correct content with unrelated extra claims is not accepted.

The candidate produced six incomplete but correct full-name components, versus none from the short-answer child on those name tasks. These are recorded as partial progress, not full owner-identity correctness. Likewise, clock-shaped output became more common but exact times remained wrong; surface structure is not factual accuracy.

## Where regressions and limits remain

- Exact color-only copying fell from **8/16 to 5/16**. Four known-color answers under the new wording lost correct factual content; one new color was copied correctly under familiar wording. The newer candidate sometimes produces sentence fragments where a color word is requested.
- Complete owner names and exact times remained **0/16 each** on the copying grid. More recognizable output forms and partial name components do not satisfy those tasks.
- Missing-owner abstention improved, but supplied full owners remained **0/8 correct** under both checkpoints. This establishes learned abstention behavior, not calibrated answerability.
- Recall gains were concentrated in familiar wording: **0/8 to 5/8**. Under novel wording, recall stayed **1/8 to 1/8**. The aggregate 1/16 to 6/16 gain is real on this bank, but robust memory transfer is not established.

## Matched vocabulary and wording grid

Copying holds four shared entities fixed and crosses known/novel value strings with familiar/novel wording, separately for color, location, full owner name and time. Known strings appear in the actually consumed broader SFT stream; novel complete strings do not. This does not mean their component tokens were unseen in pretraining or that the checkpoints had equal prior exposure.

| Copying stratum | Short-answer: content / exact | Broader: content / exact |
| --- | ---: | ---: |
| Known values, familiar wording | 4/16 / 4/16 | **8/16 / 8/16** |
| Known values, novel wording | 4/16 / 4/16 | **4/16 / 4/16** |
| Novel values, familiar wording | 0/16 / 0/16 | **2/16 / 1/16** |
| Novel values, novel wording | 0/16 / 0/16 | **2/16 / 1/16** |

The unchanged aggregate in the known-value/new-wording cell hides offsetting changes: full-location gains and color-only losses. Looking only at the total would miss both. Across the two novel-value cells, content improved from 0/32 to 4/32, while exact answers improved from 0/32 to 2/32. Transfer beyond the task vocabulary remains limited; it is not zero improvement.

The separate history bank uses familiar value vocabularies and actual model-generated previous replies. It distinguishes immediate updating from later recall but is not a pure causal manipulation of history length: corrections, distractions and generated-answer errors also differ. The primary one-turn grid is the cleaner wording/value comparison.

## Relationship to previous reports and decision

- The controlled 77/80 retained result and the broader trial's gains remain evidence of learned skills.
- The previous fresh 3/60 and 6/60 grounded-conversation results, and 1/15 and 0/15 basic-fact results, remain evidence of poor performance on those harder scenarios. Those numbers are not replaced by this more controlled bank.
- The earlier 69/80 retention guard and measured 64/80 result remain in the historical training record. No training clock, threshold or stop was reset. This reassessment neither reverses that stop nor decides the model's next disposition.
- **Decision deferred, as requested.** No checkpoint is newly promoted or rejected by this assessment. The evidence supports measurable, uneven progress and specific unresolved deficits. It does not support either a blanket dismissal of the progress or a claim of general conversation readiness. No parameter-capacity verdict is made.

## Execution and integrity

- Same own 15,191,712 parameters and tokenizer. Three frozen source checkpoints, historical stop, engine, serializer, plans and private bank were hash-verified before and after inference. No weights, gradients, optimizer steps, model architecture or teacher calls changed.
- 120 cases / 152 answers per model; reference bank 3,871 native content tokens and 584 assistant reference tokens. Exact prompt overlap with seven checked local prior banks was zero. The bank is primary-authored and primary-judged, not independent/blind; exact overlap checks do not certify semantic independence or exclusion from every historic corpus.
- Familiar/novel wording uses one template per family, and value levels deliberately differ in SFT exposure and tokenization. Scenarios are correlated. No population accuracy, statistical ranking or isolated causal training-recipe effect is inferred.
- Greedy max 32 new tokens; stop BOS/EOS; actual generated history retained. The original foundation hit the output cap on all answers; the two trained children ended all 152 answers with EOS. Maximum actual input was 177 tokens, below the 256-token context. No input was truncated.
- **31.38 seconds, 342,432 inference positions; zero training updates.** Peak observed RSS 730,480,640 bytes (~0.68 GiB). Frozen bounds: 15 minutes, 2M positions, 12 GiB RSS/GPU, 1 GiB artifacts, 60 GiB disk floor. All assessment workers exited.
- Exact preparation source, raw heldout text and detailed case judgments remain local and hash-referenced. Public code and aggregate evidence are versioned. Model hashes are unchanged; no model-selection step occurred.

Evidence: [plan](plan.json), [data receipt](data-receipt.json), [execution result](result.json), [semantic and paired review](review.json), [integrity audit](audit.json).
