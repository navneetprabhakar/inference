# Tool failure RCA — 18 November 2026

**Decision: do not extend context as a fix for these failures.** The128-token limit cut off output, but was not the underlying cause of failed tool calls. No4K/8K configuration or weight change was made.

## Evidence and controlled follow-up

| Check | Observed result | Interpretation |
|---|---|---|
|37 saved CRUD cases|242–249 prompt tokens; all responses reached128 tokens|No input overflow; maximum reserved total377 vs2,048 available|
|Native frame inspection|Zero tool-start tokens anywhere and zero end tokens across37 responses|No call to finish; decoder generated prose/malformed repetition|
|Identical notes-create prompt with512 output tokens|512-token repetitive malformed response; first128 tokens exactly match original|Four times the output budget did not recover the action|
|Production calculate control|13-token normally terminated irrelevant explanation, no call|Not a universal EOS/token-budget failure; requested addition was not done|
|Production convert control|13-token normally terminated false rejection of metre conversion, no call|Existing-schema request also fails instruction/tool selection|
|Simple greeting control|17-token normally terminated two-sentence apology, no greeting|Weak instruction following extends beyond new CRUD schemas|

The production calculator request was17+8 (expected25); the conversion was2metres to centimetres (expected200cm). Neither tool was invoked. Transport status `complete` is explicitly NOT semantic success. The full48-case suite remains stopped at the user's request; this turn ran only one larger-budget probe and three controls. No unrun cases count as passes or failures.

## Root causes and contributing factors

1. **Missing task-aligned supervision in the tested SFT phase — confirmed.** The exact Fit30 metadata binds `english-first-v1/diagnostic-manifest.json` and its24-session training file. Its hash matches and it contains zero assistant tool-call messages and zero tool observations. It is an English-only diagnostic checkpoint, not a qualified tool-calling model. This does not prove it never saw code/tool-like text in pretraining, nor that it cannot learn tools. The1,093 reviewed recent candidates have not been trained into these weights, and their orchestration lessons are text-only.
2. **Unlearned call selection and weak instruction following — observed.** CRUD responses never choose the native call boundary. Existing calculate/convert requests also return incorrect prose. The greeting control is poor. Correct serialization and stopping are possible on short native-format controls, so blaming a globally broken tokenizer/EOS is inconsistent with these observations. The precise optimization/data contribution remains unisolated.
3. **New protocol/schema transfer burden — confirmed confound.** Production `nano_chat_format.py` restricts policy/call validation to calculate/convert and numeric results. The test uses a separate experimental generic registry, ten tools at once and structured CRUD observations. The harness passing scripted cases does not establish that these prompts match trained distributions. We must not label this as a regression of previously trained CRUD ability.
4. **Output repetition — observed failure mode, not established fundamental cause.** Under fixed greedy decoding, the extra384 tokens continue the same loop. A different decoding strategy could alter text but is not evidence that weights learned executable calls. Do not repair prose into calls or declare improvement from longer generation.
5. **Diagnostic design limits — explicit.** The model sees all ten schemas; single-tool versus ten-tool routing has not been ablated. Mock field values are opaque strings, including email/URL-labelled fields. The diagnostic tests generic CRUD mechanics, not domain validators. We did not run a new training experiment, compare other checkpoints or consume protected release data.

## Why4K input plus4K output was not applied

The exact checkpoint has `sequence_len=2048`. Repository context transition code supports2,048 and4,096 total tokens and explicitly rejects unqualified8K. Four thousand input tokens plus four thousand generated tokens need at least8,192 total positions (with input framing included in the input count). This is a context-extension/qualification project, not two independent request flags. Merely changing the config would violate checkpoint identity and would not demonstrate long-context learning.

These prompts use fewer than250 input tokens. A4K input limit would add no useful information. Increasing output to512 failed under the same prompt and decoding. Since the required native action must begin with the tool delimiter and the first token is already prose, appending more tokens cannot turn that action into a valid call under this protocol. Larger context may be useful for future workflows, but is not indicated as a remedy here.

## Corrective sequence

1. Preserve Fit30 and this failed diagnostic as an exposed baseline; do not promote or claim prior CRUD proficiency. Keep the stopped full suite stopped.
2. Implement a versioned production registry and structured-result contract, with exact train/serve-prefix and masking tests. Preserve frozen historical formats; do not monkey-patch them.
3. Prepare reviewed, executable call→actual-result→faithful-answer lessons. Start with one small CRUD store, then add multi-turn state, errors and no-call policies, then ten-tool routing. Include realistic field values in the next suite. Split scenario groups before variants; reserve fresh development/release sets.
4. First use a tiny bounded fit experiment to determine whether the optimizer can teach native call boundaries, valid arguments and EOS. If it cannot, diagnose objective/masking/input exposure before adding data or tokens. Then run the mixed English/tool pilot under a separately approved finite cap and the existing failure-stop rules.
5. Evaluate exact calls, state changes, grounded final text and full workflows separately, including false success and unnecessary calls. Continue English evaluation concurrently. Context extension is a later isolated experiment only if actual workflow length warrants it.

See IMPROVEMENT_PLAN.md for proposed admission checks and pilot gates. No training, cloud operation, serving-default change or weight mutation occurred. Local MPS probes completed and joined. Raw evidence: rca-static.json, rca-probes.jsonl, rca-conclusions.json, original raw-results.jsonl and run-config.json.
