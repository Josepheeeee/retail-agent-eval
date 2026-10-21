"""Accountable summaries, fixed-coverage judge metrics and paired task bootstrap."""
from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from .schema import Grade, Trace, digest, write_json


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


def judge_metrics(grades: list[Grade], gold: dict[str, str], coverage=1.0):
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


def make_report(traces: list[Trace], grades: list[Grade], output: Path, gold=None, expected_trials=3):
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
    payload = {"source": source, "not_a_benchmark": source != "live", "versions": rows,
               "expense": expense_summary(traces, grades),
               "official_components": [{"trace_id": t.trace_id, **t.reference} for t in traces],
               "first_layer_failure_counts": dict(Counter(next((k for k in ("CTX", "OOSR", "OOC", "TCC", "CNT") if g.layers.get(k) and g.layers[k].status == "fail"), "none") for g in grades)),
               "all_failed_layers": dict(failures), "gold_metrics": judge_metrics(grades, gold) if gold is not None else None}
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
    lines += ["", "## Failed layers", "", json.dumps(dict(failures)), "", "## Representative failures", ""]
    for grade in [g for g in grades if g.overall != "pass"][:10]:
        lines.append(f"- `{grade.trace_id}`: {grade.overall}; cause={grade.cause}; {grade.recommendation or grade.error or ''}")
    if gold is None:
        lines += ["", "Human-gold accuracy/confusion is not available until independent labels are supplied."]
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
        rows.append({"judge": name, **judge_metrics(grades, gold),
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
