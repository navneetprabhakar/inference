# GPT-2 from scratch on Apple Silicon

The first milestone is a randomly initialized 124,439,808-parameter GPT-2 decoder running locally in PyTorch. It uses 12 layers, 12 heads, width 768, learned positions for 1,024 tokens, and a vocabulary of 50,257. Its output projection shares the input embedding weights. The vocabulary matches GPT-2's token ID range. Karpathy pads his final training vocabulary to 50,304 for hardware efficiency.

The reference is Andrej Karpathy's [Let's reproduce GPT-2 (124M)](https://www.youtube.com/watch?v=l8pRSuU81PU) and its [step-by-step implementation](https://github.com/karpathy/build-nanogpt/tree/6104ab1b53920f6e2159749676073ff7d815c1fa). His training recipe processes about 10 billion tokens, 50 times the previous project's largest 200M-token pretraining checkpoint. Laptop throughput needs to be measured before estimating that budget. This stage teaches next-token prediction. Conversation and tool use will need separate training and evaluation.

## Run the first check

With Python 3.12 and a virtual environment, install the dependency and run:

```sh
python -m pip install -r requirements.txt
python gpt2.py --device mps
```

Use `--device cpu` for the CPU path. The command builds random weights, checks the parameter count, varies the suffix of a sequence to test causal attention, and computes next-token loss on synthetic token IDs. It performs zero optimizer updates and saves no weights. On this laptop the MPS check passed with loss 11.2031. This measures wiring only.

## Current execution

The tokenizer and decoder parity checks passed on CPU and MPS. The 124M student memorized an eight-target batch in seven updates. A separate 999,424-target diagnostic pilot improved held-out loss on both text sources. The run artifacts include generated samples and the checkpoint inventory. See the [feasibility report](reports/astra-feasibility/README.md) for the measured results and reproduction commands.

The previous project is preserved at [main commit c5b911b](https://github.com/navneetprabhakar/inference/commit/c5b911b5a4abe096f17848e1d119549e253a0092).
