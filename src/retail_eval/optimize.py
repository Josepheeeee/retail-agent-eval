"""GEPA's public adapter with equal-information feedback and a hard call ledger."""
from __future__ import annotations

import json
from pathlib import Path

from .schema import Grade, Trace, digest, write_json


class BudgetExhausted(RuntimeError):
    pass


def feedback(trace: Trace, grade: Grade, mode: str, limit=12000) -> dict:
    if trace.split == "test" or trace.source != "live":
        raise ValueError("reflection requires live train/dev traces, never test/demo")
    if mode not in {"natural", "layered", "no_layer", "no_evidence"}:
        raise ValueError("unsupported feedback mode")
    editable = grade.cause in {"agent", "prompt"}
    facts = [{"layer": k, "status": v.status, "rule": v.rule, "reason": v.reason,
              "evidence": v.evidence} for k, v in grade.layers.items() if v.status != "blocked"]
    # A2 receives the same rules, reasons, locations and trace as A3 in prose.
    # The ablation removes the explicit link, not the underlying observed trace.
    variants = {}
    for style in ("natural", "layered", "no_layer", "no_evidence"):
        rows = [{k: v for k, v in row.items() if not (style in {"natural", "no_layer"} and k == "layer")
                 and not (style == "no_evidence" and k == "evidence")} for row in facts]
        common = {"overall": grade.overall, "cause": grade.cause, "editable": editable,
                  "prompt_location": grade.suggested_location if editable else "",
                  "recommendation": grade.recommendation if editable else "Defer: investigate data/rubric/unknown cause; do not repair the agent for this diagnosis."}
        if style == "natural":
            common["feedback"] = "\n".join(f"{r['status']}: {r['rule']} Reason: {r['reason']} Evidence events: {', '.join(r['evidence'])}." for r in rows)
        else:
            common["feedback"] = rows
        variants[style] = common
    # Reserve the same space for the common trace in all arms. Never silently
    # truncate feedback facts; overlong diagnoses are infrastructure failures.
    overhead = max(len(json.dumps(v, ensure_ascii=False)) for v in variants.values()) + 250
    if overhead >= limit:
        raise ValueError("diagnosis exceeds feedback budget")
    visible = json.dumps(trace.visible(), ensure_ascii=False)
    room = limit - overhead
    excerpt = visible[:room]
    return {"Inputs": {"trajectory": excerpt, "truncated": len(visible) > room},
            "Generated Outputs": "See assistant events in trajectory", **variants[mode]}


class RetailAdapter:
    propose_new_texts = None  # Use normal GEPA's reflection proposer.

    def __init__(self, evaluate_one, mode: str, output: Path, budget: int, feedback_limit=12000):
        self.evaluate_one, self.mode, self.output = evaluate_one, mode, output
        self.budget, self.feedback_limit, self.calls = budget, feedback_limit, 0
        self.ledger = []

    def evaluate(self, batch, candidate, capture_traces=False):
        from gepa import EvaluationBatch
        if set(candidate) != {"agent_prompt"}:
            raise ValueError("only agent_prompt may be optimized")
        if self.calls + len(batch) > self.budget:
            raise BudgetExhausted("stop before an evaluation batch would exceed the registered budget")
        if any(item["split"] not in {"train", "dev"} for item in batch):
            raise ValueError("held-out data cannot enter GEPA")
        scores, outputs, trajectories = [], [], []
        for item in batch:
            self.calls += 1
            trace, grade = self.evaluate_one(item, candidate["agent_prompt"], self.calls)
            record = {"call": self.calls, "candidate_sha256": digest(candidate), "task_id": trace.task_id,
                      "split": trace.split, "score": trace.reference.get("official_reward"),
                      "trace_id": trace.trace_id, "status": trace.status, "judge_status": grade.overall}
            self.ledger.append(record)
            write_json(self.output / "metric_ledger.json", self.ledger)
            write_json(self.output / "candidates" / (digest(candidate) + ".json"), candidate)
            if trace.status != "complete" or record["score"] is None or grade.overall in {"error", "parse_error"}:
                raise RuntimeError("evaluation infrastructure error; preserved artifacts, optimization aborted")
            scores.append(float(record["score"]))
            outputs.append({"trace_id": trace.trace_id, "official_reward": record["score"]})
            trajectories.append((trace, grade))
        return EvaluationBatch(outputs=outputs, scores=scores, trajectories=trajectories if capture_traces else None,
                               num_metric_calls=len(batch))

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        if components_to_update != ["agent_prompt"] or eval_batch.trajectories is None:
            raise ValueError("reflection contract mismatch")
        return {"agent_prompt": [feedback(t, g, self.mode, self.feedback_limit) for t, g in eval_batch.trajectories]}


def optimize_prompt(adapter: RetailAdapter, prompt: str, train: list[dict], dev: list[dict],
                    endpoint, config: dict, feedback_prompt: str, seed: int):
    import gepa

    def reflection_lm(messages):
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        answer, usage = endpoint.complete([{"role": "system", "content": feedback_prompt}, *messages], config)
        index = len(list((adapter.output / "reflections").glob("*.json"))) if (adapter.output / "reflections").exists() else 0
        write_json(adapter.output / "reflections" / f"{index:04d}.json", {"messages": messages, "answer": answer, "usage": usage})
        return answer

    result = None
    stopped = "gepa_completed"
    try:
        result = gepa.optimize(seed_candidate={"agent_prompt": prompt}, trainset=train, valset=dev, adapter=adapter,
                               reflection_lm=reflection_lm, max_metric_calls=adapter.budget,
                               reflection_minibatch_size=3, seed=seed, cache_evaluation=False,
                               run_dir=str(adapter.output / "gepa"), raise_on_exception=True, display_progress_bar=False)
    except BudgetExhausted:
        stopped = "hard_budget_boundary"
    if result is not None:
        write_json(adapter.output / "gepa_result.json", result.to_dict())
    # Select only candidates with a complete fixed dev-set evaluation. Earliest
    # candidate wins ties. Partial last batches cannot influence selection.
    dev_ids = {d["task_id"] for d in dev}
    observations = {}
    for row in adapter.ledger:
        if row["split"] == "dev" and row["status"] == "complete" and row["score"] is not None:
            observations.setdefault(row["candidate_sha256"], {}).setdefault(row["task_id"], row["score"])
    eligible = [(key, sum(v.values()) / len(v)) for key, v in observations.items() if set(v) == dev_ids]
    if not eligible:
        raise RuntimeError("no fully evaluated development candidate; no candidate frozen")
    key, score = max(eligible, key=lambda kv: kv[1])
    selected = json.loads((adapter.output / "candidates" / (key + ".json")).read_text(encoding="utf-8"))
    (adapter.output / "selected_prompt.md").write_text(selected["agent_prompt"], encoding="utf-8")
    summary = {"stop": stopped, "metric_calls": adapter.calls, "budget": adapter.budget,
               "candidate_sha256": key, "development_score": score, "selection": "complete development mean; earliest tie"}
    write_json(adapter.output / "optimization.json", summary)
    plot_optimization(adapter.ledger, adapter.output, dev_ids)
    return summary


def plot_optimization(ledger, output: Path, dev_ids: set[str]):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    seen, points = {}, []
    for r in ledger:
        if r["split"] == "dev" and r["score"] is not None:
            scores = seen.setdefault(r["candidate_sha256"], {})
            scores.setdefault(r["task_id"], r["score"])
            if set(scores) == dev_ids:
                points.append((r["call"], sum(scores.values()) / len(scores)))
    fig, ax = plt.subplots(figsize=(7, 4), constrained_layout=True)
    if points:
        ax.plot(*zip(*points), marker="o")
    ax.set(xlabel="Task scoring calls (including development)", ylabel="Fixed development official reward", title="Development curve — not held-out test")
    fig.savefig(output / "optimization.png", dpi=160); plt.close(fig)
