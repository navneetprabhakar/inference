# Local conversation and tool model

The experimental assistant runs on the training Mac at <http://127.0.0.1:8767/>. Enable **Allow offline tools this turn** when asking it to calculate or convert. A new chat starts with its own history. The UI shows the actual adapter call, arguments, result and response origin.

A useful starter sequence is “Add 14 and 37,” “Now multiply that result by two,” then “Repeat the last result.” The first two turns each need tool permission. A name can be set, corrected, recalled and forgotten within one session. Names stay in memory on this Mac. The UI separates host replies and observed tool results from decoder-generated English.

## General conversation

Three conversational students were trained from the same randomly initialized GPT-2 lineage. The first mixed fit passed 0/20 development conversations as a raw model. The second fit improved on familiar wording but its raw model still passed 0/20 whole sessions. In a paired comparison it passed 11/16 with training wording and 1/16 when the question was independently paraphrased and the facts stayed fixed. It supplies the decoder for the live experimental preview.

The third student added learned attention to copy tokens from earlier turns, alongside counterfactual training. All 5,500 optimizer steps finished in 81m55s. It used 4,280,032 training positions and 1,053,245 positive assistant targets. It answered both variants correctly on 9/28 internal changed-fact pairs, with prior gold dialogue supplied. The two whole-conversation sets below used the model's own preceding answers. Each has 20 sessions and 40 substantive turns. The validation set was frozen separately before this endpoint was chosen.

| Final copy student | Automatic whole sessions | Independently reviewed whole sessions | Independently reviewed turns | Correct first calls |
|---|---:|---:|---:|---:|
| Development A, raw decoder | 0/20 | 1/20 | 5/40 | 1/6 |
| Validation B, raw decoder | 0/20 | 2/20 | 8/40 | 0/6 |
| Development A, complete assistant | 0/20 | 1/20 | 7/40 | 4/6 |
| Validation B, complete assistant | 0/20 | 0/20 | 6/40 | 1/6 |

The reviewers credited some garbled responses with identifiable meanings. Removing the borderline credits gives the raw model 0/20 complete sessions on each set. The B product answered six individual turns but never sustained a complete session. The development gate requires 12/20 complete sessions and subgroup minima. The final copy weights are retained for research and the sealed 100 release sessions remain unscored. See [exact run and model lineage](../copy-chat/endpoint.json), [raw transcripts and judgments](../copy-chat/adjudication-raw.json) and [product transcripts and judgments](../copy-chat/adjudication-product.json).

The full sequential logs on this Mac are [raw A](../../runs/copy-final-a-raw/transcripts.jsonl), [raw B](../../runs/copy-final-b-raw/transcripts.jsonl), [assistant A](../../runs/copy-final-a-assistant-preview/transcripts.jsonl) and [assistant B](../../runs/copy-final-b-assistant-preview/transcripts.jsonl).

## Live preview and observed defects

A fresh 15-session usability run used the live previous student with learned tool routing, explicit name memory and host rendering of actual tool observations. It passed 6/15 complete sessions and 17/34 turns. Name memory passed 3/3, everyday prose 0/5, single-tool sessions 2/3, dependent-call sessions 1/2 and tool-boundary sessions 0/2. All eight adapter executions were real. Two subtraction calls sent the wrong arguments. No prohibited execution occurred. Counts and incorrect arguments are preserved in the [pre-repair usability report](../live-usability-scope-v2/report.md).

The language continuation experiment lowered held-out loss on all three sources. The final checkpoint missed the predeclared minimum gain, so it was retained separately and never used to initialize a conversational student. All student training and serving stayed local with zero paid API or cloud spend.

The subtraction fix now asks for clarification when operand order is ambiguous. On the fixed CPU development regression it passed 24/24 cases, up from 10/24, and passed seven additional multi-step checks. The repaired live service was restarted and exercised through real HTTP turns. It returned 37 for “Subtract 9 from 46,” dispatched a second call to add 6 and returned 43, then repeated 43 with zero new calls. The [repair evidence](../explicit-command-order-v2/report.md) distinguishes host serialization from learned proposals.

## Learning when to ask a follow-up

A separate from-scratch dialogue-act model learned when to ask for missing tool arguments and how to classify a follow-up. Its second fit has 36,118 coefficients. On held-out wording it classified 79/79 accepted openers and 68/74 accepted pending turns correctly, accepting 56% and 71% of those inputs respectively. The product used typed argument collection and the existing permission-checked broker. [Classifier fit](../slot-dialogue/README.md).

On a prospective test of automatic entry, it completed 5/16 task sessions versus 0/16 for the previous assistant. It passed 20/42 task turns versus 6/42, and both made zero calls on 11 unrelated control turns. One correction was discarded, leaving a stale quantity that reached the converter. The first trial session also exposed a per-turn initialization error. It counted as failed in the primary result; replay after repair passed. The automatic mode missed the required 10/16 and zero incorrect calls, so it was withheld from the live pin. [Paired acceptance decision](../slot-dialogue/acceptance-prospective.json).

## Explicit guided tools

A separate research build let the user enter a calculator or conversion flow and give missing arguments over several turns. It passed 18 local integration regressions, 264 parser checks and a real mobile-browser calculation. External use was substantially weaker.

| Actual HTTP test | Complete guided sessions | Passing guided turns | Exact required calls | Incorrect executions |
|---|---:|---:|---:|---:|
| First guided build, prospective panel | 8/14 | 50/59 | 10/13 | 0 |
| Final guided build, new prospective panel | 2/12 | 34/53 | 3/13 | 1 |
| Final build, original panel reused as a regression | 8/14 | 50/59 | 10/13 | 0 |

The twelve-session panel required ten complete tasks and zero incorrect executions. In one case a rejected correction left an earlier quantity active. The next unit reply triggered a conversion using the obsolete quantity. No forbidden or control calls executed. The automatic and explicitly guided research builds are excluded from the public server. The current live pin retains the repaired direct-command assistant. See the [original report](../guided-external-acceptance/original-result.json), [fresh final report](../guided-external-acceptance/final-fresh-result.json) and [exposed regression](../guided-external-acceptance/exposed-regression-result.json).
