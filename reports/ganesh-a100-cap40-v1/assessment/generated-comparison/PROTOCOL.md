# Local generated comparison protocol

Exposed diagnosis only. Not training data, pristine release, independent grading or a capability ceiling. Same author writes and reviews the panel. All checkpoints are Own/Ganesh-base; no pretrained replacement, weight modification, cloud launch or HTTP server.

## Fixed panel

48 hand-authored scenario pairs / 96 variants, eight families, six scenario pairs per family. Each variant is tested with identical user content as plain `BOS + prompt + newline Answer:` and canonical native chat, no extra system, tools disabled. Three retained checkpoints: base10B, fit30, SFT194. Greedy decoding, no repetition penalty, 64-token maximum, same canonical uncached generator. No answer candidates provided. This is an intentionally narrow short-answer panel; it does not measure general English breadth. Plain Q&A framing can itself disadvantage a completion model. Supplied distractors are not real conversation history.

Raw IDs/text, exact prefixes, checkpoint manifest hashes, panel hash, parsed action, token-cap exhaustion and timings retained. Native framing is applicable to native chat only; native-valid figures for plain output are diagnostic, not plain-language correctness. Reaching the token cap cannot be counted as a valid native completion. No truncation or repaired answer is served or reported as model improvement.

## Content scoring

Review every raw record; automation may prepare labels but cannot establish semantic acceptance from substring matches.

- `core_correct`: output unambiguously answers the requested fact/action or preserves the paraphrase's required meaning. For factual answers, explicitly reporting both old and new facts is acceptable only if the current answer is correctly distinguished. For unknowns, acknowledge missing evidence without inventing an answer. For exact-output tasks, only requested content is correct (outer whitespace ignored); explanations are failures. Continuation that later retracts/contradicts the answer makes core correctness false.
- `clean_content`: core correct AND the entire output is responsive, coherent, non-repetitive and contains no substantive unrelated continuations, invented facts, forged conversation or illegal control tokens. The final native assistant-end marker is excluded for this content check; other controls remain evidence.
- `native_valid_text`: unmodified project parser accepts text; not a semantic judgment.
- `usable_native`: clean content AND native-valid text, native-chat rows only.

Report individual variants and both-variants-correct pairs; pairs control static answer bias but remain clustered by scenario family. Do not inflate confidence using 576 rows as independent observations. Report each family and each model, plus paired plain/native discordance. Do not interpret differences as proof of a training remedy.

## Generated rollouts

Separate 12-session (six paired scenarios), three-turn panel per model/framing, covering delayed recall and corrections amid distractors. Native history follows BrokerChat; invalid replies block subsequent turns, and blocked turns remain failures in the denominator. Plain history contains the complete generated text, including malformed text; it is an exploratory transcript continuation, not a production broker. Fixed 64-token budget; all outputs retained. Never insert expected assistant answers to unblock a session. Analyze content and end-to-end success separately; differing history validity constrains plain/native comparisons.

## Decision boundary

Choose no parent solely from aggregate scores. A framing-only hypothesis requires a consistent plain semantic advantage across relevant families and meaningful plain competence; low scores in both modes cannot justify it. A content-learning hypothesis requires recurring semantic failures in both modes, including actual state/correction tasks, not only malformed endings. Mixed results or unstable family rankings mean no parent promotion or cloud launch. Any subsequent training needs a prospectively approved single-variable design, reviewed data, finite budget and existing safety gates. Counts here are bounded diagnostic design choices, not sufficient-data or release thresholds.
