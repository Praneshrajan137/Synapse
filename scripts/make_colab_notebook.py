"""Generate notebooks/train_synapse_agents.ipynb — a Colab/Kaggle GPU training
notebook for SYNAPSE. Run locally: ``python scripts/make_colab_notebook.py``.

Kept as a generator (not a hand-written .ipynb) so the notebook JSON is always
valid and reviewable as plain Python.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "train_synapse_agents.ipynb"

REPO = "https://github.com/Praneshrajan137/Synapse.git"


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": text.strip("\n").splitlines(keepends=True),
    }


cells = [
    md(
        """# SYNAPSE — Agent Training (Colab / Kaggle, free GPU)

Trains the SYNAPSE agents that have a **real** training loop and produces
content-hashed checkpoints + a `TrainResult` proving the loop took real
gradient steps (ADR-042).

**Honest scope (what this actually trains):**
| Agent | Loop | This notebook |
| --- | --- | --- |
| `demand_prophet` | real CRPS gradient loop (HGT-TFT hybrid) | **full GPU training** |
| `inventory_sentinel` | analytical (closed-form newsvendor + conformal) | calibration run (no GPU needed) |
| other 6 agents | **no `train.py` yet** | not trainable until their loops are written (future work) |

So this notebook makes `demand_prophet` serve a **real model** (not a fallback),
which is what turns its live confidence from the consensus-derived floor into a
genuine conformal-calibrated signal.

> Runtime → Change runtime type → **GPU** (T4 is plenty) before running.
"""
    ),
    md("## 1. Check the GPU"),
    code(
        """
import subprocess, sys
print(subprocess.run(["nvidia-smi"], capture_output=True, text=True).stdout or "NO GPU — set Runtime>GPU")
"""
    ),
    md("## 2. Clone the repo"),
    code(
        f"""
import os
if not os.path.isdir("Synapse"):
    !git clone --depth 1 {REPO}
%cd Synapse
!git log --oneline -1
"""
    ),
    md("## 3. Install dependencies (GPU torch + the agent stack)"),
    code(
        """
# CUDA torch (Colab provides CUDA); pinned to the repo's supported range.
!pip -q install "torch>=2.2,<2.4"
!pip -q install -e packages/
!pip -q install -r packages/requirements.txt
!pip -q install -r agents/demand_prophet/requirements.txt
!pip -q install "lifelines>=0.27,<0.31" "pymoo>=0.6,<0.7" jsonschema pyyaml || true
print("deps installed")
"""
    ),
    md(
        """## 4. Train `demand_prophet` (real, multi-epoch, GPU)

This runs the genuine CRPS gradient loop (`loss.backward()` / `optimizer.step()`),
fits the conformal calibrator on a holdout, and writes a content-hashed
checkpoint. Bump `--epochs` for a stronger model (50 is a good start).
"""
    ),
    code(
        """
import os
os.environ["PYTHONPATH"] = "."
# Full training (NOT --smoke). Writes the checkpoint + artifacts/training/demand_prophet.json.
!python -m agents.demand_prophet.training.train --epochs 50
"""
    ),
    md("## 5. Prove the model is real (substance gates) + inspect the result"),
    code(
        """
import os
os.environ["SYNAPSE_SMOKE_RUN"] = "1"  # let the runtime gates read artifacts/
# Analytical agent (no GPU) — calibration on real residuals:
!PYTHONPATH=. python -c "from agents.inventory_sentinel.training.train import train; print(train(smoke=True))"
# Substance gates (ADR-042): real gradient steps + nominal interval coverage
!PYTHONPATH=. python -m scripts.audit.training_truth --check || true
!PYTHONPATH=. python -m scripts.audit.calibration_truth --check || true
import json, glob
for p in glob.glob("artifacts/training/*.json"):
    print(p); print(json.dumps(json.load(open(p)), indent=2)[:1200])
"""
    ),
    md(
        """## 6. Package the checkpoint for the live deployment

Download the zip, then register it so the live `demand_prophet` loads it via
its `ModelRegistry`. Two options:

**A) MLflow (preferred).** On the VM, the MLflow server runs at `:5000`. From a
machine with IAP/SSH access to the VM:
```bash
# copy the checkpoint up, then log it as the demand_prophet model
gcloud compute scp demand_prophet_checkpoint.zip synapse-demo:~/  --tunnel-through-iap --zone=asia-south1-a
# unzip + `mlflow models` / register under name the agent expects (see agents/demand_prophet/config.py)
```

**B) Bind-mount the checkpoint** into the agent container and point
`MODEL_CHECKPOINT_PATH` at it (see `agents/demand_prophet/inference/serving_model.py`).

Either way, restart `synapse-demand-prophet` and its `/health` will show
`model_loaded: true`, and live decisions will carry a real conformal-calibrated
confidence.
"""
    ),
    code(
        """
import glob, zipfile, os
ckpts = glob.glob("artifacts/**/*.pt", recursive=True) + glob.glob("artifacts/**/*.ckpt", recursive=True) + glob.glob("artifacts/training/*.json")
with zipfile.ZipFile("demand_prophet_checkpoint.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in ckpts:
        z.write(f); print("added", f)
print("\\nDownload demand_prophet_checkpoint.zip from the Colab file browser (left panel).")
try:
    from google.colab import files  # type: ignore
    files.download("demand_prophet_checkpoint.zip")
except Exception:
    pass
"""
    ),
]

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
        "accelerator": "GPU",
        "colab": {"provenance": []},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print(f"wrote {OUT.relative_to(ROOT)} ({len(cells)} cells)")
