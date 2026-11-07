# Approach reassessment: change the learning plan

## Current user-authorized parameter ceiling

On 2026-11-08, after this review, the user explicitly authorized increasing the model ceiling to **1 billion total parameters**. This supersedes the earlier200M ceiling for prospective model selection. Random initialization, own-weight ancestry, local-only execution and zero paid compute remain in force; the user did not authorize pretrained student substitution or paid/cloud training. Historical experiments and their parameter counts/specifications stay unchanged.

Do not automatically instantiate a1B model. Select architecture and size using measured training throughput, full optimizer/activation memory, tokenizer efficiency and attainable processed-data budget. A larger undertrained model is not an established improvement. The already frozen124M MLX benchmark remains a useful baseline and is not resized in place. Any larger-model feasibility run requires a new bounded disposable specification before execution. References below to the former cap describe the research scope at that time, not the current authorization.

The user subsequently confirmed gradual increases. A metadata-only construction of the existing architecture (no weights allocated, no GPU) gives a concrete depth-only ladder:12layers=124,439,808parameters;18layers=166,967,040;24layers=209,494,272;36layers=294,548,736, all at width768 and the current tokenizer. This is a comparison inventory, not an activated architecture or promise that each rung improves quality. FP32 weights+gradients+twoAdam moments alone occupy approximately1.85/2.49/3.12/4.39GiB respectively; activations, logits, runtime caches, temporary copies and OS memory are additional. These counts do not prove fit or throughput. Any growth of existing weights needs a separate explicit initialization/optimizer policy and tests that original behavior is preserved at the expansion boundary; ordinary random layer insertion cannot be labeled seamless continuation.

2026-11-08. User requested parallel primary-source research of open-source conversational models, their training and datasets. This decision supersedes treating narrative-only continuation as the default recovery run. It does not activate GPU training, change acceptance, or substitute pretrained student weights.

## Decision and rationale

Change the approach in three places: meaningful language exposure, task coverage in posttraining, and explicit compute planning. Preserve the own-base objective and current checkpoint as the control. Two failed SFT runs and a strong train/development gap do not support another finite-template round. Thirty million additional story tokens are a useful possible component, not an evidenced cure.

Small open models demonstrate that the parameter cap is not categorically impossible. However, strong conversational reference models train at enormous scale; newer small tool specialists still use billions of tokens and often explicitly do not converse. Do not transfer narrow benchmark scores, advertised local inference, constrained decoding, or self-reported demonstrations into a claim of our joint usability.

Our own selection process also merits correction. Everyday dialogue was already available but eventually removed as a whole cohort, while summaries/rewrites remained. The second SFT gives chat about79% of update opportunities despite65% of assistant targets. Neither fact proves the cause of failure, but both are concrete, testable design issues. Existing assistant-only masking and real tool execution are already implemented; proposing them again is not progress.

## Next work, in priority order

1. Finish the bounded full-model MLX correctness/sustained-speed measurement, fixing the discovered worker/controller interface issues first. Keep Torch if correctness or practical speed gain fails. No new optimizer search or architecture rewrite is justified yet.
2. Audit existing conversational source exclusions and family grouping. Recover eligible ordinary conversation coverage under a new prospective policy, preserving known bad examples, historical splits and protected-case exclusions. Avoid a duplicate dataset download and avoid retrospectively cleaning validation for a better score.
3. Prepare a bounded fixed-source intake of Cosmopedia simple expository text. Mix with narrative and a separately verified broad-English lane where available. Exact percentages await measured yield; no unsupported30M web allocation or silent substitution.
4. Freeze a substantive language-learning experiment and subsequent matched conversational/tool evaluation. A planning range of hundreds of millions toward low billions of additional targets is more consistent with the evidence than treating another2M-token probe as a repair. It is not a minimum or success guarantee. Final budget, throughput, checkpoint milestones and stop conditions must be concrete before launch.
5. Rebuild the SFT mixture around complete short conversations, grounded transformations and execution-backed tools. Measure optimizer-step share as well as target share. Progress single-call selection/arguments, actual-result readback and clarification/correction before long dependencies, while retaining language examples. Use unseen wording and unseen numeric domains as separately reported diagnostics, then unchanged joint-session acceptance.

The dataset researcher's2M-per-arm proposal is retained as an independent suggestion, **not adopted as a quality verdict or automatic next run**: its low exposure could make a negative result uninformative. Similarly, proposed mixture fractions are hypotheses, not literature-established optima. Prefer fewer informative runs with meaningful exposure to a succession of tiny comparisons.

At the older124M throughput reference,1B additional targets is about8.1active days and2B about16.2, before evaluation/checkpoint/cooling time. Backend results may change this; smaller-model rates cannot be inferred from parameter count alone. No defensible usable-model completion ETA exists. The research does not establish a guaranteed successful recipe within the constraints.

## Evidence inventory

- `compute-and-method.md`: local token/parameter arithmetic, nanochat, repetition, small-budget negative examples, filtering audit.
- `datasets.md`: source sizes, provenance/license metadata, prior local use, proposed intake and curriculum; suggestions are not activation.
- `tool-conversation.md`: primary tool-training recipes, sub200M specialist counterexamples, local loss/update accounting and evidence limits.
- `model-recipes.md`: small-model architecture/pretraining/posttraining recipes and inspectable local-hardware examples, when finalized.

No public model weights are adopted. No private acceptance cases opened. No claim of capability follows from this research or from eventual faster training alone.

## Execution follow-up

Read-only inspection of the original v3 candidate confirms the Everyday split problem: all811 pre-custody histories were grouped into only five first-user greeting families (390Hi,154Hey!,129Hello,128Hi there,10Hi.). Every group was assigned train. The cause therefore exists before custody filtering; it is not explained by a lack of substantive task diversity. `everyday-split-audit.json` pins the database and builder. Historical assignments remain unchanged. A prospective cohort design must group substantive scenario/near-duplicate histories while retaining full conversation context and all protected boundaries.

Public Cosmopedia metadata shows the smallest complete official shard is1,174,424,341bytes, larger than the earlier1GiB proposed intake cap. Root authorizes a new prospective1.25GiB compressed cap for that exact hash-bound shard, with3GiB total additional output,20GiB disk floor,30minute wall cap andSTOP protection. This is an explicit bounded intake adjustment, not permission for the full122GB subset, unbounded download, or training admission. Downloader/plan review remains required before acquisition.
