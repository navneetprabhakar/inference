# Raw own-base sampler

`base_sample.py` produces raw text continuations from explicitly selected, saved own-base campaign checkpoints. It is not a chat assistant: there are no roles, instruction wrappers, tools, downloads, or pretrained assistant weights. It is CPU-only, one thread, to avoid competing for the live trainer's MPS lock. CPU inference still uses shared system RAM and memory bandwidth.

Select a protected checkpoint by its **optimizer step**, not its token count. Inspect the names in the run's `protected.json`; do not assume a checkpoint exists. For example, after protected step 123 exists:

```sh
.venv/bin/python base_sample.py runs/own-base-foundation-01 \
  --protected-step 123 --prompt 'A bridge is built to' --max-new-tokens 48
```

`--step` admits a step in the checksummed campaign ledger's checkpoint receipts or protected inventory. If multiple saves have the same step, use `--checkpoint EXACT_BASENAME.pt`. There is no implicit latest selection. Prefer protected checkpoints because ordinary rolling checkpoints may be retired. A busy checkpoint writer causes a retryable refusal; the sampler does not acquire the GPU lock or modify any run state.

Default temperature 0 is greedy. Set `--temperature 0.8 --seed 7` for reproducible CPU sampling. The prompt plus maximum requested new tokens must fit 512 tokens; the sampler refuses overflow rather than truncating or silently using untrained positions. EOT ends generation. Standard output contains only the raw continuation; standard error identifies the checkpoint and explicitly labels this as a base model.

Before allocating the full model, the loader checks the campaign ledger checksum, frozen campaign identity, expected own-parent SHA `f029b7d3…34a4`, tokenizer and architecture, trained context 512, checkpoint filename/content SHA, payload campaign identity, and optimizer/token cursor. It compares file size with the ledger's size receipt when one exists. Historical protected inventories contain only filenames with content hashes: for those, the full digest binds bytes and length, while before/after size/inode checks detect concurrent change; there is **no independent historical size receipt**. SHA checks detect accidental corruption and establish recorded lineage, not signatures or hostile-owner attestation. Missing/retired files fail closed.

The full model must have 124,439,808 parameters and FP32 master weights. No full-model generation was performed while implementing this tool. Tiny CPU tests cover lineage, ledger/content corruption, size, context, wrong payload/cursor, explicit selection, symlinks, model size, and deterministic generation:

```sh
.venv/bin/python verify_base_sample.py
```
