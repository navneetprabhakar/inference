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

## 4. Run Repaired SFT on the `537M` `Base10B` Checkpoint (`mps`)

After you copy or symlink `runs/` (`runs/ownbase-budget50-v1/checkpoints/step-000019074` and `runs/ownbase-v2-data/tokenizer/tokenizer.pkl`) into `runs/`, run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python cloud_training/ganesh_sft_repair.py \
  --checkpoint runs/ownbase-budget50-v1/checkpoints/step-000019074 \
  --device mps \
  --epochs 2 \
  --batch-size 4 \
  --lr 3e-5
```
