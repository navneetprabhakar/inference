# Gradual architecture growth: prospective choices

**Keep the live 124M continuation unchanged. The first size experiment, if evidence warrants one, is 16 layers at width768:152.79M total. The1B ceiling is permission to investigate, not a target to fill.**

These are exact counts for our current `gpt2.py`, including tied token/output embeddings, learned positions, biases and LayerNorm. They are architecture choices, not implementations or launches. `calculate.py` uses integer arithmetic only; `options.json` records exact components and current source hash. No model allocated.

| Choice | Depth × width / heads | Exact total | FP32 weights+gradients+Adam floor | Weights+moments checkpoint floor | Compute proxy vs current |
|---|---:|---:|---:|---:|---:|
| Current |12×768 /12|124,439,808|1.854GiB|1.391GiB|1.00×|
| Modest depth increase |16×768 /12|152,791,296|2.277GiB|1.708GiB|1.24×|
| Depth-only intermediate |30×768 /12|252,021,504|3.755GiB|2.817GiB|2.07×|
| Wider intermediate |23×1024 /16|342,226,944|5.100GiB|3.825GiB|2.74×|
| Approximately500M |22×1280 /20|498,545,920|7.429GiB|5.572GiB|3.95×|
| Below1B ceiling |32×1536 /24|985,379,328|14.683GiB|11.012GiB|7.77×|

- **Exact formula:** `(50,257+1,024)d + L(12d²+13d) + 2d`. Per block:12d² dense weights;9d linear biases;4d affine LayerNorm. Output embedding is tied and counted once. Token embedding alone is38,597,376 parameters at width768.
- **Memory is a floor, not a fit claim:**16bytes/parameter assumes FP32 weights, gradients and two Adam moments; BF16 autocast does not halve those. Excludes activations, full-vocabulary logits, allocator/cache, optimizer temporaries, host copies and checkpoint operations. One checkpoint is at least12bytes/parameter; rolling retention and atomic replacement multiply storage requirements. The985M floor already exceeds the previous12GiB GPU guard; that guard cannot be silently relaxed. Hardware fit requires a separate reviewed measurement.
- **Compute is arithmetic, not an ETA:** proxy per forward token at sequence512 is `24Ld² + 4L·512·d + 2·50,257·d`. It includes full-square attention upperbound work and vocabulary projection, excludes smaller operations/backend effects. Training adds backward work. More layers are sequential; larger widths can improve hardware utilization but increase quadratic matrix cost. Neither effect establishes actual throughput. All choices retain head dimension64 and context1024.
- **Growth is not a trivial checkpoint resume:** depth-only retains tensor dimensions for existing layers, but inserting layers changes the function and optimizer mapping. Width changes invalidate almost every tensor shape. No function-preserving growth method is implemented or verified here. A fresh larger random-initialized model remains within the own-model objective, but discards learned weights and requires new training; transferring only our own weights requires a separately tested migration and explicit optimizer treatment. Never substitute a pretrained student.
- **Decision gate:** first inspect the current run's fixed heldout explanatory/narrative losses, correct-versus-swapped context conditioning, original-web retention and raw continuation behavior. Better training loss alone does not justify growth. If heldout transfer improves and then plateaus while data and compute remain available, compare a modest152.79M candidate against124M on the same admitted data and fixed heldout evidence, using a predeclared wall/compute budget. If conditioning/generalization remains weak, prioritize source quality/diversity and learning diagnosis; more parameters alone is not a resolution.
- **Later sizes remain conditional:**252M tests added depth without widening;342M is an alternative width/depth tradeoff, not an obligatory subsequent step.500M and985M should follow demonstrated transfer per unit compute and actual memory fit, not the new cap alone. Fixed data repeated over a bigger model does not create additional unique evidence.

Existing primary-source review: `reports/approach-reassessment-v1/model-recipes.md`. MobileLLM and SmolLM are useful deep/thin architecture references, but their large token budgets and posttraining do not predict success for our local run. Historical research notes mentioning a200M cap are superseded by the user's1B allowance; historical evidence and frozen experiments remain unchanged. No new web research was needed for exact local parameter accounting.
