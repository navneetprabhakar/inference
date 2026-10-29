# G0 v3 custody overlap audit

Bounded exact-overlap and source-field checks completed. Final remains restricted, unsealed and ineligible for G5; this report is not full G0 admission.

Algorithm: Python str.casefold(); re.sub(r"\s+", " ", s); strip(); UTF-8 encode; SHA-256. Whole conversation concatenates ordered user AND reference contents with newline before normalization, with no role markers. Per-user and reference hashes normalize each content independently. No Unicode NFC/NFKC or punctuation stripping.

Assignment inventory: 517 hashes are unique pipe-delimited DATA source-record field strings, not structured joint person/time/object assignment tuples. Recomputed using AST literal evaluation only; author script never executed. Therefore a generic matching field is not proof of shared concrete event assignment.

| Compared corpus | Rows | Whole conversations | Users/readiness fragments | Reference hashes | Concrete value hashes | Complete source field sets | Shared 8/12/20-word user ngrams |
|---|---:|---:|---:|---:|---:|---:|---|
| training/private/candidates.json | 6400 | 0 | 0 | 0 | 0 | 0 | {'8': 0, '12': 0, '20': 0} |
| benchmarks/development.json | 120 | 0 | 0 | 0 | 0 | 0 | {'8': 0, '12': 0, '20': 0} |
| benchmarks/grammar_contrasts.json | 60 | None | 0 | 0 | 0 | 0 | {'8': 0, '12': 0, '20': 0} |
| benchmarks/grounded_choices.json | 120 | None | 0 | 0 | 0 | 0 | {'8': 0, '12': 0, '20': 0} |
| benchmarks/native_continuations.json | 60 | None | 0 | 0 | 0 | 0 | {'8': 0, '12': 0, '20': 0} |

Limitations:
- Scope is old G0 training candidates, development and three readiness assets only. Additional/new training or broad corpora require a fresh check before admission.
- No exact multi-turn duplicate and no reproduced complete multi-token source-field set establishes only bounded lexical disjointness, not semantic independence.
- Shared abstract correction, grounding, instruction and interruption structures are intentional task structures. Exact 8/12/20-word overlaps quantify surface structural reuse, not leakage by themselves.
- The public assignment inventory hashes individual fields, including generic relations/answers, and cannot alone prove concrete joint-assignment disjointness. Full source-field reproduction test is conservative and may miss paraphrased scenarios, changed entities, subsets, or split information.
- Readiness has no whole conversation representation: conversation overlap is null (not applicable). Readiness reference hashes compare all option/suffix strings, not merely correct choices. Training declared assignments cover only the explicitly supplied slot_assignment metadata; other lexical values are covered by full rendered-text field search.
- Independent semantic comparison of every source scenario across corpora is not performed. Namespace disjointness does not prove source-family semantic independence.
- Final is 240 functional adaptations from 40 source scenarios; inference must account for cluster dependence.
- Custody is procedural same-user access, not cryptographic isolation. Private source DATA and final payload were processed on CPU with no utterances or reference values emitted.
