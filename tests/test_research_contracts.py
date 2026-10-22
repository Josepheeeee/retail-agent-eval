"""Research contracts added for the dual-project delivery.

These tests exercise evidence localisation, complete human-label retention,
training export caps and report aggregation. They do not call a model.
"""
from __future__ import annotations

import json

import pytest
import yaml

from retail_eval.data import (blind_packets, export_sft, judge_sft_config, unblind_annotations,
                              verbosity_variant)
from retail_eval.judge import fixture_grade
from retail_eval.report import (calibration_metrics, dimension_metrics, localization_metrics,
                                make_report, verbosity_consistency)
from retail_eval.run import ROOT
from retail_eval.schema import Trace, read_jsonl, validate_grade


@pytest.fixture
def labelled():
    traces = [Trace.model_validate(r) for r in read_jsonl(ROOT / "data/fixtures/traces.jsonl")]
    labels = json.loads((ROOT / "data/fixtures/labels.json").read_text(encoding="utf-8"))
    return {t.trace_id: t for t in traces}, {t.trace_id: fixture_grade(t, labels) for t in traces}


def _live(trace: Trace, split="train", task_id="1"):
    return trace.model_copy(update={"source": "live", "split": split, "task_id": task_id,
                                    "reference": {"official_reward": 1}})


def _first(traces, grades, predicate=lambda g: True):
    return next(t for tid, t in traces.items() if tid in grades and predicate(grades[tid]))


def test_error_type_and_localization_contract(labelled):
    traces, grades = labelled
    fail = next(g for g in grades.values() if g.error_type == "unconfirmed_write")
    trace = traces[fail.trace_id]
    assert validate_grade(fail, trace).earliest_error_event == "e3"

    bad = fail.model_copy(deep=True, update={"error_type": "privacy_leak"})
    with pytest.raises(ValueError, match="contradicts"):
        validate_grade(bad, trace)

    bad = fail.model_copy(deep=True, update={"earliest_error_event": "e1"})
    with pytest.raises(ValueError, match="supporting evidence"):
        validate_grade(bad, trace)

    bad = fail.model_copy(deep=True, update={"cause": "unknown", "attribution_uncertainty": "low"})
    with pytest.raises(ValueError, match="unknown cause"):
        validate_grade(bad, trace)

    unclassified = fail.model_copy(deep=True, update={"error_type": "unclassified",
                                                      "attribution_uncertainty": "low"})
    with pytest.raises(ValueError, match="unclassified failure"):
        validate_grade(unclassified, trace)


def test_human_gold_keeps_layers_location_evidence_and_review(labelled, tmp_path):
    traces, grades = labelled
    trace = _first(traces, grades)
    grade = grades[trace.trace_id]
    packets = tmp_path / "packets.jsonl"
    blind_packets([trace], packets)
    rows = read_jsonl(packets)
    rows[0]["annotation"] = grade.model_dump(exclude={"trace_id", "judge_version"})
    rows[0]["review"] = {"reviewer_id": "reviewer-a", "round": 1, "status": "first",
                         "minutes": 12, "notes": "checked evidence"}
    packets.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    output = tmp_path / "gold.jsonl"
    assert unblind_annotations(packets, packets.with_suffix(".mapping.json"), output) == 1
    stored = read_jsonl(output)[0]
    assert stored["grade"]["layers"] and stored["grade"]["error_type"]
    assert stored["review"]["reviewer_id"] == "reviewer-a"
    assert stored["review"]["annotation_sha256"]

    report = make_report([trace], [grade], tmp_path / "report", gold={trace.trace_id: grade},
                         gold_records=[stored])
    assert report["label_sources"] == {"human": 1}
    assert report["human_gold_records"][0]["review"]["round"] == 1
    assert report["gold_dimensions"]["n"] == 1
    assert "Dimension agreement" in (tmp_path / "report/report.md").read_text(encoding="utf-8")


def test_localization_metrics_split_verdict_type_and_event(labelled):
    traces, grades = labelled
    gold = next(g for g in grades.values() if g.overall == "fail" and g.earliest_error_event)
    trace = traces[gold.trace_id]
    second_trace = trace.model_copy(update={"trace_id": "second"})
    second_gold = gold.model_copy(deep=True, update={"trace_id": "second"})
    same = gold.model_copy(deep=True)
    metrics = localization_metrics([same, second_gold], {gold.trace_id: gold, "second": second_gold},
                                   [trace, second_trace])
    assert metrics["gold_fail"] == 2
    assert metrics["exact_event"] == 2
    assert metrics["error_type_accuracy"] == 1


def test_calibration_and_dimension_metrics_use_decisions_only(labelled):
    _, grades = labelled
    gold = {k: v for k, v in grades.items()}
    calibration = calibration_metrics(list(grades.values()), gold)
    assert calibration["n"] >= 1 and 0 <= calibration["ece"] <= 1
    dimensions = dimension_metrics(list(grades.values()), gold)
    assert set(dimensions["layers"]) == {"CTX", "OOSR", "OOC", "TCC", "CNT", "RED"}
    assert dimensions["layers"]["TCC"]["accuracy"] == 1


def test_judge_sft_export_cap_and_three_seed_configs(labelled, tmp_path):
    traces, grades = labelled
    candidates = [t for t in traces.values() if grades[t.trace_id].overall not in {"parse_error", "error"}]
    first, second = candidates[:2]
    live_first, live_second = _live(first), _live(second, task_id="2")
    rubric = yaml.safe_load((ROOT / "rubrics/retail.yaml").read_text(encoding="utf-8"))
    manifest = {"splits": {"train": ["1", "2"], "dev": [], "test": []}}
    labels = [{"trace_id": trace.trace_id, "label_source": "teacher",
               "grade": grades[trace.trace_id].model_dump()} for trace in (first, second)]
    target = tmp_path / "sft.jsonl"
    assert export_sft([live_first], labels[:1], target, "judge", manifest, rubric, max_trajectories=1) == 1
    exported = json.loads(target.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    assert exported["rows"] == 1 and exported["label_source_counts"]["teacher"] == 1
    with pytest.raises(ValueError, match="exceed"):
        export_sft([live_first, live_second], labels, tmp_path / "too-many.jsonl", "judge", manifest, rubric,
                   max_trajectories=1)

    configs = tmp_path / "configs"
    for seed in (42, 43, 44):
        judge_sft_config(seed, configs, target)
        config = json.loads((configs / f"seed{seed}.yaml").read_text(encoding="utf-8"))
        assert config["lora_rank"] == 32 and config["learning_rate"] == 1e-4
        assert config["per_device_train_batch_size"] * config["gradient_accumulation_steps"] == 4
        assert config["seed"] == seed
    with pytest.raises(ValueError, match="42/43/44"):
        judge_sft_config(45, configs, target)


def test_verbosity_variant_preserves_evidence_and_measures_drift(labelled):
    traces, grades = labelled
    trace = _first(traces, grades, lambda g: g.overall in {"pass", "fail"})
    variant = verbosity_variant(trace)
    assert variant.trace_id.endswith("-verbose")
    assert variant.metadata["verbosity_of"] == trace.trace_id
    assert {e.id for e in variant.events} == {e.id for e in trace.events}
    assert len(variant.events[-1].content) > len(trace.events[-1].content) if trace.events[-1].role == "assistant" else True
    original = grades[trace.trace_id]
    same = original.model_copy(deep=True)
    assert verbosity_consistency([original], [same])["overall_agreement"] == 1
    drifted = same.model_copy(deep=True, update={"overall": "abstain" if same.overall != "abstain" else "pass"})
    assert verbosity_consistency([original], [drifted])["overall_agreement"] == 0


def test_remote_budget_must_be_registered():
    from retail_eval.run import assert_api_budget
    remote = {"agent": {"base_url": "https://api.example.com/v1"}}
    prices = {"price_input_per_million": 1.0, "price_output_per_million": 2.0}
    with pytest.raises(ValueError, match="budget"):
        assert_api_budget({"budget": {"max_task_runs": 0, **prices}}, 5, remote)
    assert_api_budget({"budget": {"max_task_runs": 10, **prices}}, 5, remote)
    with pytest.raises(ValueError, match="prices"):
        assert_api_budget({"budget": {"max_task_runs": 10}}, 5, remote)
    with pytest.raises(ValueError, match="exceeded"):
        assert_api_budget({"budget": {"max_task_runs": 4, **prices}}, 5, remote)
    local = {"agent": {"base_url": "http://127.0.0.1:8000/v1"}}
    assert_api_budget({"budget": {"max_task_runs": 0}}, 5, local)


def test_teacher_labels_are_summarised_not_accuracy(labelled, tmp_path):
    traces, grades = labelled
    trace = _first(traces, grades, lambda g: g.overall not in {"parse_error", "error"})
    grade = grades[trace.trace_id]
    teacher = {"trace_id": trace.trace_id, "label_source": "teacher", "grade": grade.model_dump()}
    report = make_report([trace], [grade], tmp_path / "r", teacher_labels=[teacher])
    assert report["gold_metrics"] is None
    assert report["teacher_labels_summary"]["n"] == 1
    assert "never substitute for human gold" in (tmp_path / "r/report.md").read_text(encoding="utf-8")
