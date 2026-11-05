# Session name memory preview

The opt-in `memory-preview` runtime stores one explicitly supplied display name in the current local chat. It recognizes whole-turn introductions such as “Hello, my name is Niko”, “please call me …”, explicit corrections, direct name recall and “forget my name”. The host renders these replies and labels each frame `host/session-memory`. Tool execution is disabled for these turns.

A recognized meeting courtesy can accompany an explicit naming clause. A greeting such as “Hello there, I’m Zélie. It’s great to meet you.” also qualifies when it contains a single proper-name-shaped token and a standalone meeting courtesy. “I go by Marisol”, “call me Iona instead”, and “please call me Ori from now on” update the current session slot. Direct recall accepts “now” or “again”.

Other requests go to the configured backend. Bare “I am …” statements, quotes, conditionals, mixed commands, third-party descriptions, indefinite aliases and travel uses of “go by” fall through. The ambiguous greeting construction excludes role and state descriptors, acronyms and common descriptive suffixes. A caller with a name outside this narrow construction can use “my name is …”. Arbitrary key/value preferences and personal attributes are outside the preview. Forgetting clears the slot and removes name-bearing turns from the model-facing context. The visible transcript keeps the original exchange. Starting a new session creates an empty slot.

**CPU verification.** On the existing preview checkpoint, “Hello, my name is Niko” received “Hello, Niko.” The follow-up “What name did I just give you?” received “Your name is Niko.” Both records carry host origins and empty tool traces. A second session reported no saved name. These are host-feature checks and contribute no points to the raw neural score.

```sh
python serve_chat.py --pin reports/working-chat/preview.json --runtime memory-preview --cli
python verify_memory_chat.py --pin reports/working-chat/preview.json
```

The constructor is `memory_chat.Chat(model, tokenizer, guard)`. Raw checks are in `runs/memory-preview-qa/checks.json`.

**Extension verification.** The CPU checks passed 25 recognized forms and 77 ambiguous/adversarial rejections, retaining the original cases. A fresh seven-turn session exercised a greeting with a courtesy sentence, a changed alias, both correction qualifiers and recall. Every memory reply carried `host/session-memory` and an empty tool trace. The fresh output is in `runs/memory-preview-qa-variants/checks.json`. The earlier usability report remains a separate historical measurement.
