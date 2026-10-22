#!/usr/bin/env bash
# Run J0-J4 on one frozen trajectory pool with independent human gold.
# Usage: TRACES=data/raw/frozen.jsonl GOLD=data/annotations/test_gold.jsonl scripts/linux/run_judge_matrix.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
. .venv/bin/activate
TRACES="${TRACES:?set TRACES to the frozen judge trajectory pool}"
GOLD="${GOLD:?set GOLD to the independent human gold JSONL}"
python -m retail_eval.run judge-matrix --traces "$TRACES" --gold "$GOLD"
echo "Judge matrix written under runs/. Compare J0-J4 on the same trajectories only."
