# Small own-base model recipes: evidence review

Reviewed 2026-11-08. Primary-source, read-only research; no foreign weights loaded, no model scored, no GPU work. Counts below include embeddings where explicitly stated or calculated. Author-reported results are not independent reproductions. This review does not authorize training or substitute pretrained weights.

## Decision-relevant findings

- The <=200M cap does not make conversation impossible. Published small models demonstrate some instruction following, but even heavily trained ones remain weak. Neither their huge token budgets nor hobby-project claims establish the minimum budget for our goal.
- Our next learning experiment needs broader language and varied conversation, with held-out behavioral evidence. Another narrow template-SFT round is unsupported by our observed memorization/generalization gap.
- The most directly relevant implementation reference is **Gab**, an inspectable Apple-Silicon random-init model. It is not a low-token success: its card reports **33.88B pretraining tokens**.
- **Genesis/Particle at about2B tokens** are useful hypotheses, not established dependable assistants. **L20-Edu at13B** has much stronger benchmark documentation, but its reported metrics still do not demonstrate usable conversation or tool execution.

## Comparable recipes and evidence

| Project | Total parameters and training | What the evidence establishes; important limits |
|---|---|---|
| **SmolLM1** | Published135M;600B tokens for135M/360M. SmolLM-Corpus, deep/thin GQA, tied embeddings,49,152 vocabulary, trapezoidal schedule with20% cooldown. | Open recipe and checkpoints; a large-budget reference, not evidence600B is necessary. [Author release](https://huggingface.co/blog/smollm) |
| **SmolLM2-135M** | **134,515,008**, calculated from released configuration;2T tokens. FineWeb-Edu,DCLM,TheStack and curated data. SFT smol-smoltalk, then UltraFeedback DPO. | Card reports IFEval29.9 and substantial limitations. Family function-calling claims explicitly concern1.7B, so cannot be assigned to135M. [Model card](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct), [configuration](https://huggingface.co/HuggingFaceTB/SmolLM2-135M/raw/main/config.json) |
| **MobileLLM** | Published125M including embedding accounting;1T tokens; deep/thin,GQA,tied embeddings,SwiGLU. | Actual chat evaluation:125M MT-Bench2.33/10, layer-sharing variant2.52. Better than earlier tiny baselines remains weak conversation. Headline API parity with Llama2-7B concerns350M, outside our cap. [Paper](https://arxiv.org/html/2402.14905v2) |
| **L20-Edu** | **134,515,008**;10B FineWeb-Edu plus3B curated continuation;random initialization;single48GB L20. | Six-task mean.4150 versus SmolLM.4767;87.1% ratio is descriptive, not equivalent capability. Initial10B averaged38.5k tokens/s (~72GPU-hours). No chat-quality benchmark demonstrated in reviewed material. [Paper](https://arxiv.org/html/2606.22189v1) |
| **Genesis152M** | Author151.8M total/122.8M nonembedding;2B pretraining;singleA10080GB;hybrid linear/full attention. | Low-token released research artifact, with five knowledge/commonsense scores and explicit brittle-instruction/math limitations. Does not establish reliable chat/tools or causal advantage from hybrid architecture. [Author card](https://huggingface.co/guiferrarib/genesis-152m-instruct) |
| **Particle1.0** | Author~100M;12layers,width768,custom32k tokenizer;first~2B FineWeb-Edu tokens. Exact total not independently counted here. | Random-init claim;smol-smoltalk first user/assistant pairs plus greeting seeds. No quantitative conversation benchmark found in reviewed card. [Author card](https://huggingface.co/prathamkode/particle-1.0) |
| **Gab** | **99,753,216**;13layers,width768,10k vocabulary,tied embedding;33,882,142,110 pretraining tokens;1,016,529,229 fine-tuning stream tokens. | Author reports short English conversations on Mac Studio; full code/weights available. No independently reproduced chat score, training duration or exact Studio configuration established here. Fine-tuning stream count is not assistant-target count. [Author card](https://huggingface.co/gszauer/Gab100M) |

### Inspectable details worth transferring as hypotheses

**SmolLM2:** the released small-model SFT recipe uses two epochs, LR1e-3, cosine schedule,10% warmup, BF16 and8,192-token maximum sequences. This is a recipe for an already extensively trained base, not a justified LR for our weak base. Its real conversational corpus is a qualitatively different signal from our generated state templates. [SFT configuration](https://raw.githubusercontent.com/huggingface/alignment-handbook/main/recipes/smollm2/sft/config_smol.yaml), [post-training recipe](https://github.com/huggingface/alignment-handbook/blob/main/recipes/smollm2/README.md)

**Gab:** pretraining uses its own corpus plus Cosmopedia v2; chat uses its own corpus plus SmolTalk. The MLX source implements random parameter initialization, fused causal attention, AdamW(.9,.999), clipping1, warmup/cosine3e-4→3e-5 and checkpointed optimizer state. Its finetuner starts a fresh optimizer and masks loss to assistant replies including end markers. These are inspectable engineering patterns, not demonstrated M4 throughput. [Repository](https://github.com/gszauer/Gab), [pretrainer](https://raw.githubusercontent.com/gszauer/Gab/main/pretrainer.py), [finetuner](https://raw.githubusercontent.com/gszauer/Gab/main/finetuner.py)

**L20-Edu:** continuation includes educational web, scientific papers,Wikipedia,StackExchange,math and small tutorial/reasoning fractions. SFT uses426,842 filtered rows. Released weights interpolate87.5%SFT/12.5%base, selected using the same six-task benchmark; selection bias and one training seed limit inference. The card exposes Transformers/safetensors and points to evaluation artifacts. Browser file-tree access failed, so code/log/checkpoint ancestry has **not** been independently audited. Its negative RLVR result also argues against expecting reward tuning to create missing basic competence. [Release card](https://huggingface.co/AliceYin/l20-edu-135m)

**Genesis:** claimed mixture is51%FineWeb-Edu,22%DCLM,12%FineMath,8%StackEdu,5%Cosmopedia,2%synthetic. It reports WSD,peakLR1e-3 and one smol-smoltalk epoch. PyPI repeats the card, not an independent validation. Training logs, complete ancestry, duration and exact weight count remain unverified. Do not adopt its much more complex hybrid implementation on the strength of marketing comparisons. [Package description](https://pypi.org/project/genesis-llm/)

## Larger and narrower references: boundaries

- **SmolLM3** is3B,11.2T tokens and reported384H100/24days, with staged web/code/math data and mid-training/SFT/DPO. Useful data-engineering reference; outside the parameter/compute envelope. [Author release](https://github.com/huggingface/blog/blob/main/smollm3.md)
- **OpenELM** begins270M; **OLMo2** reviewed smallest release1B. They are transparency/process references, not qualifying candidates. OpenELM's~1.8T describes its data pool and must not automatically be treated as consumed tokens. [OpenELM card](https://huggingface.co/apple/OpenELM-270M), [OLMo release notes](https://docs.allenai.org/release_notes/olmo-release-notes)
- **TinyStories** shows coherent simplified stories at very small sizes; it does not establish general instruction following, correction/recall or tool interaction. [Original paper](https://arxiv.org/abs/2305.07759)

## Implications for our124M local run

1. **Measure efficiency before choosing the token commitment.** Our measured~1,425tokens/s implies2B≈16.2 continuous active days and13B≈105.6days, excluding evaluation/checkpoint/downtime. These are arithmetic planning estimates for the existing model, not predictions for other architectures. MLX speedup is still unmeasured.
2. **Compare useful text per second, not only tokens per second.** Gab's10k vocabulary saves embedding/softmax work but increases token fragmentation. Our tied50,257×768 embedding costs38,597,376 parameters; Gab's10k×768 costs7.68M. A tokenizer change needs a fresh model and retokenized corpus; evaluate compression on held-out ordinary prose, numbers and tool JSON before any restart.
3. **Architecture is a secondary controlled hypothesis.** SmolLM2's30×576 allocates~106.2M nonembedding parameters versus28.3M embedding; modern deep/thin designs are plausible. More layers may reduce laptop throughput. Compare fixed wall time and common raw-text evaluations, rather than trusting equal-token comparisons across tokenizers.
4. **Choose a staged language budget with stopping evidence.** A2B-scale broad-language path is a defensible research hypothesis from low-budget releases, not a promise of usability. Start with a smaller predeclared tranche and evaluate base continuation, unseen prompt conditioning and a fixed modest conversation probe. Continue only with measured improvement. Avoid another extensive infrastructure campaign before a discriminating result.
5. **Preserve our goal and provenance.** Public synthetic training text can teach our randomly initialized student without copying pretrained weights. Data rights/custody still need verification. No foreign model performance has been reproduced in this review; no broad success claim is warranted.

The existing MLX controller work is preserved and paused for approach review. No runnable benchmark activation or new training run was launched.
