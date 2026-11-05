# Continuous chat rating — 100 exchanges

Original artifacts: [raw records](../continuous-chat-100-v1/raw-records.jsonl), [rendered transcript](../continuous-chat-100-v1/CONVERSATION.md), [prompt plan](../continuous-chat-100-v1/prompt-plan.json). This evaluates 100 sequential exchanges in one rolling-context chat, not 100 independent conversations.

Superseded for quality interpretation by [scoring-training-audit-v1](../scoring-training-audit-v1/AUDIT.md). This original report remains preserved audit history; no old scores were erased.

## Frozen rubric

Each dimension is 0–2: relevance/direct answer; correctness/grounding in supplied user facts; follows explicit instructions/constraints; continuity with actual available context; and clarity/completeness/nonrepetition. Total is their sum (0–10). `0` fails, `1` partial, `2` fully satisfies. Cutoffs and omitted rolling-window context are noted where relevant but are not automatic penalties. Full per-dimension decisions, evidence, and context notes are in [ratings.json](ratings.json) and its ten referenced batch files; rubric details are in [rubric.json](rubric.json).

## Coverage and distribution

All 100 IDs were reviewed; none is unreviewed. Mean: **1.91/10**. Median: **2.00**. P95: **4.00**. P99: **5.01**. P5 (poor-tail context): **0.00**.

Percentiles use linear interpolation at `(n−1)×q` over 100 sorted totals, with no rounding before display. Higher is better: P95/P99 describe the best-scoring tail, not the worst tail. Median position 49.50 uses sorted neighbors `2, 2`; P95 position 94.05 uses `4, 4`; P99 position 98.01 uses `5, 6` (`5 + .01×(6−5) = 5.01`).

Histogram: `0: 20`, `1: 22`, `2: 15`, `3: 37`, `4: 3`, `5: 2`, `6: 1`, `7–10: 0`.

## Per-exchange totals

| Exchange | Score | Brief reason |
|---:|---:|---|
| 1 | 0 | No objective; wrong community-table claim. |
| 2 | 0 | No invitation purpose; repeated boilerplate. |
| 3 | 0 | No allocation; invents Friday time. |
| 4 | 0 | Map directions, not swap fairness. |
| 5 | 1 | Names book counts but gives no rule. |
| 6 | 3 | Acknowledges constraint, no supply list. |
| 7 | 3 | Mentions budget, never subtracts ₹300. |
| 8 | 2 | Attempts arithmetic; ₹1920 is wrong. |
| 9 | 1 | Repeats wrong ₹1920, no split. |
| 10 | 0 | No layout checklist. |
| 11 | 2 | Repeats six tables, no assignment. |
| 12 | 5 | Correct table fact only; no category decision. |
| 13 | 0 | No condition wording; invents tables. |
| 14 | 3 | Mentions books, omits requested line. |
| 15 | 3 | Mentions children, omits adult/no-care rule. |
| 16 | 3 | No three volunteer roles. |
| 17 | 2 | No assessment of named roles. |
| 18 | 3 | Setup theme, no actions. |
| 19 | 1 | No timeline tasks; out-of-range times. |
| 20 | 1 | No late-arrival plan. |
| 21 | 3 | Two-minute reference, no welcome content. |
| 22 | 2 | No calm conflict solution. |
| 23 | 3 | No hold-sign decision. |
| 24 | 3 | No browsing-table rules. |
| 25 | 3 | Generic sentences, not table signs. |
| 26 | 2 | Not an invitation. |
| 27 | 2 | No less-formal/browse revision. |
| 28 | 1 | Violates no-food instruction. |
| 29 | 4 | RSVP theme and 12 retained, no recommendation. |
| 30 | 3 | No optional RSVP sentence. |
| 31 | 3 | Backup mentioned, no tentative wording. |
| 32 | 3 | No accessibility checklist. |
| 33 | 3 | Partial seating echo, unusable line. |
| 34 | 2 | No quiet-environment choices. |
| 35 | 2 | No placement for quiet period. |
| 36 | 0 | Misreads time as days. |
| 37 | 2 | No recommendation time. |
| 38 | 3 | No optional announcement. |
| 39 | 3 | No unclaimed-book disposition. |
| 40 | 2 | No two low-pressure options. |
| 41 | 3 | No return-policy entry wording. |
| 42 | 3 | No return-books sign. |
| 43 | 1 | Wrong budget arithmetic. |
| 44 | 1 | No ₹400 contingency calculation. |
| 45 | 1 | No cap/optional-purchase rule. |
| 46 | 1 | No stationery kit. |
| 47 | 0 | Does not address name tags. |
| 48 | 1 | No tag fields; invents account number. |
| 49 | 1 | No tag count. |
| 50 | 1 | Does not assess 18 tags. |
| 51 | 0 | No check-in; invents account number. |
| 52 | 0 | No capacity-gauging approach. |
| 53 | 1 | ‘Adversarial act’ is not contingency. |
| 54 | 3 | Contingency theme, no framing. |
| 55 | 1 | No usable crowded-room sentence. |
| 56 | 4 | One plausible field; otherwise incoherent. |
| 57 | 3 | No no-prices label wording. |
| 58 | 6 | Says owner name not required; incoherent rationale. |
| 59 | 3 | No take-back identification method. |
| 60 | 0 | Exam/city text, no sticker assessment. |
| 61 | 0 | No dot-sticker sign. |
| 62 | 1 | No suggested limit; suggests more books. |
| 63 | 3 | No five-book evaluation. |
| 64 | 3 | No no-exact-match sentence. |
| 65 | 3 | No book-acceptance cutoff. |
| 66 | 1 | Coffee measures replace time decision. |
| 67 | 1 | No closing sequence. |
| 68 | 1 | No ten-minute buffer. |
| 69 | 0 | No cleanup supply priority. |
| 70 | 0 | No two-person division. |
| 71 | 0 | No no-volunteer contingency. |
| 72 | 0 | No indoor-rain impact. |
| 73 | 1 | Contradicts indoor rain context. |
| 74 | 1 | No room-unavailable plan. |
| 75 | 1 | Empty invitation bullets. |
| 76 | 0 | No four-person guidance. |
| 77 | 0 | No mixed-table guidance. |
| 78 | 2 | Invitation theme only. |
| 79 | 2 | No neighbor-enjoyment line. |
| 80 | 3 | No privacy wording. |
| 81 | 3 | No permission sign. |
| 82 | 3 | No usable phone guidance. |
| 83 | 3 | No softer calls-outside wording. |
| 84 | 0 | No room-care reminders. |
| 85 | 3 | No three reminders. |
| 86 | 3 | No feedback questions. |
| 87 | 3 | No anonymous-feedback answer. |
| 88 | 3 | No warm feedback prompt. |
| 89 | 4 | Unsupported allowance conclusion; no method. |
| 90 | 5 | Compatible conclusion, missing ₹300/₹0 arithmetic. |
| 91 | 1 | Ignores three extra drop-ins. |
| 92 | 3 | No food-optional plan. |
| 93 | 3 | No category/assumption summary. |
| 94 | 0 | No run-of-show. |
| 95 | 3 | No final invitation. |
| 96 | 3 | Omits five-books and browse note. |
| 97 | 3 | No three room details. |
| 98 | 2 | No three welcome duties; nonsense math. |
| 99 | 2 | No three cleanup duties. |
| 100 | 2 | No requested recap sections. |

## Limitations

This is an assistant-output review, not an independent human benchmark. It assesses only facts and context recorded as actually supplied for each generation. Older chat facts outside the rolling window were not treated as available; that differs from ignoring information in the current prompt, external support, or retained pairs.
