#!/bin/sh
# LOCAL ONLY. Does not initialize CUDA, train, create a lease or start a VM.
set -eu
.venv/bin/python -m cloud_training.nano_sft \
 --manifest reports/corrective-corpus-v1/candidate-4k/manifest.json \
 --base runs/local-readiness-v1/base10b \
 --base-manifest-sha 7d803e32928ca9ecc1fe38bf7d47c54bca80c0996d6bb006b718cfd851975e53 \
 --tokenizer runs/ownbase-v2-data/tokenizer \
 --tokenizer-sha ad777bb448ea8fcf115835548596f9303f3ee5e85a014b0bb315567091080cc5 \
 --repo runs/nanochat-source --output runs/local-readiness-v1/preflight \
 --quality-contract reports/corrective-corpus-v1/quality-contract.json \
 --context-tokens 4096 --allow-context-extension --stage general \
 --batch-tokens 32768 --microbatch 1 --packing-buffer-size 1 \
 --epochs 2 --lr-multiplier 0.125 --seed 103 --max-updates 10 \
 --eval-rows 512 --eval-every-updates 5 --deterministic --deterministic-attention --validate-only
