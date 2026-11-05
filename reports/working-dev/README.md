# Independent working-chat development evaluation

The set froze on 5 November 2026 before inspection of candidate outputs. Twenty local conversations exercise 40 sequential turns across 10 prose, six tool and four no-call sessions. There are 19 scenario families. Two tool sessions share a prompt and intentionally differ only in their recorded observations. This development sample cannot establish the release threshold on the sealed 100-case confirmation set.

The case file binds its own plain-language rubric, accepted output patterns, required broker sequence, tool permissions and fixture conditions to each turn. Start a fresh trusted Chat per case. Use its normal turn method, greedy output cap and actual history throughout that case. Keep malformed replies, denied proposals, all actual frames and all actual broker records in the transcript. The evaluator never substitutes the ideal fixture after a wrong first call.

Content, protocol and call sequence must all pass for a turn. Both turns must pass for a conversation. Number-only rubrics accept one numeric quantity. Explicit formatting tasks use the requested case and punctuation. Natural answers use preregistered whole-answer alternatives. A valid open-ended paraphrase can miss these conservative alternatives. Preserve the original verdict and exact transcript for any independent adjudication; never silently amend a rubric after inspecting a candidate.

Report first-call correctness per tool session and per required turn. Report complete call sequences, required no-call turns without a failed protocol or attempted call, and post-tool faithfulness both conditionally on an observation and over all expected readbacks. Report forbidden or unknown successful calls separately. A wrong call and a faithfully reported actual result receive separate judgments. Recall references the latest actual turn. A failed conversation stays in every applicable denominator.

To exercise the scripted controls, run:

    .venv/bin/python verify_working_eval.py

The controls use actual Chat.turn and the offline broker with a scripted CPU generator. They exercise all 20 ideal conversations and deliberate negative cases. These are wiring tests. Candidate scores must come from raw student responses and a pinned checkpoint. The CPU command runs a student once:

    .venv/bin/python evaluate_working.py <weights> <sha256> <fresh-run-directory>

A process already holding the exclusive device guard may instead call `run_evaluation(model, tokenizer, guard, fresh_output_dir, identity)`. Preserve the checkpoint hash in identity. Outputs include raw JSONL transcripts, score numerators and denominators, the scorer/chat/case hashes and completion state.
