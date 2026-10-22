#!/usr/bin/env bash
# Validate the local engineering state and audit recorded runs.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
. .venv/bin/activate
python -m pip check
python -m pytest -q
python -m compileall -q src scripts
python -m retail_eval.run doctor
python scripts/audit_runs.py
