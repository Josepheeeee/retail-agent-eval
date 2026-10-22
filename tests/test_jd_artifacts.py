"""The public JD archive must stay internally consistent with its analysis."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_jd_manifest_covers_thirty_companies_and_seventy_jds():
    sources = json.loads((ROOT / "data/manifests/jd_sources.json").read_text(encoding="utf-8"))
    review = json.loads((ROOT / "data/manifests/jd_review.json").read_text(encoding="utf-8"))
    assert sources["scope"]["companies_checked"] == 30
    assert sources["scope"]["official_complete_jds_selected"] == 70
    assert len(sources["companies"]) == 30
    assert len(review["records"]) == 70
    assert len({row["jd_id"] for row in review["records"]}) == 70
    assert len({row["body_sha256"] for row in review["records"]}) == 70
    assert sum(row["category"] == "core" for row in review["records"]) == 51
    assert sum(row["category"] == "adjacent" for row in review["records"]) == 18
    assert sum(row["category"] == "unverified" for row in review["records"]) == 1
    assert len(sources["dedup"]["excluded_records"]) == 4
    assert len(sources["missing_or_excluded_companies"]) == 11
    assert all(row["source_url"].startswith("https://") for row in review["records"])
    assert all(row["evidence"] for row in review["records"])


def test_jd_raw_hash_and_analysis_index_match_manifest():
    sources = json.loads((ROOT / "data/manifests/jd_sources.json").read_text(encoding="utf-8"))
    raw = (ROOT / "docs/JD_RAW.md").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert hashlib.sha256(raw.encode("utf-8")).hexdigest() == sources["provenance"]["raw_sha256"]
    analysis = (ROOT / "docs/JD_ANALYSIS.md").read_text(encoding="utf-8")
    missing = [f"JD-{index:02d}" for index in range(1, 71) if f"JD-{index:02d}" not in analysis]
    assert not missing
    assert "排除" in analysis and "剩余缺口" in analysis


def test_capability_stats_prioritise_intern_and_campus():
    stats = json.loads((ROOT / "data/manifests/jd_capability_stats.json").read_text(encoding="utf-8"))
    assert stats["level_counts"] == {"social": 28, "intern": 28, "campus": 14}
    assert stats["category_counts"] == {"core": 51, "adjacent": 18, "unverified": 1}
    assert stats["capability_stats"]["benchmark"]["intern_campus"] >= 30
    assert sum(values["all"] for values in stats["capability_stats"].values()) > 70


def test_jd_fit_matches_review_and_declares_its_limits():
    fit = json.loads((ROOT / "data/manifests/jd_fit.json").read_text(encoding="utf-8"))
    review = json.loads((ROOT / "data/manifests/jd_review.json").read_text(encoding="utf-8"))
    assert len(fit["records"]) == 70
    assert {row["jd_id"] for row in fit["records"]} == {row["jd_id"] for row in review["records"]}
    capabilities = {cap for row in review["records"] for cap in row["capabilities"]}
    assert set(fit["coverage_levels"]) == capabilities
    recomputed = sum(row["score"] for row in fit["records"]) / 70
    assert abs(recomputed - fit["summary"]["mean_all"]) < 1e-9
    assert fit["external_dependency"]["code"]["vendored_lines"] == 0
    assert abs(sum(row["share"] for row in fit["external_dependency"]["estimates"]) - 100) < 1e-9
    assert "design coverage" in fit["scope"]["note"].lower()
