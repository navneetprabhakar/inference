# Guided calculator and converter acceptance

The patched guided candidate failed both preregistered gates. Keep the existing live preview. The tests used real HTTP sessions on a separate CPU loopback server and its offline broker. Each complete task required all of its turns to pass.

| Panel | Complete guided tasks | Guided turns | Expected executions | Actual broker executions | Correct / wrong | Ordinary control sessions |
|---|---:|---:|---:|---:|---:|---:|
| Original build, independent panel | 8/14 (12 required) | 50/59 | 13 | 10 | 10 / 0 | 6/6 |
| Patched build, independent new panel | 2/12 (10 required) | 34/53 | 13 | 4 | 3 / 1 | 3/5 |
| Patched build, exposed original regression | 8/14 (12 required) | 50/59 | 13 | 10 | 10 / 0 | 6/6 |

**Original panel and exposed regression.** Of six incomplete guided tasks, three failed to produce a required execution, including subtraction and a conversion that lost the supplied amount. Two reached the correct result but failed an earlier turn, respectively an incomplete permission notice and a lost source measurement. One left the conversion workflow unexpectedly and failed to acknowledge cancellation. All ten actual executions used the expected arguments and returned the expected value.

**Fresh patched panel.** Of ten incomplete tasks, nine omitted one required execution each. Five lost a prose operand, amount or correction before completion. Four missed an otherwise complete request. The tenth task executed a conversion with the stale source quantity after rejecting a correction, then reported the resulting wrong value. All four actual executions were permitted. Two ordinary controls failed their interaction rubric: the delegated decoder imitated an input prompt in one, and it proposed an off-route call blocked before dispatch in the other. No ordinary control entered the host-guided workflow or generated a broker event on either panel. No transport failure occurred.

The original and fresh panels use different wording and operation sequences. Their difference cannot isolate the effect of the patch. The paired original regression produced the same per-turn answers and failures. The change did not improve performance on that panel. This evaluation covers the explicit guided interface and ordinary routing controls only.

The three JSON results beside this report pin each implementation, suite and raw observation file by SHA-256. Complete transcripts, per-turn grading reasons and prespecified rubrics are held privately under runs/guided-acceptance-custody-01, runs/guided-acceptance-custody-02 and runs/guided-exposed-regression-01.
