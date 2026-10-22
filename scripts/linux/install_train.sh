#!/usr/bin/env bash
# Isolated four-GPU Judge SFT environment. Run on the H20 host.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
python3.12 -m venv .venv-train
. .venv-train/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock.txt -r requirements-train.txt
if [ ! -d external/LlamaFactory ]; then python scripts/fetch_references.py LlamaFactory; fi
python -m pip install --no-deps -e external/LlamaFactory
python -m pip install --no-deps --no-build-isolation -e .
python -m pip check
python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), 'gpus', torch.cuda.device_count())"
