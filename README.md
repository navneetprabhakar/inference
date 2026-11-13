# Own-base language model experiments

Current work uses an **own randomly initialized 537M-parameter model**, with roughly **6B base-training tokens** completed toward a conditional 10B target. The retained tuned checkpoint is still **2K-trained**; general conversation remains unreliable. Preparing 4K data does not establish 4K model capability.

As of 13 November 2026, the reviewed corpus contains **508 sessions** and **115,754 training assistant targets**. This new corpus has not been trained. The VM must remain off until an explicitly approved, budgeted restart; the latest work is local data preparation and planning.

## Start here

- [Current handoff](OWN_BASE_HANDOFF.txt): checkpoint identities, verified corpus, constraints and remaining gaps.
- [Next execution plan](OWN_BASE_NEXT_STEPS.txt): data and evaluation gates, conditional VM training, promotion and shutdown.
- [Latest corpus evidence](reports/l4-qualification-v1/long-context-campaign-v3/corpus-state.json): counts, hashes and limitations.
- [Training audit](TRAINING_AUDIT.txt): append-only history; read the newest entries, not its old current-state header.
- [Historical artifact index](reports/repository-cleanup-20261113.json): preserved plans, receipts and their superseded status.

## Repository layout

- `cloud_training/`: own-base training, SFT, evaluation, checkpoint and serving code.
- `reports/`: versioned evidence, review receipts and reproducibility scripts. Historical records are not current launch instructions.
- `own-base-candidates/`: candidate metadata and provenance; existence does not imply promotion.
- `runs/`, `data/`, `checkpoints/`: local runtime/data/weight paths excluded from Git. A clone does not include these assets; follow the handoff's verified restore paths before running dependent workflows.

The original GPT-2 implementation and results below are retained as project history. Their architecture, preview commands and service status do not describe the current 537M model. Do not restart an old service or training job based on historical instructions.

# Historical Apple Silicon experiments

The first milestone is a randomly initialized 124,439,808-parameter GPT-2 decoder running locally in PyTorch. It uses 12 layers, 12 heads, width 768, learned positions for 1,024 tokens, and a vocabulary of 50,257. Its output projection shares the input embedding weights. The vocabulary matches GPT-2's token ID range. Karpathy pads his final training vocabulary to 50,304 for hardware efficiency.

The reference is Andrej Karpathy's [Let's reproduce GPT-2 (124M)](https://www.youtube.com/watch?v=l8pRSuU81PU) and its [step-by-step implementation](https://github.com/karpathy/build-nanogpt/tree/6104ab1b53920f6e2159749676073ff7d815c1fa). His training recipe processes about 10 billion tokens, 50 times the previous project's largest 200M-token pretraining checkpoint. Laptop throughput needs to be measured before estimating that budget. This stage teaches next-token prediction. Conversation and tool use will need separate training and evaluation.

## Run the first check

With Python 3.12 and a virtual environment, install the dependency and run:

```sh
python -m pip install -r requirements.txt
python gpt2.py --device mps
```

Use `--device cpu` for the CPU path. The command builds random weights, checks the parameter count, varies the suffix of a sequence to test causal attention, and computes next-token loss on synthetic token IDs. It performs zero optimizer updates and saves no weights. On this laptop the MPS check passed with loss 11.2031. This measures wiring only.

## Historical execution

The 124M student passed foundation and pretraining gates on the M4 Air. After 2,457,600 pretraining targets and 74 supervised updates, it passed 0/12 development conversations and 0/20 pairs in each required transfer skill. That feasibility run closed at its conversation gate. Later supervised and tool experiments are summarized below. See the [result and artifacts](reports/astra-feasibility/RESULT.md) and [foundation reproduction commands](reports/astra-feasibility/README.md).

The previous project is preserved at [main commit c5b911b](https://github.com/navneetprabhakar/inference/commit/c5b911b5a4abe096f17848e1d119549e253a0092).

## Historical local conversation and tools

The historical preview used the original from-scratch GPT-2 lineage, a learned tool router, a session-scoped offline calculator and converter, explicit name memory, and a learned trace-readback model. The loopback interface shows whether a reply came from the decoder, a selected context span, or the broker's observed result.

```sh
.venv/bin/python serve_chat.py --pin reports/working-chat/live.json --watch-pin --port 8767
.venv/bin/python serve_chat.py --pin reports/working-chat/live.json --cli --tools
```

Open [the local chat](http://127.0.0.1:8767/) on the training machine. This run launched the stable preview as the local macOS service `local.forge.astra-chat-preview`. To stop that service, run `launchctl remove local.forge.astra-chat-preview`. Enable offline tools for a turn when appropriate. To inspect the original decoder without the product heads, add `--runtime raw`. The latest copy-model experiment missed the development and independent validation gates. The 100-case release set remains unscored. [Results, scorecards and working examples](reports/working-chat/RESULT.md).
