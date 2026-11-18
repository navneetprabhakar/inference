# Worker B: final candidate review

237 conversations accepted for parent assembly: 230 original scenarios and seven reviewed replacements. These contain 1,414 unique assistant texts and 25,823 supervised target positions per policy mode. All dialogue was generated or revised through Codex CLI 0.167.1 with requested model `gpt-6.1-terra`; no orchestrator-written dialogue was inserted. Backend routing cannot independently be established from CLI events.

All 1,414 final assistant turns received fresh-session semantic review and full content inspection by worker B or the parent. The parent directly inspected 29 unchanged accepted conversations; two additional parent-held conversations were subsequently repaired through Terra and reread by worker B. Same-model fresh-session review is not independent release acceptance.

The selected data remains candidate-only. No training, model-quality improvement, release acceptance, cloud operation, serving change or frozen/weight modification occurred. Parent global split, semantic deduplication and admission gates remain required.

## Final evidence

- `accepted.jsonl`: canonical exact raw-generated messages, per-row generation/review/plan evidence, canonical delayed-memory annotation, and memory/history/index-normalization receipts.
- `final-audit.json`: actual native tokenizer checks for tools-disabled and tools-enabled/no-call policies; 2,048 context, 256 reply reserve, no truncation. Maximum full context 1,745 tokens, generation prompt 1,718 and actual reply 38 targets.
- `final-content-review.json`: all 237 final message hashes, every actual assistant turn, reviewer and rationale.
- `final-memory-evidence.json`: original annotation exactly as generated, final conservative annotation, credit, reason and sources. `final-memory-annotation-review.json` normalizes previously recorded manual/cold decisions; it does not invent a new review.
- `final-generation-history.json`: every generation call containing each selected scenario, including superseded drafts. Maximum two revisions per scenario. Review-only retries do not count as text revisions.
- `final-index-normalization.json`: preserves original assistant review indices. Only exact full flat-message sequences 2,4,...,2n map to pair indices; no loose normalization.
- `final-exclusions.json`: 13 excluded scenarios. Nine original mechanism overlaps, one original unresolved practical constraint after two revisions, and three replacement grounding defects. Parent stopped additional volume because global reviewed candidates exceeded 1,000; no quality threshold was relaxed to reach the worker quota.

## Boundaries and caveats

All retained examples have at least two complete intervening pairs after the last supporting mention at the recorded narrow focus. Contextual cues remain; these are lessons, not an isolated memory benchmark. Pair counts are 4–8; b159 has an explicit hash-bound planned-seven/actual-six variance authorized by the parent. Positive tool-call workflows are absent from this worker's memory subset.

The first review rubric was sometimes overinterpreted as requiring unrelated topic switches. Original evidence was retained and corrected fresh reviews permitted coherent same-activity subtopics while preserving factual and delay requirements. Parent and worker inspection caught additional unsupported claims despite cold-review passes. Failed drafts remain evidence and are not counted as new accepted conversations.

No CLI jobs remain. No more generation is queued. Reproducible final validation: `.venv/bin/python reports/ganesh-english-sourcing-v1/scale-1000/worker-b/final_audit.py`. `finalize.py` and `finish_evidence.py` are assembly-stage helpers and should not be invoked casually after finalization; the final memory adjudication includes additional explicit canonicalization evidence.
