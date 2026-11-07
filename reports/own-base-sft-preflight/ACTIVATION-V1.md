# Hardware preflight activation candidate

Prepared for root review; not executed. The spec uses the existing `reviewed_for_hardware_preflight` state required by the runner, but preparation alone does not launch or complete the trial. No frozen runtime, source admission, optimizer selection rule, or previous receipt was edited.

- Spec: `reports/own-base-sft-preflight/activation-v1.json`
- SHA256: `6200d72f5aee26688259a95116d2e8db2d72be21faaad044e8594f0755fd2732`
- Fresh canonical output: `runs/own-base-sft-preflight-01`
- Selection: preserve-095. The completed comparison reports `no_candidate_qualified=true`; this is the frozen fallback, not a claim that preserve-095 is globally optimal or usable. The lower-loss reset-scaled arm failed the frozen combined screen.
- Parent endpoint: `step-002441-100cdf77a1c34e5be3dfc79e4a1842caead481b652d871d03115ff5d897fcefb.pt`.
- All three aligned datasets are pinned through their original receipts and separate diagnostic admission/verification receipts. The extension qualification is also pinned. Runtime and preflight protocol/code hashes are explicit.
- CPU-only `own_base_sft_preflight.validate` passed against the exact in-memory spec before writing. It verifies paths, current runtime hashes, admissions, verification receipts, qualification, configuration and STOP absence. This is not the full parent tensor/data verification or MPS test; execution performs those checks under the foreground watchdog.
- Fixed trial: 40 disposable BF16 updates, accumulation 8, microbatch 1, 48 FP32 evaluation rows, context 1024, hard 1,200-second watchdog. Existing source/work/RSS/output/disk limits remain in the pinned implementation. No checkpoint export, retry or resume.

After root review, exact launch command from the repository:

```sh
/Users/navneetprabhakar/Documents/git/image/inference/.venv/bin/python /Users/navneetprabhakar/Documents/git/image/inference/own_base_sft_preflight.py /Users/navneetprabhakar/Documents/git/image/inference/reports/own-base-sft-preflight/activation-v1.json /Users/navneetprabhakar/Documents/git/image/inference/runs/own-base-sft-preflight-01 --execute-reviewed
```

Root should verify the spec hash before launch and let the foreground watchdog own its worker. A final `hardware-receipt.json` with `state=PASS`, verified against watchdog/ledger/selection, is required before using measured throughput to freeze an SFT budget. Child-only success or a CPU preparation pass does not suffice. Useful conversation and tool behavior remain separately unproven.

Root subsequently reviewed and executed this exact spec. The watchdog-backed hardware receipt passed in113.1seconds, with40updates and48FP32evaluation rows. Root reverified artifact hashes, ledger, activation identity and selected parent. See `hardware-result-v1.json`. This is hardware evidence only; all disposable weights were released.
