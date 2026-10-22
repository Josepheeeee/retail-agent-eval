#!/usr/bin/env bash
# Base environment for offline checks and Agent/Judge API collection.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock.txt
if [ ! -d external/tau-bench ]; then python scripts/fetch_references.py tau-bench; fi
python -m pip install --no-deps --no-build-isolation -e external/tau-bench -e .
python -m pip check
python -m retail_eval.run doctor
echo "Base environment ready. Training: install_train.sh; serving: install_infer.sh"
