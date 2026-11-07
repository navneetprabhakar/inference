# Real own-base development evaluation — activation v1

Prepared for root review; no inference launched by this preparation.

- Candidate: `own-base-candidates/sft-diagnostic-01/manifest.json`, SHA256 `504f0117e548688ebdd782e1041f768347b8ca9a9cac09d4d65e206475b241bd`; development candidate, not approved for release.
- Specification: `activation-v1.json`, SHA256 `44c7915f5f1d76f2389f14268f50e1fdfc71273b715658237097425a5114b0fd`.
- Exact order/inventory: primary tools422sessions/583turns; four-call sessions8/24; public conversation12/25. Total442sessions/632turns. No subset, source-answer substitution, private-gate access or fallback.
- CPU-only preparation passed `own_base_dev_run.validate_spec` and `read_inputs`: every current runtime/corpus byte pin, canonical case hash, receipt/freeze binding and full session/turn count. No candidate weights were loaded and no GPU operation ran. Runtime candidate lineage/weight verification remains mandatory in the runner.
- Exact selected device: MPS FP32, real greedy decoder,256-token reply reserve, complete shared Chat history and real broker observations. Existing call quotas do not bound decoder frames because denied proposals can continue.
- Global ceilings:4096frames;1,048,576reserved and actual generation tokens;938,999,808reserved input positions;846,600,863,744reserved attention cells. These use worst-case768-token prefix per frame. They are resource ceilings/accounting proxies, not a guarantee all possible trajectories complete or a FLOP count. Early EOT does not refund reservations.
- Wall ceiling24hours includes setup/verification/load/evaluation. This is an operational cap, not an ETA. Heartbeat120seconds; termination grace10seconds; process-group RSS18GiB; swap growth1GiB; free disk20GiBminimum; output2GiB; thermal≤1. Inherits root, foundation, SFT source, all optimizer-arm and destination STOP paths. Output must be fresh `runs/own-base-dev-diagnostic-01`.
- Resource/infrastructure aborts preserve available traces and mark the run incomplete; no full aggregate result is permitted. No automatic retry or silent budget expansion. All manual rubrics remain pending until actually adjudicated. Even a completed development run is not final acceptance or release approval.

Root-reviewed launch from repository root:

```sh
.venv/bin/python own_base_dev_run.py run reports/own-base-dev-evaluation-v1/activation-v1.json --expected-spec-sha256 44c7915f5f1d76f2389f14268f50e1fdfc71273b715658237097425a5114b0fd
```

Root reviewed the exact activation hash and reran metadata/input checks for all442sessions/632turns, then launched the foreground runner under caffeinate. Log: `runs/own-base-dev-diagnostic-01-worker.log`. No result is claimed until the full runner output and manual-pending cases are reviewed.
