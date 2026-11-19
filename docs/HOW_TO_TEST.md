# How to Test and Train `Ganesh-base` (`537M`) Locally on Apple Silicon (`mps`)

## 1. Run Contract, Guardrail, and 9-Category Evaluation Checks

From the repository root, run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ganesh.plan validate
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ganesh.plan check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m ganesh.evaluation --require-ready
```

---

## 2. Run the Verification Suite

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p "verify_*.py" -v
```

---

## 3. Rebuild the Balanced SFT v2 Dataset (`1,531` Train / `285` Val Conversations)

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/build_ganesh_sft_v2.py
```

---

## 4. Verify the local Base10B parent and both splits on MPS

With the pinned nanochat checkout and tokenizer under `runs/`, run the following from the repository root.

```bash
.venv/bin/python -m cloud_training.ganesh_sft_repair --checkpoint runs/local-readiness-v1/base10b --device mps --validate-only
```

This checks hashes, encodes both splits with the project tokenizer, reserves 256 tokens at each assistant action, and runs a finite forward pass. Training is on hold pending selected-checkpoint persistence, reload verification, and behavioral regression gates.
