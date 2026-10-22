#!/usr/bin/env bash
# Run the five-task real-API smoke and stop on missing credentials.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
. .venv/bin/activate
python -m retail_eval.run doctor
python -m retail_eval.run collect --split train --group A0 --limit 5 --trials 1
echo "Inspect the new run manifest/traces/grades before any batch job."
