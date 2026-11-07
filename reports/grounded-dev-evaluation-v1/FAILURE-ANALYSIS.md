# Grounded diagnostic failure analysis

The completed own124M grounded SFT candidate is not usable. Stop template expansion; prioritize clean broad-language training and measured compute efficiency. This is an independent read-only analysis of exposed development outputs, metric logs and CPU-mapped checkpoint metadata; no model execution or private acceptance contents were used.

## Evidence

The endpoint completed3,975updates /820,293assistant targets in8,501.7active seconds. Last100chat updates average masked CE0.01977 (median0.00260), while held-out canonical chat-family development CE moved7.0647→3.2423→3.3477 at steps0/2000/3975. This is severe template overfit, not failure to minimize training loss. Tool development CE9.6274→0.4174→0.3288 and session CE9.6082→0.6540→0.3973 do not establish autonomous behavior: their teacher-forced structures remain much closer to training than public wording.

The full public primary suite reports0/422sessions and4/453requested calls correct,115/522required readbacks with an observation,28/115faithful given an observation,116protocol failures.91turns answer 'What is the second operand?' Arithmetic requests receive unrelated display-frame or movement prose. A four-call case observed calculator253.79166666666666 but claimed737.79166666666666. Such examples support weak conditioning/template substitution, not a broker defect. Public conversation has0/25automated turn passes,19manual-pending; pending is not a pass. Long sessions0/8.

Chat occupies3,128/3,975updates (78.7%) despite64.8%of targets; primary660updates and session187. Each normalized small-target chat batch still receives a complete optimizer update. This may amplify narrow chat patterns but is a hypothesis, not causal proof. Total target exposure[10144,753004,56545,600] across successive256-position bins gives almost no final-quarter supervision.

Sources: runs/own-base-grounded-sft-diagnostic-01/metrics.jsonl and protected endpoint history; runs/own-base-dev-grounded-diagnostic-01/{primary_tools,public_conversation,four_call_sessions}.json. Existing source/receipt identities remain immutable.

## Next discriminators and viable direction

A fixed small transfer audit should compare exact training histories and retained development histories: raw greedy next-frame behavior and identical target CE with correct versus deterministically shuffled current-user text. Retain teacher prefixes/tool observations, report teacher-prefix dependence honestly, and do not turn this into another acceptance benchmark or new training data. It can distinguish narrow memorization from measurable input conditioning; shuffled text is an out-of-distribution intervention and not a clean causal estimate by itself.

Then continue the selected own base on genuinely broader, cleaned language data, subject to inventory and parity/throughput results. A20–30M-token tranche is a learning-curve experiment, not an expected cure. At the completed optimizer arm's19,996,672tokens /14,032.7seconds,100Madditional tokens costs about19.5active hours and1Babout8.1active days before speedups. Do not promise general chat from another tiny template pass. If learning fails to improve fixed natural-language loss and context sensitivity, investigate quality/optimization rather than automatically repeat.

The existing full-model MLX benchmark protocol is the efficiency gate. Preserve FP32 master/moments, optimizer resume and checkpoint parity; measure synchronized sustained work, not lazy graph construction. [Official MLX compilation guidance](https://github.com/ml-explore/mlx/blob/main/docs/src/usage/compile.rst) documents compiling stateful training, but gives no evidence of a speedup for this specific model/hardware.

[TinyStories](https://arxiv.org/abs/2305.07759) supports coherent restricted-domain language at small sizes, not general conversation/tool competence. [SmolLM2](https://openreview.net/pdf?id=3JiCl2A14H) reports2Tpretraining tokens for135M; this is reference scale, not a minimum requirement. [Compute-optimal training research](https://arxiv.org/abs/2203.15556) supports jointly considering model and data scale; its fit is not a task-specific success guarantee. No pretrained substitution is proposed.
