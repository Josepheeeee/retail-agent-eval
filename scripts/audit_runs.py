"""Audit run manifests without calling any model."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    runs = []
    for folder in sorted((ROOT / "runs").iterdir()):
        path = folder / "manifest.json"
        if not folder.is_dir() or not path.exists():
            continue
        manifest = json.loads(path.read_text(encoding="utf-8"))
        runs.append({"run": folder.name, "kind": manifest.get("kind"), "status": manifest.get("status"),
                     "split": manifest.get("split"), "group": manifest.get("group"),
                     "benchmark_complete": manifest.get("benchmark_complete"),
                     "expected": manifest.get("expected_records"),
                     "actual": len((folder / "traces.jsonl").read_text(encoding="utf-8").splitlines())
                     if (folder / "traces.jsonl").exists() else None})
    counts = Counter((row["kind"], row["status"]) for row in runs)
    problems = [row for row in runs if row["status"] == "complete" and row["benchmark_complete"] is False
                and row["kind"] in {"collect", "optimize"}]
    print(json.dumps({"runs": len(runs), "counts": {f"{k[0]}:{k[1]}": v for k, v in counts.items()},
                      "incomplete_but_kept": problems[:20]}, ensure_ascii=False, indent=2))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
