# V4 objective teacher-label checks

Prospective, count-only; never rewrite answers, strip constraints or admit data. Start v3 root-custody survivors minus all20 v3 review deferrals. Inspect train system inventory only: dominant templates are two summary instructions and three rewrite instructions. Rules below apply identically to both fixed splits; preserve all families. Low priority, one CPU thread,15minutes/50MiB, honor STOP, no GPU/tokenization/new intake.

For EXACT summary system specifying up to three sentences, reject assistant with >3 sentence units or second/third person pronouns. For EXACT one-very-short-sentence system, reject >1 sentence unit. Sentence units split at terminal .!? plus whitespace/end, protecting decimal dots and common titles; this is an operational heuristic, not a linguistic proof. Pronoun regex uses whole words (you/your/yours/yourself/yourselves/he/him/his/himself/she/her/hers/herself/it/its/itself/they/them/their/theirs/themselves), because the system bans both categories.

Reject unresolved meta placeholders [relation], [num_sentences], [num_highlights], [response_options] in user or assistant, unless the user explicitly supplies that named parameter as name: value. Do not reject ordinary requested [city]/[author] placeholders indiscriminately.

For exactly the two summary and three rewrite systems, reject digit-based numeric values in an assistant answer absent from the immediately supplied user passage. Compare normalized numeric strings with commas removed; this deliberately conservative rule may reject legitimate calculations or transformations. It cannot detect spelled-out number changes, invented nonnumeric facts or temporal drift.

Reject unqualified first-person own-model origin/cutoff or completed external-action/access claims matching frozen explicit regexes. Skip this identity/action rule when system or user explicitly establishes fiction/role-play using frozen markers; no claim that fictional actions happened in reality. Do not flag negated access inability as a positive claim. These lexical rules do not validate general factual truth.

Freeze code and tests before full scan. Store only excluded IDs/rules, original hash pins and source/split counts; no corpus mutation. Freeze8 new TRAIN samples/source,2/rank input-length quartile, lowest SHA256(`sft-v4-quality-20261106|source|doc_id`), disjoint prior48; report shortfall if insufficient, no reroll. Read all selected histories and record subjective retain/review/hold reasons; no statistical certification or model-quality claim.
