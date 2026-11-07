# Executable external milestone adapter

`own_base_language_milestone.py` consumes the trainer's exact committed checkpoint request. It does not modify training code, original diagnostics, evaluation sets or root decisions. Uses frozen `base_train.document_losses` at FP32/512 on all256 original web windows and `base_train.language_diagnostics` on32 context pairs plus32 raw greedy continuations with48-token cap. No private acceptance cases.

Root prepares a protocol with explicit event/time budgets (CPU metadata only):

```
.venv/bin/python reports/language-milestone-v1/prepare_protocol.py --events N --seconds-per-event SECONDS --calendar-seconds CALENDAR --output ABSOLUTE_PROTOCOL_PATH
```

Review protocol and pin it in `external_milestone_gate.protocol`. Its series and budgets satisfy the trainer's existing schema. The fixed evaluation inventory determines worst-case target/input/attention counts; no manually guessed token cap. Seconds are operational caps, not ETA.

When trainer pauses and publishes `milestone-T-request.json`, root explicitly invokes:

```
.venv/bin/python own_base_language_milestone.py ABSOLUTE_REQUEST_PATH --request-sha256 EXACT_SHA
```

Supervisor output is the sibling runs/RUN-external-evaluation/milestone-T. Campaign budget reserves the entire worst-case targets/input positions/attention elements and lease time before child spawn; charges persist after crashes and early EOT. No automatic retry or free retry under another output path. A separate budget lock serializes launch accounting; worker exclusively owns shared runs/mps.lock and an inherited watchdog ticket.120s heartbeat,10s termination grace,18GiB RSS,1GiB swap-growth,thermal<=1,20GiB diskfloor and inherited STOP controls. Event journal reserves each forward before invocation and marks forward_returned_async after the Python call returns; this is not a GPU-completion claim. Final result publication requires explicit MPS synchronization after all scalar result reads. Attention count is sum batch*sequence_length^2, without head/layer multipliers; input-position count includes prompt recomputation on every raw generation step.

Accepted checkpoint membership, byte SHA/size, paused campaign state, exact identity/config/own-pretraining lineage, committed cursor and request/protocol binding are checked before allocation. Parent shared checkpoint lock prevents concurrent publication; GPU lock prevents simultaneous trainer use. Output records256 losses, all32 pair decisions and raw32 continuations verbatim. Incomplete/resource-aborted runs remain incomplete and fully charged. Root alone creates its existing root_reviewed_external_milestone decision after reading this result and watchdog receipt; the evaluator never decides continuation or claims conversation/tool acceptance.

Tests: check_accounting.py exercises web/masked-pair/generation cost differences, atomic budget refusal and bounds with no model/GPU. Runtime metadata and root code review are prerequisites for first real evaluation. No live checkpoint or GPU loaded during preparation.

Mandatory AC power is checked immediately before GPU allocation and at least every5seconds during evaluation. Unknown/unparseable power status fails closed. Protocol pins and result records actual Torch, NumPy and full Python versions in addition to interpreter path and code hashes.
