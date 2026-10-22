"""Accountable summaries, fixed-coverage judge metrics and paired task bootstrap."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .schema import LAYERS, Grade, Trace, digest, write_json


def _as_grade(value):
    if isinstance(value, Grade):
        return value
    if isinstance(value, dict):
        if "grade" in value:
            return Grade.model_validate(value["grade"])
        if "overall" in value:
            return Grade.model_validate({**value, "judge_version": value.get("judge_version", "human-v1")})
    return None


def _overall_map(gold: dict | None) -> dict[str, str]:
    """Accept overall strings, Grade objects or label records for compatibility."""
    result = {}
    for trace_id, value in (gold or {}).items():
        grade = _as_grade(value)
        result[trace_id] = grade.overall if grade is not None else str(value)
    return result


def total_tokens(usage: dict | None):
    usage = usage or {}
    if usage.get("total_tokens") is not None:
        return usage["total_tokens"]
    a = usage.get("input_tokens", usage.get("prompt_tokens"))
    b = usage.get("output_tokens", usage.get("completion_tokens"))
    return a + b if a is not None and b is not None else None


def expense_summary(traces: list[Trace], grades: list[Grade]):
    observed = {role: [] for role in ("agent", "user", "official_judge", "layered_judge")}
    for t in traces:
        for m in t.usage.get("messages", []):
            role = "agent" if m["role"] == "assistant" else "user"
            observed[role].append(total_tokens(m["usage"]))
        for m in t.usage.get("official_judge", []):
            observed["official_judge"].append(total_tokens(m["usage"]))
    observed["layered_judge"] = [total_tokens(g.usage) for g in grades]
    costs = {}
    for role, values in observed.items():
        known = [v for v in values if v is not None]
        costs[role] = {"known_token_total": sum(known) if known else None,
                       "calls_with_token_usage": len(known), "usage_records": len(values)}
    calls, repeated = 0, 0
    for t in traces:
        seen = set()
        for e in t.events:
            for call in e.tool_calls if e.role == "assistant" else []:
                calls += 1
                if call.get("name") in t.metadata.get("mutating_tools", []):
                    key = digest({"name": call["name"], "arguments": call.get("arguments", {})})
                    repeated += key in seen
                    seen.add(key)
    costs["business_tool_calls"] = calls
    costs["repeated_identical_write_calls_proxy"] = repeated
    costs["note"] = "Missing provider usage is unknown, not zero. Repeated writes are a diagnostic proxy, not proven unwanted side effects."
    return costs


def judge_metrics(grades: list[Grade], gold: dict, coverage=1.0):
    gold = _overall_map(gold)
    if not 0 < coverage <= 1:
        raise ValueError("coverage must be in (0,1]")
    eligible = [g for g in grades if gold.get(g.trace_id) in {"pass", "fail"}]
    decided = sorted([g for g in eligible if g.overall in {"pass", "fail"}], key=lambda g: (-g.confidence, g.trace_id))
    target = int(len(eligible) * coverage)
    chosen = decided[:target]
    tp = sum(g.overall == "pass" and gold[g.trace_id] == "pass" for g in chosen)
    tn = sum(g.overall == "fail" and gold[g.trace_id] == "fail" for g in chosen)
    fp = sum(g.overall == "pass" and gold[g.trace_id] == "fail" for g in chosen)
    fn = sum(g.overall == "fail" and gold[g.trace_id] == "pass" for g in chosen)
    ratio = lambda a, b: a / b if b else None
    p, r = ratio(tp, tp + fp), ratio(tp, tp + fn)
    all_failures = sum(gold[g.trace_id] == "fail" for g in eligible)
    return {"eligible": len(eligible), "decided": len(chosen), "target_coverage": coverage,
            "coverage": ratio(len(chosen), len(eligible)), "coverage_target_met": len(chosen) == target and target > 0,
            "accuracy_decided": ratio(tp + tn, len(chosen)), "precision": p, "recall": r,
            "f1": 2 * p * r / (p + r) if p is not None and r is not None and p + r else 0 if chosen else None,
            "false_pass_rate_decided_failures": ratio(fp, fp + tn), "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
            "false_pass_rate_all_gold_failures": ratio(fp, all_failures),
            "failure_coverage": ratio(fp + tn, all_failures),
            "abstain": sum(g.overall == "abstain" for g in eligible),
            "parse_error": sum(g.overall == "parse_error" for g in eligible),
            "error": sum(g.overall == "error" for g in eligible),
            "gold_abstain_n": sum(gold.get(g.trace_id) == "abstain" for g in grades),
            "abstain_recall": ratio(sum(gold.get(g.trace_id) == "abstain" and g.overall == "abstain" for g in grades),
                                    sum(gold.get(g.trace_id) == "abstain" for g in grades))}


def calibration_metrics(grades: list[Grade], gold: dict, bins=10):
    """Expected calibration error and Brier score on decisions, never on abstains."""
    gold_map = _overall_map(gold)
    pairs = [(g.confidence, int(g.overall == gold_map.get(g.trace_id))) for g in grades
             if g.overall in {"pass", "fail"} and gold_map.get(g.trace_id) in {"pass", "fail"}]
    if not pairs:
        return {"n": 0, "ece": None, "brier": None, "bins": []}
    rows = []
    ece = 0.0
    for index in range(bins):
        low, high = index / bins, (index + 1) / bins
        bucket = [p for p in pairs if low <= p[0] < high or (index == bins - 1 and p[0] == 1)]
        if not bucket:
            continue
        confidence = sum(p[0] for p in bucket) / len(bucket)
        accuracy = sum(p[1] for p in bucket) / len(bucket)
        ece += len(bucket) / len(pairs) * abs(accuracy - confidence)
        rows.append({"low": low, "high": high, "n": len(bucket),
                     "mean_confidence": confidence, "accuracy": accuracy})
    brier = sum((p[0] - p[1]) ** 2 for p in pairs) / len(pairs)
    return {"n": len(pairs), "ece": ece, "brier": brier, "bins": rows}


def dimension_metrics(grades: list[Grade], gold: dict):
    """Per-layer agreement and failure detection, using only human-labelled layers."""
    gold_map = {k: _as_grade(v) for k, v in (gold or {}).items()}
    gold_map = {k: v for k, v in gold_map.items() if v is not None}
    if not gold_map:
        return {"layers": {}, "n": 0}
    by_id = {g.trace_id: g for g in grades}
    result = {}
    for layer in LAYERS:
        # (human truth, automatic prediction)
        pairs = [(g.layers[layer], by_id[t].layers[layer]) for t, g in gold_map.items()
                 if t in by_id and layer in g.layers and layer in by_id[t].layers]
        if not pairs:
            result[layer] = {"n": 0}
            continue
        accuracy = sum(truth.status == pred.status for truth, pred in pairs) / len(pairs)
        gold_fail = [(truth, pred) for truth, pred in pairs if truth.status == "fail"]
        pred_fail = [(truth, pred) for truth, pred in pairs if pred.status == "fail"]
        tp = sum(truth.status == "fail" and pred.status == "fail" for truth, pred in pairs)
        precision = tp / len(pred_fail) if pred_fail else None
        recall = tp / len(gold_fail) if gold_fail else None
        result[layer] = {
            "n": len(pairs), "accuracy": accuracy,
            "gold_fail": len(gold_fail), "pred_fail": len(pred_fail), "tp": tp,
            "precision": precision, "recall": recall,
            "f1": (2 * precision * recall / (precision + recall))
            if precision is not None and recall is not None and precision + recall else None,
            "status_agreement": dict(Counter(f"{truth.status}->{pred.status}" for truth, pred in pairs)),
        }
    return {"n": len(gold_map), "layers": result}


def _event_turn(traces: list[Trace]):
    lookup = {}
    for trace in traces:
        lookup[trace.trace_id] = {e.id: e.turn for e in trace.events}
    return lookup


def localization_metrics(grades: list[Grade], gold: dict, traces: list[Trace]):
    """Evaluate overall verdict, error type, error layer and first-error localization separately."""
    gold_map = {k: _as_grade(v) for k, v in (gold or {}).items()}
    gold_map = {k: v for k, v in gold_map.items() if v is not None}
    by_id = {g.trace_id: g for g in grades}
    turns = _event_turn(traces)
    rows = []
    for trace_id, truth in gold_map.items():
        pred = by_id.get(trace_id)
        if pred is None:
            continue
        rows.append((pred, truth, turns.get(trace_id, {})))
    gold_fails = [(p, t) for p, t, _ in rows if t.overall == "fail"]
    localized = [(p, t, turn) for p, t, turn in rows if t.overall == "fail" and t.earliest_error_event]
    exact = same_turn = within_one = layer_match = 0
    for pred, truth, turn in localized:
        if not pred.earliest_error_event:
            continue
        exact += pred.earliest_error_event == truth.earliest_error_event
        same_turn += turn.get(pred.earliest_error_event) == turn.get(truth.earliest_error_event)
        a, b = turn.get(pred.earliest_error_event), turn.get(truth.earliest_error_event)
        within_one += a is not None and b is not None and abs(a - b) <= 1

        def layer_of(grade, event_id):
            return next((k for k, v in grade.layers.items() if event_id in v.evidence), None)

        pred_layer, gold_layer = layer_of(pred, pred.earliest_error_event), layer_of(truth, truth.earliest_error_event)
        layer_match += pred_layer is not None and pred_layer == gold_layer
    typed = [(p, t) for p, t in gold_fails if t.error_type not in {"unclassified", "none"}]
    return {
        "gold_fail": len(gold_fails),
        "localized_gold": len(localized),
        "predicted_localized": sum(bool(p.earliest_error_event) for p, _ in gold_fails),
        "exact_event": exact if localized else None,
        "same_turn": same_turn if localized else None,
        "within_one_turn": within_one if localized else None,
        "error_layer_match": layer_match if localized else None,
        "error_type_accuracy": (sum(p.error_type == t.error_type for p, t in typed) / len(typed)) if typed else None,
        "error_type_n": len(typed),
        "abstain_on_gold_fail": sum(p.overall == "abstain" for p, _ in gold_fails),
    }


def evidence_quality(grades: list[Grade]):
    failed = [layer for g in grades for layer in g.layers.values() if layer.status == "fail"]
    return {
        "fail_layers": len(failed),
        "with_evidence": sum(bool(layer.evidence) for layer in failed),
        "direct_support": sum(layer.support == "direct" for layer in failed),
        "inferred_support": sum(layer.support == "inferred" for layer in failed),
        "without_support": sum(layer.support == "none" for layer in failed),
        "direct_support_rate": (sum(layer.support == "direct" for layer in failed) / len(failed)) if failed else None,
    }


def paired_bootstrap(a: list[Trace], b: list[Trace], samples=10000, seed=2026, trials=3):
    """Resample optimization seeds and paired tasks; trials stay within task cells."""
    if samples < 1:
        raise ValueError("bootstrap samples must be positive")

    def cells(rows):
        result = defaultdict(dict)
        for t in rows:
            reward = t.reference.get("official_reward")
            if t.status != "complete" or reward is None:
                raise ValueError("incomplete outcome cannot enter paired comparison")
            key = (t.optimization_seed, t.task_id)
            if t.trial in result[key]:
                raise ValueError("duplicate task/seed/trial")
            result[key][t.trial] = float(reward)
        if not result or any(set(v) != set(range(trials)) for v in result.values()):
            raise ValueError(f"each cell must contain exactly trials 0..{trials-1}")
        return {k: float(np.mean(list(v.values()))) for k, v in result.items()}

    ca, cb = cells(a), cells(b)
    if ca.keys() != cb.keys():
        raise ValueError("unmatched task/optimization-seed cells")
    seeds = sorted({k[0] for k in ca}, key=str)
    tasks = sorted({k[1] for k in ca})
    if len(ca) != len(seeds) * len(tasks):
        raise ValueError("comparison must be rectangular across seeds and tasks")
    delta = np.array([[cb[(s, t)] - ca[(s, t)] for t in tasks] for s in seeds])
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(samples):
        si = rng.integers(0, len(seeds), size=len(seeds))
        ti = rng.integers(0, len(tasks), size=len(tasks))
        draws.append(float(delta[np.ix_(si, ti)].mean()))
    return {"estimand": "B minus A official reward; equal task/seed weight", "difference": float(delta.mean()),
            "ci95": np.quantile(draws, [.025, .975]).tolist(), "tasks": len(tasks), "trials_per_cell": trials,
            "optimization_seeds": seeds, "per_seed_difference": {str(s): float(delta[i].mean()) for i, s in enumerate(seeds)},
            "bootstrap_samples": samples, "bootstrap_seed": seed,
            "warning": "one optimization seed cannot estimate optimizer variability" if len(seeds) == 1 else None}


def make_report(traces: list[Trace], grades: list[Grade], output: Path, gold=None, expected_trials=3,
                gold_records=None, teacher_labels=None):
    output.mkdir(parents=True, exist_ok=True)
    if len({t.trace_id for t in traces}) != len(traces) or len({g.trace_id for g in grades}) != len(grades):
        raise ValueError("duplicate trace/grade identity")
    if {g.trace_id for g in grades} != {t.trace_id for t in traces}:
        raise ValueError("every collected trace must have a grade, including errors")
    if len({t.source for t in traces}) > 1:
        raise ValueError("demo and live results cannot be pooled")
    index = {g.trace_id: g for g in grades}
    grouped = defaultdict(list)
    for t in traces:
        grouped[t.agent_version].append(t)
    rows = []
    for group, ts in sorted(grouped.items()):
        outcomes = [t.reference["official_reward"] for t in ts if t.status == "complete" and t.reference.get("official_reward") is not None]
        gs = [index[t.trace_id] for t in ts]
        bytask = defaultdict(list)
        for t in ts:
            bytask[(t.optimization_seed, t.task_id)].append(t)
        complete_cells = [v for v in bytask.values() if len(v) == expected_trials and {x.trial for x in v} == set(range(expected_trials))
                          and all(x.status == "complete" and x.reference.get("official_reward") is not None for x in v)]
        policy_known = [g for g in gs if g.layers.get("TCC") and g.layers["TCC"].status in {"pass", "fail"}]
        rows.append({"version": group, "n": len(ts), "official_outcomes_known": len(outcomes),
                     "observed_official_success": float(np.mean(outcomes)) if outcomes else None,
                     "official_success_complete": float(np.mean(outcomes)) if outcomes and len(outcomes) == len(ts) else None,
                     "pass3": float(np.mean([all(t.reference["official_reward"] == 1 for t in c) for c in complete_cells])) if complete_cells else None,
                     "pass3_cells": len(complete_cells), "pass3_total_cells": len(bytask),
                     "judge_pass": sum(g.overall == "pass" for g in gs), "judge_fail": sum(g.overall == "fail" for g in gs),
                     "abstain": sum(g.overall == "abstain" for g in gs), "parse_error": sum(g.overall == "parse_error" for g in gs),
                     "error": sum(g.overall == "error" for g in gs),
                     "policy_violation_rate_judge_proxy": sum(g.layers["TCC"].status == "fail" for g in policy_known) / len(policy_known) if policy_known else None,
                     "policy_judge_coverage": len(policy_known) / len(gs) if gs else None,
                     "mean_task_seconds": float(np.mean([t.elapsed_seconds for t in ts])) if ts else None,
                     "mean_judge_seconds": float(np.mean([g.elapsed_seconds for g in gs])) if gs else None})
    failures = Counter(k for g in grades for k, v in g.layers.items() if v.status == "fail")
    source = traces[0].source if traces else "empty"
    gold_records = gold_records or []
    if gold_records:
        label_sources = dict(Counter(row.get("label_source", "human") for row in gold_records))
        human_records = [row for row in gold_records if row.get("label_source", "human") == "human"]
        teacher_records = [row for row in gold_records if row.get("label_source") == "teacher"]
    else:
        label_sources = {"human": len(gold)} if gold else {}
        human_records = [{"trace_id": k, "label_source": "human", "grade": _as_grade(v).model_dump()}
                         for k, v in (gold or {}).items() if _as_grade(v) is not None]
        teacher_records = []
    gold_map = {row["trace_id"]: Grade.model_validate(row["grade"]) for row in human_records}
    human_reviews = {row["trace_id"]: row.get("review", {}) for row in human_records}
    payload = {"source": source, "not_a_benchmark": source != "live", "versions": rows,
               "expense": expense_summary(traces, grades),
               "official_components": [{"trace_id": t.trace_id, **t.reference} for t in traces],
               "first_layer_failure_counts": dict(Counter(next((k for k in ("CTX", "OOSR", "OOC", "TCC", "CNT") if g.layers.get(k) and g.layers[k].status == "fail"), "none") for g in grades)),
               "all_failed_layers": dict(failures), "judge_evidence_quality": evidence_quality(grades),
               "error_type_counts": dict(Counter(g.error_type for g in grades)),
               "localized_failures": sum(bool(g.earliest_error_event) for g in grades if g.overall == "fail"),
               "label_sources": label_sources,
               "teacher_labels_summary": {"n": len(teacher_labels or teacher_records),
                                          "used_for": "training signal only; never human-gold accuracy"},
               "gold_metrics": judge_metrics(grades, gold_map) if gold_map else None,
               "gold_dimensions": dimension_metrics(grades, gold_map) if gold_map else None,
               "gold_localization": localization_metrics(grades, gold_map, traces) if gold_map else None,
               "gold_calibration": calibration_metrics(grades, gold_map) if gold_map else None,
               "human_gold_records": [{"trace_id": row["trace_id"], "grade": row["grade"],
                                       "review": row.get("review", {})} for row in human_records]}
    write_json(output / "summary.json", payload)
    with (output / "versions.csv").open("w", encoding="utf-8-sig", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    title = "FIXTURE DEMO — not model benchmark results" if source == "fixture" else "Live retail evaluation"
    lines = [f"# {title}", "", "Environment outcome and Judge verdict are reported separately. Unknown values are N/A.", "",
             "| Version | N | Official known | Observed success | pass³ | Judge pass/fail | Abstain/parse/error |", "|---|---:|---:|---:|---:|---|---|"]
    fmt = lambda v: "N/A" if v is None else f"{v:.3f}"
    for row in rows:
        lines.append(f"| {row['version']} | {row['n']} | {row['official_outcomes_known']} | {fmt(row['observed_official_success'])} | {fmt(row['pass3'])} | {row['judge_pass']}/{row['judge_fail']} | {row['abstain']}/{row['parse_error']}/{row['error']} |")
    lines += ["", "## Label provenance", "",
              "Official environment outcomes, LLM verdicts, human gold and teacher labels are separate objects and are never pooled.",
              "", f"- Sources: `{json.dumps(label_sources, ensure_ascii=False)}`",
              f"- Teacher labels: {payload['teacher_labels_summary']['n']} (training signal only).", "",
              "## Failed layers and error types", "", json.dumps(dict(failures)), "",
              json.dumps(payload["error_type_counts"]), "",
              f"Localized failures: {payload['localized_failures']} / {sum(g.overall == 'fail' for g in grades)}.",
              "", "## Representative failures", ""]
    for grade in [g for g in grades if g.overall != "pass"][:10]:
        location = f"; earliest={grade.earliest_error_event}" if grade.earliest_error_event else "; earliest=unknown"
        lines.append(f"- `{grade.trace_id}`: {grade.overall}; type={grade.error_type}{location}; "
                     f"uncertainty={grade.attribution_uncertainty}; cause={grade.cause}; "
                     f"{grade.recommendation or grade.error or ''}")
    if gold_map:
        gm = payload["gold_metrics"]
        lines += ["", "## Independent human gold", "",
                  f"Overall agreement: {fmt(gm['accuracy_decided'])} on {gm['decided']} decided labels; "
                  f"coverage {fmt(gm['coverage'])}; false-pass rate {fmt(gm['false_pass_rate_decided_failures'])}.",
                  "", "| Trace | Gold | Predicted | Error type | Earliest event | Uncertainty | Review |",
                  "|---|---|---|---|---|---|---|"]
        for row in payload["human_gold_records"]:
            grade = Grade.model_validate(row["grade"])
            pred = index.get(row["trace_id"])
            review = row.get("review") or {}
            review_text = f"{review.get('reviewer_id', 'n/a')} / {review.get('status', 'n/a')} / round {review.get('round', 'n/a')}"
            lines.append(f"| `{row['trace_id']}` | {grade.overall} | {pred.overall if pred else 'n/a'} | "
                         f"{grade.error_type} | {grade.earliest_error_event or 'unknown'} | "
                         f"{grade.attribution_uncertainty} | {review_text} |")
        lines += ["", "### Dimension agreement", "", "| Layer | N | Accuracy | Gold fails | TP | Precision | Recall |", "|---|---:|---:|---:|---:|---:|---:|"]
        for layer, values in payload["gold_dimensions"]["layers"].items():
            lines.append(f"| {layer} | {values.get('n', 0)} | {fmt(values.get('accuracy'))} | "
                         f"{values.get('gold_fail', 'N/A')} | {values.get('tp', 'N/A')} | "
                         f"{fmt(values.get('precision'))} | {fmt(values.get('recall'))} |")
        loc = payload["gold_localization"]
        lines += ["", "### Localization and calibration", "",
                  f"- Exact first-error event: {loc['exact_event']} / {loc['localized_gold']} human-localized failures.",
                  f"- Same turn: {loc['same_turn']}; within one turn: {loc['within_one_turn']}; layer match: {loc['error_layer_match']}.",
                  f"- Error-type accuracy: {fmt(loc['error_type_accuracy'])} on {loc['error_type_n']} typed failures; "
                  f"abstain on gold failure: {loc['abstain_on_gold_fail']}.",
                  f"- ECE: {fmt(payload['gold_calibration']['ece'])}; Brier: {fmt(payload['gold_calibration']['brier'])}.",
                  "", "### Judge evidence quality", "",
                  f"Direct support on failed layers: {fmt(payload['judge_evidence_quality']['direct_support_rate'])} "
                  f"({payload['judge_evidence_quality']['direct_support']} / {payload['judge_evidence_quality']['fail_layers']}).",
                  "", "Annotations retain dimension labels, error location, evidence and review records. "
                  "Only `label_source=human` enters these calculations."]
    elif gold is None:
        lines += ["", "Human-gold accuracy/confusion is not available until independent labels are supplied. "
                  "Teacher labels never substitute for human gold."]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    plot_report(payload, output)
    return payload


def plot_report(payload: dict, output: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    versions = payload["versions"]
    axes[0].bar([r["version"] for r in versions], [r["judge_fail"] for r in versions], color="#356c9b")
    axes[0].set(title="Judge fail count (not success rate)", ylabel="Traces")
    failures = payload["all_failed_layers"]
    axes[1].bar(list(failures), list(failures.values()), color="#c6763b")
    axes[1].set(title="Failure diagnostics", ylabel="Failed checks")
    fig.suptitle("FIXTURE DEMO — no model performance claims" if payload["not_a_benchmark"] else "Live evaluation diagnostics")
    fig.savefig(output / "diagnostics.png", dpi=160)
    plt.close(fig)
    if payload.get("gold_metrics"):
        c = payload["gold_metrics"]["confusion"]
        fig, ax = plt.subplots(figsize=(4, 4), constrained_layout=True)
        vals = np.array([[c["tn"], c["fp"]], [c["fn"], c["tp"]]])
        ax.imshow(vals, cmap="Blues")
        for (y, x), value in np.ndenumerate(vals):
            ax.text(x, y, str(value), ha="center", va="center")
        ax.set(xticks=[0, 1], yticks=[0, 1], xticklabels=["fail", "pass"], yticklabels=["fail", "pass"], xlabel="Predicted", ylabel="Human gold", title="Decided binary examples only")
        fig.savefig(output / "confusion.png", dpi=160); plt.close(fig)


def compare_judges(groups: dict[str, list[Grade]], gold: dict[str, str], output: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    output.mkdir(parents=True, exist_ok=True)
    if len({frozenset(g.trace_id for g in gs) for gs in groups.values()}) != 1:
        raise ValueError("Judge comparison requires identical trajectory IDs")
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), constrained_layout=True)
    rows = []
    for name, grades in groups.items():
        curve = [judge_metrics(grades, gold, c / 20) for c in range(1, 21)]
        valid = [p for p in curve if p["coverage_target_met"]]
        axes[0].plot([p["coverage"] for p in valid], [p["accuracy_decided"] for p in valid], label=name)
        tokens = [total_tokens(g.usage) for g in grades]
        known = [v for v in tokens if v is not None]
        calibration = calibration_metrics(grades, gold)
        rows.append({"judge": name, **judge_metrics(grades, gold),
                     "ece": calibration["ece"], "brier": calibration["brier"],
                     "evidence_quality": evidence_quality(grades),
                     "dimension_accuracy": {k: v.get("accuracy") for k, v in dimension_metrics(grades, gold)["layers"].items()},
                     "mean_seconds": float(np.mean([g.elapsed_seconds for g in grades])),
                     "mean_known_tokens": float(np.mean(known)) if known else None,
                     "usage_known": len(known)})
        write_json(output / (name + ".coverage.json"), curve)
    axes[0].set(xlabel="Coverage", ylabel="Decided accuracy", ylim=(0, 1), title="Independent human gold")
    axes[0].legend()
    axes[1].bar([r["judge"] for r in rows], [r["mean_seconds"] for r in rows])
    axes[1].set(title="Judge wall time", ylabel="Mean seconds / trace")
    known_rows = [r for r in rows if r["mean_known_tokens"] is not None]
    axes[2].bar([r["judge"] for r in known_rows], [r["mean_known_tokens"] for r in known_rows])
    axes[2].set(title="Known token usage (missing != zero)", ylabel="Mean tokens / usage-known call")
    fig.savefig(output / "judge_reliability_cost.png", dpi=160); plt.close(fig)
    write_json(output / "judge_comparison.json", rows)
    with (output / "judge_comparison.csv").open("w", encoding="utf-8-sig", newline="") as f:
        if rows:
            writer = csv.DictWriter(f, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    return rows
