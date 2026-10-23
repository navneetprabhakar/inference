# Approved second foundation stage

Resume own 15,191,712-parameter checkpoint at step 1173 with unchanged optimizer, scheduler, RNG and exact data cursor (600,576 sequences). Run at most 572 updates / 74,973,184 new targets to step 1745 / 228,720,640 total targets. Stop for review regardless of results. This reaches the cumulative +149,946,368-target mandatory progress gate relative to step 601.

GPT-6 Sol (`gpt-6-sol`) replaces Luna for independent review. No SFT, correction generation, further stage or full run authorized. Keep the frozen comparable full-window evaluation unchanged; record generated BOS markers and first-document text separately. Teacher-model change prevents interpreting Luna/Sol score differences as learning alone.

Three-hour stage cap within the preserved original eight-hour deadline; 80M current-stage processed positions, 320M original aggregate cap including all prior 77,705,855 positions. Unchanged finite checks, 12GiB memory caps, 512MiB swap-growth cap from original baseline, 60GiB disk floor, AC and thermal stops. Full recoverable state every 100 updates and final checkpoint; exact CPU roundtrip and independent FP32 validation required.

Mandatory +150M progress gate: original fixed NLL improves at least .10 nats, conservative coherence at least 20/100 and gain at least ten percentage points over the original 0/100. Regardless of pass, stop and seek owner review. Formal English gate remains unpassed.
