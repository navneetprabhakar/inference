# Why basic conversation fails

Creator: Navneet Prabhakar

Date: 19 October 2026

## Decision

The latest checkpoint is a **memorization control on an inadequate language foundation**, not a trained conversational assistant. Preserve the failed results. Continue the next language phase from the project's own foundation checkpoint, not either SFT branch. Do not start training until the revised launch contract is executable.

## Findings ranked by evidence

| Finding | Evidence | Conclusion and limit |
| --- | --- | --- |
| Narrow-control overfitting | Train NLL4.158→0.174; validation4.881→5.853. In the100-conversation run,288/300 replies contain at least12 contiguous normalized words from the actual12 training dialogues. | Strong evidence of memorized response templates generalizing inappropriately. Overlap alone does not establish exclusive causation; these records can also occur in earlier data. |
| Failure already exists before that control | A new identical-prompt comparison on10 basic requests yields0/10 at the foundation,950-dialogue SFT and12-dialogue control endpoints. | The control's template collapse is not the whole explanation. Neither earlier checkpoint is a functioning chatbot to recover by merely undoing the control. |
| Too little and too narrow language learning | The81M model's selected foundation trajectory sees10,223,491 positions, approximately0.127 per parameter, from25,339 OpenAssistant/Dolly dialogue paths. There was no substantial diverse prose pretraining phase. | Leading underlying explanation: severe undertraining and inadequate language/task distribution. More pretraining is a testable intervention, not an isolated proof or a guaranteed cure. |
| Supervision loses context in the original foundation packing | Only78.3% of assistant content retains the full preceding user in its window;69.3% retains the full document prefix. | Real objective/data-quality limitation. Most context remains present; this alone does not explain failure on every short fresh request. Whole-dialogue SFT subsequently fails too. |
| Training metrics were insufficient for capability decisions |950-dialogue SFT reduces assistant validation NLL4.649→4.463 but solves0/8 conversation tasks. The12-dialogue control achieves730/762 teacher-forced final-reference token matches but only5/12 exact generated references. | Average forced loss and stopping cannot stand in for free-generation task success. A single wrong early token can lead to an unrelated or repetitive continuation. |

The practical planning error was allowing tiny mechanics/overfitting experiments to occupy the role of a language-learning program. The original broad pretraining plan was not actually delivered by the10M-position dialogue pilot. Repeating source audits or another miniature memorization run does not resolve that deficit.

## New read-only measurements

Frozen protocol: `configs/conversation-collapse-diagnostic-v1.json`. Actual evidence: `reports/conversation-collapse-diagnosis.json`; raw measurements and source-span matches remain in `data/conversation-collapse-diagnostic-v1`.

The same ten **single-turn control-training answers** are scored under their correct user prompts and under a cyclically rotated, unrelated prompt. Values are content-token-weighted NLL on exactly the same references:

| Checkpoint | Correct prompt | Wrong prompt | Correct-prompt advantage | Basic generation tasks |
| --- | ---: | ---: | ---: | ---: |
| Own foundation |4.355|4.645|0.290|0/10|
| Whole-dialogue SFT |4.135|4.470|0.335|0/10|
| Fitting control |0.162|0.498|0.336|0/10|

The control makes familiar answers easy to continue even under a wrong prompt. **The positive gap also shows some input conditioning remains**; it is incorrect to say attention is broken or that the model literally ignores every input. Teacher-forced reference prefixes supply most of each answer, so these losses do not measure independent answering ability. The ten generation cases are post-hoc development prompts, not a new blinded benchmark.

All300 actual user prompts pass tokenizer byte roundtrips. All12 complete control dialogues independently pass next-token shifting, role/content reconstruction, assistant-only target masks and inference-prefix alignment. Source/input/checkpoint hashes are unchanged before/after. Thirty bounded64-token generations and60 reference scores occur with **zero gradients, teacher calls or cloud spend**.

## Explanations not supported as the primary cause

- **Only KV-cache failure:** all seven earlier first errors on nonexact training references also occur under uncached full-prefix inference. This is targeted evidence, not universal cache parity.
- **Only system prompt or generation cap:** the earlier16-case diagnostic fails at64 and256 tokens and after system-message removal.
- **Missing EOS learning:** forced EOS-after-message-end probability is strong; correct answer selection and appropriate earlier stopping remain weak.
- **Tokenizer corruption or an obvious shifted-label/mask error:** the actual reconstruction checks above pass. This does not audit every gradient or prove all numerical paths correct.
- **81M parameters categorically cannot speak English:** not established. Restricted-domain coherent English has been demonstrated at much smaller sizes in [TinyStories](https://arxiv.org/abs/2305.07759). That result does not imply broad chat, adult styles or tools at this size.

No new evidence isolates learning rate, batch size, normalization, initialization or capacity as the exclusive cause. Do not change architecture, tokenizer, numerical conventions and corpus together and then claim an identified fix.

## Scale reality

The approved100M additional physical positions are a **learning pilot**, not a sufficient broad-conversation budget. The published135M SmolLM used600B training tokens plus separate instruction tuning; its architecture, tokenizer and mixture differ, so that count is context, not our requirement. [Primary training report](https://huggingface.co/blog/smollm).

Training exposure must grow with capability evidence; [compute-optimal training research](https://arxiv.org/abs/2203.15556) supports considering parameters and training data jointly. It does not supply a magic minimum that guarantees this project's behavior. Billion-position stages in the long-term plan remain unapproved research proposals; no new financial authorization is inferred.

The concrete remedy and predeclared stopping/promotion criteria are in [the revised next-iteration plan](next-iteration-training-plan.md). This diagnosis supports that intervention; the intervention's results must establish whether it works.
