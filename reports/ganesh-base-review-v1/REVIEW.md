# Ganesh-base — evidence-first reassessment

**Model: Ganesh-base. Creator: Navneet Prabhakar.** Reviewed17November2026(IST).

## Verdict

The project has not established a reliable path from its current weights to English conversation. There is no single demonstrated bug that explains all failures. The strongest evidence points to inadequate demonstrated conversational learning, a small/misaligned instruction curriculum, fragile response-format/state-update behavior, and an experiment sequence that has not completed its decisive learnability test. Recovery infrastructure problems are real but are not established causes of the conversation failures.

The model is not devoid of language or context use: the base completes a simple color fact correctly, and trained checkpoints retrieve an access word from supplied history. Neither behavior is reliable, concise, correction-aware conversation. Naming the model, changing a prompt, increasing reply length, or resolving restart parity is not by itself a conversation repair.

This is an evidence-first review, not a genuinely blind external audit. The reviewer has project history. To reduce anchoring, data statistics were recomputed from the checkpoint-bound training file, source code was inspected, new local probes were run, and previous conclusions were treated as hypotheses. No sealed release suite was used. No model weights were updated.

## 1. Identity: declared versus learned

The canonical declaration is `MODEL_IDENTITY.json`. Historical Own/ownbase/forge paths remain unchanged to preserve lineage and hashes. They now refer to Ganesh-base; this does not require renaming payloads. Previously deleted legacy Ganesh buckets are distinct from the retained Own-lineage checkpoints.

The requested name/creator are **not yet embedded and verified in the weights**. Fresh raw identity probes invent names/creators, including Mara/Dev for SFT194 and Joey for SFT50. There was no prior basis for these newly supplied identity facts to be learned.

Prepared12training-candidate and8development-candidate conversations,32total turns, under `reports/ganesh-base-identity-v1/`. All responses were reviewed and native formatting/masks checked. Both tools-disabled/no-call and tools-enabled/no-call modes are represented. Scenarios include direct identity, attribution, follow-up questions, user/model-name separation, ordinary-task controls and context after an introduction. No system prompt injects the desired answer. These are unadmitted candidates, not trained weights; the frozen English fit set is unchanged.

Real completion requires training a separately identified candidate, then testing new identity phrasings without identity-bearing prompts or answer substitution, verifying correct full creator name, unrelated-task controls, context retention and checkpoint reload. Identity keyword occurrence alone is not acceptance. Facts learned in parameters are not cryptographically permanent and cannot guarantee that every adversarial prompt will elicit the right identity.

No weight-training step was run because cloud execution remains paused pending a new cap, and the current training path is CUDA-qualified-by-contract rather than an approved local MPS training recipe. A metadata edit must not be reported as successful weight embedding.

## 2. What was actually trained

Fresh audit of the JSONL bound to SFT194's source manifest:

| Family | Sessions | User turns | Unique-pass assistant target positions |
|---|---:|---:|---:|
| Natural dialogue |80|190|32,288|
| Unit conversion |112|112|3,638|
| Calculation |105|105|3,646|
| Tool correction |52|104|3,611|
| Total |349|511|43,183|

Eight epochs produced345,464target exposures, not345,464different lessons. The natural family accounts for74.77%of assistant targets. It is therefore incorrect to infer that tool rows dominated the language-model loss merely because they comprise269of349sessions. The80natural dialogues are meaningful supervised examples, but their volume and range are small for broad conversational behavior.

A concrete routing defect in the curriculum is confirmed:190user turns have tools disabled and no call;321have tools enabled and a call; **zero have tools enabled and no call**. The model was not taught that tool availability is compatible with ordinary conversation. Later corrective data addresses this in design, but preparation is not evidence that it was trained.

Natural response lengths also differ from the later short-answer objective: median152.5tokens, mean169.94;121/190responses exceed128tokens and167/190exceed64. The trained style favors longer replies than many later tests request. These are valid references, not proof the data are garbage. The issue is curriculum alignment and coverage.

The base checkpoint is16layers,536,871,738parameters, native2048tokens;19,074updates ×524,288positions =10,000,269,312processed positions. Its recorded source is a bounded sample of `karpathy/climbmix-400b-shuffle` at the pinned revision. Approximately16.35%of source tokens in the available packed-inventory report were cropped during preparation; this is not a direct causal explanation. Full source payloads are now in GCS, and this task did not re-download/re-audit every source document, duplication or contamination rate.

## 3. Fresh raw-output evidence

Three checkpoints were probed locally: base10B, development-best SFT50 and default experimental SFT194. Five chat questions plus a plain-text control were used; the same five were also run without the policy boilerplate for base10B and SFT194. Total30outputs includes repeated plain controls; it is not30independent benchmark questions. Decoding was greedy, penalty1, MPSFP32,64tokens for chat and32for the plain control. This is a small exploratory diagnostic, not a release score or a capability ceiling.

The two context probes supply correct assistant history to separate recall/correction from first-turn generation failure. They do **not** demonstrate successful autonomous multi-turn conversations.

| Probe under current production framing | Base10B | SFT50 | SFT194 |
|---|---|---|---|
| Greeting | Unrelated tool-list continuation; invalid frame | Museum-host instructions; invalid frame | Photo-shoot instructions; invalid frame |
| One-sentence thank-you for help moving | Repetitive refusal; invalid | Starts with thanks but adds unrelated demands/advice; valid frame | Invented story about Iris; invalid |
| Name and creator | Repetition; invalid | Invented Joey identity; invalid | Invented Mara/Dev identity; invalid |
| Access word in supplied history | Includes marigold but echoes policy; invalid | Identifies marigold, adds permission to change it; valid | Correctly identifies marigold; valid, but violates “just that word” |
| Tuesday corrected to Friday | Answers Tuesday; invalid | Answers Tuesday; valid | Answers Tuesday; valid |

The plain-text base control starts with the correct answer, red, then repeats. SFT50and194drift away from the color question. This is evidence against assuming that the newest SFT checkpoint improves every behavior; it is not a statistically sufficient comparison of general model quality.

In the no-policy ablation, SFT194answers the corrected meeting day as Friday with a valid end token, although it still violates “just the day.” The base also starts with Friday but fails to stop appropriately. Greeting, instruction-following and identity remain poor. Removing the policy makes factual correction succeed in one paired case; it does not establish a general serving fix and was not deployed.

## 4. Why conversation is failing

### A. The learned assistant behavior is inadequate — confirmed

The model often generates unrelated content, copies instructions/policy text, invents entities and fails requested brevity. These are semantic/instruction failures, not only parser complaints. SFT50and194can emit clean end markers in some contexts, so a claim that end-token generation is universally broken is false. Base and two-update diagnostic end-token failures should not be generalized to every retained checkpoint.

The broad from-scratch foundation has not been established as strong enough for the intended assistant. The base shows some language completion, but no adequate general English baseline is documented by these probes. More pretraining could help; these observations do not prove how much is needed or that additional SFT cannot improve it.

For scale context, the official [SmolLM2-360M model card](https://huggingface.co/HuggingFaceTB/SmolLM2-360M) reports4trillion pretraining tokens, versus10billion here. That is400times more tokens, despite fewer parameters. Its [instruction model](https://huggingface.co/HuggingFaceTB/SmolLM2-360M-Instruct) uses a separate instruction-training recipe. These are not minimum requirements or apples-to-apples guarantees; they show why parameter count and a completed10Bjob do not establish comparable quality. The [Chinchilla study](https://arxiv.org/abs/2203.15556) optimizes training compute allocation, not a guaranteed threshold for conversational competence.

### B. The curriculum does not adequately teach the target interaction — confirmed gaps, causal strength unmeasured

Only80natural dialogues were in the completed194update run. General conversation, brief answers, clarification, correction precedence, distractor resistance and persistent constraints need deliberate coverage and behavioral checks. Repeating43Ktarget positions eight times does not supply that breadth. The missing enabled/no-call mode is exact, not speculative. Names/creators also require explicit factual supervision.

There is no basis for blaming Codex-generated data merely because it is synthetic: source examples include reasonable edits, explanations and interpersonal rewrites. Quality must be assessed per example, per skill and by training effect. Conversely, manual approval of good examples does not establish that the model learned them.

### C. Framing, response style and evaluation interact badly — confirmed effects, not a complete cause

The host prepends tool-policy prose/JSON to every user turn, including when calls are disabled. The model sometimes echoes it. Correct history is forwarded by the serving code; overflow is explicitly rejected rather than silently truncated. Therefore “the chat UI forgot the history” is not the supported explanation for these in-window failures.

The64token fresh probes and128token earlier fit probes can classify an overlong reply as an invalid frame. Longer budgets might finish some replies, but do not fix unrelated content, invented identities or incorrect correction handling. A useful diagnostic must report semantic correctness, instruction adherence, clean termination and raw truncation separately, while keeping the actual product failure denominator honest.

Earlier0/72fit results included24invalid initial frames and48blocked follow-ups. That is a valid operational score, but it is not72independently generated wrong answers and cannot alone measure memory. Fresh supplied-history probes demonstrate this distinction.

### D. Checkpoint selection and training control have been weak — confirmed historical facts

The194checkpoint records best development loss at step50(2.312421), yet completed all194updates. Prior end-of-run reports show later deterioration. A lower loss does not prove conversation quality, and fresh SFT50is also not acceptable. We needed generation-based checks during training and a predeclared selection rule, not an assumption that final equals best.

Current quality/regression and retention checks are stronger, but adding them after the fact does not repair existing weights. No trained model should be promoted from infrastructure or teacher-forced metrics alone.

### E. The experiment sequence has not answered the central question — confirmed

Recent cloud attempts primarily qualified allocation, restart and backup paths. The new English24-session fit pilot has not been completed. Two-update diagnostics and successful infrastructure tests do not answer whether the base can learn these examples.

The optimizer divergence is localized but not resolved. Its observed small numerical discrepancy has not been connected causally to the broad conversation failure, which predates that diagnostic. Treating optimizer exactness as the explanation for everything is unsupported. Continuing unrestricted infrastructure iterations can consume the entire budget without producing a learning result.

## 5. Context awareness: separate capabilities

1. **Context transport:** current messages are supplied within the2048token budget; no evidence here of silent history loss.
2. **Fact extraction:** partially present—marigold is retrieved under supplied history.
3. **Correction/update precedence:** unreliable—Tuesday persists despite Friday; one formatting ablation improves it.
4. **Constraint retention across distractors:** not demonstrated by these short probes. Long3K–4Kdata were not consumed by the native2Krun; stored data do not extend the trained context window.
5. **Memory across separate chats:** no persistent-memory store is established in this runtime. This is distinct from within-chat learning and from identity facts stored in weights. It should not be silently promised.

## 6. What is missing, in priority order

| Missing evidence/capability | Smallest useful next result | What must not count as success |
|---|---|---|
| Name/creator learned in weights | Identity-trained candidate passes no-hint raw-generation and reload checks | README, metadata, system prompt or string substitution |
| Basic response/control learnability | Frozen short English fit demonstrably learned with correct endings and instructions | Loss decrease, two updates, good calculator outputs |
| Correction and state management | Paired counterfactual conversations where the same question requires different answers after updates | Echoing one unchanged fact or supplying gold answers as if generated |
| Generalization | Scenario-disjoint tasks, diverse phrasing and full generated histories | Training examples, repeated exposed tests, same-author stylistic matching |
| Foundation adequacy | Measured simple-language baselines and transfer after successful fit |10Btokens,537Mparameters or a theoretical scaling ratio |
| Affordable execution | One explicit bounded decision experiment with backup, stop and outcome accounting | More capacity/recovery retries without answering a learning question |

## 7. Recommended reset of the plan

Keep Ganesh-base's weights and the frozen fit set. Stop broad corpus growth and long-context/math expansion. The next approved work must prioritize proving basic learning.

- Finish a **bounded** actual-input optimizer diagnosis if pursuing the current exact-resume contract; do not let it become an open-ended program.
- Alternatively, separately review an **uninterrupted, no-resume learning diagnostic** to isolate learnability from continuation parity. An interrupted trial is discarded as a learning result; backups, finite STOP, one writer and no promotion remain mandatory. This is a proposed new contract, not a waiver or an implemented bypass of the current gates. Bitwise restart parity is not itself an English-learning objective.
- Admit the identity candidates only through a new reviewed manifest/contract. Do not silently mix them into or rewrite the frozen24-session fit set. Track identity and English outcomes separately. No claim of identity embedding until a weight update and raw no-hint checks succeed.
- Require the predeclared fit gate before broad curriculum spending. If training-fit fails, inspect objective/end-token/optimization or foundation limitations. If fit succeeds but unseen transfer fails, invest in curriculum diversity and foundation quality—not more replay of the same tiny set.
- For context lessons, use explicit state updates, competing old/new values, distractors and controlled counterfactual pairs. Test with generated histories and separately supplied-history diagnostics; neither replaces the other.

A small identity pilot may teach two facts; that is not evidence that a small extra GPU budget will deliver general English. No reliable cost-to-finish estimate or success probability can be supported yet. The missing measurement is the bounded learning curve and generated fit/transfer behavior.

## Current action status

Completed: canonical name/creator declaration,20reviewed identity candidate sessions, fresh checkpoint-bound data audit,30exploratory outputs with raw IDs, framing ablation, manual evidence review and handoff update. All41frozen hashes unchanged. No GPU/HTTP/training, no serving patch, no prompt-injected identity, no weight edits, no GCS mutation, no commit/push. Identity embedding remains pending trained-candidate verification; the user must not be told it is done.

Evidence files: `data-audit.json`, `answer-lengths.json`, `*-fresh.json`, `*-minimal-frame.json`, `manual-review.json`, `frozen-check.json`; identity examples and acceptance criteria are in `../ganesh-base-identity-v1/`. Local-only experiments use MPSFP32 and do not establish CUDA parity.
