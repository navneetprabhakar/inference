# Public conversation development v1

This is an exposed, authored development set, not either protected acceptance gate. It covers multi-turn recall/correction, grounded rewriting and summarization, clarification, supplied-fact reasoning, drafting versus claiming external action, and ordinary conversational follow-up. It contains no tool-required arithmetic. Tool capability has separate development cases.

Freeze the exact cases and evaluator fingerprint before any model execution. Do not feed these cases, answers or model-specific revisions into training. The set's novelty relative to cached teaching corpora is not established; no sealed/generalization claim is permitted. Future corpus intake must exclude this public development file as well as existing protected sources.

Exact-answer turns deliberately request the exact short response. Open prose uses explicit manual rubrics: an automated runner must retain manual-pending status, preserve the full response and planned denominator, and cannot turn those cases into passes without documented review of every substantive turn. Report objective checks and manual judgments separately. Review the actual model output for relevance, factual preservation, consistency and unsupported claims, not similarity to a preferred teacher answer.

Use the actual own-base Chat with complete history, fixed 1024 context and 256 reply reservation. Any context/protocol failure fails the affected full session; never shorten histories or skip remaining planned turns. An infrastructure failure aborts the evaluation with an incomplete receipt. No training, runtime promotion or acceptance claim follows from preparing this set.
