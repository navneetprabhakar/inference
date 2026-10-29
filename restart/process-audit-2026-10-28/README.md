# Whole-process audit —28 October 2026

**No training or model inference performed.** Evidence-first review requested before another training phase.

- [Audit and challenged assumptions](REPORT.md)
- [Revised phased plan and decision gates](PLAN.md)
- [Fresh CPU evidence](evidence.json)
- [Reproducible evidence inspection](inspect_evidence.py)

Confirmed issues: narrow task/data support, task-conditioned output collapse, confounded evaluation and preservation pressure. Root-cause ranking remains uncertain; model capacity and broader pretraining are hypotheses, not proven fixes. Numerical correctness has bounded historical support and serialization was independently reconstructed here. The next study separates data diversity from replay pressure while measuring matched transfer.
