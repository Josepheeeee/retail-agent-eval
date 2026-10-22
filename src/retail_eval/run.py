"""One CLI for reproducible collection, scoring, optimization and analysis."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml
from dotenv import load_dotenv

from .data import (JUDGE_SFT_SEEDS, assert_membership, blind_packets, clean_trace, export_sft,
                   judge_sft_config, prepare_splits, unblind_annotations, verbosity_variant)
from .judge import ModelEndpoint, fixture_grade, judge_trace
from .report import compare_judges, judge_metrics, make_report, paired_bootstrap, verbosity_consistency
from .schema import Grade, Trace, digest, read_jsonl, validate_grade, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def traces_at(path):
    return [Trace.model_validate(r) for r in read_jsonl(Path(path))]


def human_gold(path, traces):
    """Load complete human labels, not only their overall verdict."""
    index = {t.trace_id: t for t in traces}
    gold = {}
    for row in read_jsonl(path):
        if row["label_source"] != "human":
            raise ValueError("Judge accuracy requires independent human gold")
        if row["trace_id"] not in index or row["trace_id"] in gold:
            raise ValueError("unknown or duplicate human gold trace")
        grade = validate_grade(Grade.model_validate(row["grade"]), index[row["trace_id"]])
        if grade.overall not in {"pass", "fail", "abstain"}:
            raise ValueError("human gold must be pass/fail/abstain")
        gold[grade.trace_id] = grade
    return gold


def config_at(path=None):
    cfg = yaml.safe_load(Path(path or ROOT / "configs/experiment.yaml").read_text(encoding="utf-8"))
    if cfg["concurrency"] != 1:
        raise ValueError("v1 tau registry adapter requires serial execution")
    if cfg["max_metric_calls"] > 150 or cfg["max_metric_calls"] < 20:
        raise ValueError("registered optimization budget must be between 20 and 150")
    # Config snapshots are public experiment metadata, never credentials.
    if any("key" in k.lower() or "secret" in k.lower() for k in cfg):
        raise ValueError("credentials belong in .env, not experiment configuration")
    return cfg


def split_manifest():
    path = ROOT / "data/manifests/splits.json"
    if not path.exists():
        raise ValueError("run prepare-data first")
    return read(path)


def endpoints(roles):
    return {role: ModelEndpoint.from_env(role).public() for role in roles}


def assert_api_budget(cfg, planned_task_runs, public_endpoints):
    """Stop before a paid batch when the run budget is not registered."""
    budget = cfg.get("budget", {})
    limit = int(budget.get("max_task_runs", 0) or 0)
    if limit and planned_task_runs > limit:
        raise ValueError(f"registered budget exceeded: {planned_task_runs} > {limit} task runs")
    remote = [role for role, value in public_endpoints.items()
              if not any(local in value["base_url"] for local in ("127.0.0.1", "localhost", "0.0.0.0"))]
    if remote and not limit:
        raise ValueError("remote endpoint requires configs/experiment.yaml budget.max_task_runs before batch runs")


def new_run(kind, cfg, roles=(), prompt=None):
    path = ROOT / "runs" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + kind + "-" + uuid4().hex[:8])
    path.mkdir(parents=True, exist_ok=False)
    snapshots = path / "snapshots"; snapshots.mkdir()
    files = {"agent.md": ROOT / cfg["agent_prompt"], "judge.md": ROOT / cfg["judge_prompt"],
             "feedback.md": ROOT / cfg["feedback_prompt"], "retail.yaml": ROOT / cfg["rubric"],
             "references.lock.yaml": ROOT / "references.lock.yaml"}
    hashes = {}
    for name, source in files.items():
        content = prompt if name == "agent.md" and prompt is not None else source.read_text(encoding="utf-8")
        (snapshots / name).write_text(content, encoding="utf-8")
        hashes[name] = digest(content)
    write_json(snapshots / "experiment.json", cfg)
    if (ROOT / "data/manifests/splits.json").exists():
        shutil.copyfile(ROOT / "data/manifests/splits.json", snapshots / "splits.json")
        hashes["splits.json"] = digest(read(snapshots / "splits.json"))
    try:
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except subprocess.CalledProcessError:
        head = "uncommitted-bootstrap"
    source_hashes = {str(p.relative_to(ROOT)).replace("\\", "/"): digest(p.read_text(encoding="utf-8"))
                     for p in (ROOT / "src").rglob("*.py")}
    versions = {p: importlib.metadata.version(p) for p in ("pydantic", "deepagents", "langchain-openai", "gepa", "dspy", "tau2")
                if importlib.util.find_spec(p.replace("-", "_")) is not None}
    manifest = {"kind": kind, "status": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
                "git_head": head, "source_hashes": source_hashes, "config": cfg, "hashes": hashes,
                "python": platform.python_version(), "packages": versions, "endpoints": endpoints(roles)}
    write_json(path / "manifest.json", manifest)
    return path, manifest


def finish(path, manifest, **updates):
    manifest.update(updates)
    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(path / "manifest.json", manifest)


def protocol_signature(manifest):
    # Excludes candidate prompt, arm and optimization seed by design.
    cfg = dict(manifest["config"])
    cfg.pop("agent_prompt", None)
    return digest({"config": cfg, "hashes": {k: v for k, v in manifest["hashes"].items() if k != "agent.md"},
                   "endpoints": {k: v for k, v in manifest["endpoints"].items() if k != "reflection"},
                   "source_hashes": manifest["source_hashes"], "packages": manifest["packages"]})


def collect_one(output, reference, task_id, split, prompt, group, trial, seed, cfg, rubric,
                opt_seed=None, call=None):
    from .agent import run_tau_task
    name = f"{group}-s{opt_seed}-t{task_id}-r{trial}" + (f"-c{call}" if call is not None else "")
    def raw_callback(stage, payload):
        destination = output / "raw" / (name + "." + stage + ".json")
        if destination.exists():
            raise ValueError("raw artifacts cannot be overwritten")
        write_json(destination, payload)
    raw_trace, _ = run_tau_task(reference, task_id, split, prompt, group, trial, seed, cfg, opt_seed, raw_callback)
    raw_trace.trace_id = name
    raw_trace.metadata["candidate_sha256"] = digest({"agent_prompt": prompt})
    write_json(output / "raw" / (name + ".trace.json"), raw_trace.model_dump())
    trace = clean_trace(raw_trace)
    grade, raw_grade = judge_trace(trace, rubric, (output / "snapshots/judge.md").read_text(encoding="utf-8"),
                                   ModelEndpoint.from_env("judge"), cfg, cfg["judge_version"])
    write_json(output / "raw" / (name + ".judge.json"), raw_grade)
    write_json(output / "records" / (name + ".json"), {"trace": trace.model_dump(), "grade": grade.model_dump()})
    # Incremental append retains successful records if a later call is interrupted.
    for filename, record in (("traces.jsonl", trace), ("grades.jsonl", grade)):
        with (output / filename).open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")
    print(f"{name}: execution={trace.status}, official={trace.reference.get('official_reward')}, judge={grade.overall}", flush=True)
    return trace, grade


def freeze_run(path: Path):
    manifest = read(path / "manifest.json")
    if manifest["status"] != "complete" or manifest.get("split") != "dev" or not manifest.get("benchmark_complete", False):
        raise ValueError("freeze requires a complete, error-free development run/optimization")
    selected = path / "selected_prompt.md"
    prompt = (selected if selected.exists() else path / "snapshots/agent.md").read_text(encoding="utf-8")
    expected = set(read(path / "snapshots/splits.json")["splits"]["dev"])
    traces = traces_at(path / "traces.jsonl")
    selected_hash = digest({"agent_prompt": prompt})
    dev = [t for t in traces if t.split == "dev" and t.metadata.get("candidate_sha256") == selected_hash]
    if {t.task_id for t in dev} != expected or any(t.status != "complete" or t.reference.get("official_reward") is None for t in dev):
        raise ValueError("selected prompt needs all 20 development tasks with known outcomes")
    payload = {"frozen_utc": datetime.now(timezone.utc).isoformat(), "source_run": str(path.resolve()),
               "prompt": prompt, "prompt_sha256": digest(prompt), "group": manifest["group"],
               "optimization_seed": manifest.get("optimization_seed"), "protocol_signature": protocol_signature(manifest),
               "development_task_ids": sorted(expected), "development_traces": [t.trace_id for t in dev]}
    target = path / "frozen_candidate.json"
    if target.exists():
        raise ValueError("already frozen; keep the existing artifact")
    write_json(target, payload)
    return target


def cli_parser():
    p = argparse.ArgumentParser(description="Retail Agent evaluation: fixtures, tau/DeepAgents, GEPA, Judge and analysis")
    p.add_argument("--config", type=Path)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor"); sub.add_parser("prepare-data"); sub.add_parser("demo")
    q = sub.add_parser("collect")
    q.add_argument("--split", choices=["train", "dev", "test"], required=True)
    q.add_argument("--group", default="A0")
    q.add_argument("--limit", type=int); q.add_argument("--trials", type=int, default=3)
    q.add_argument("--optimization-seed", type=int); q.add_argument("--prompt", type=Path)
    q.add_argument("--frozen", type=Path)
    q = sub.add_parser("optimize"); q.add_argument("--group", choices=["A2", "A3", "A3_no_layer", "A3_no_evidence"], required=True)
    q.add_argument("--seed", type=int, choices=[42, 43, 44], required=True)
    q = sub.add_parser("freeze"); q.add_argument("--run", type=Path, required=True)
    q = sub.add_parser("judge"); q.add_argument("--traces", type=Path, required=True)
    q.add_argument("--role", default="judge"); q.add_argument("--version", required=True)
    q.add_argument("--generic", action="store_true")
    q = sub.add_parser("judge-matrix"); q.add_argument("--traces", type=Path, required=True)
    q.add_argument("--gold", type=Path)
    q = sub.add_parser("judge-robustness"); q.add_argument("--traces", type=Path, required=True)
    q.add_argument("--role", default="judge"); q.add_argument("--version", default="verbosity-v1")
    q = sub.add_parser("report"); q.add_argument("--run", type=Path, required=True)
    q.add_argument("--gold", type=Path); q.add_argument("--coverage", type=float, default=1.0)
    q = sub.add_parser("compare"); q.add_argument("--a", nargs="+", type=Path, required=True)
    q.add_argument("--b", nargs="+", type=Path, required=True)
    q = sub.add_parser("aggregate"); q.add_argument("--runs", nargs="+", type=Path, required=True)
    q = sub.add_parser("pool"); q.add_argument("--runs", nargs="+", type=Path, required=True)
    q.add_argument("--output", type=Path, required=True)
    q = sub.add_parser("annotation-export"); q.add_argument("--traces", type=Path, required=True); q.add_argument("--output", type=Path, required=True)
    q.add_argument("--count", type=int); q.add_argument("--seed", type=int, default=2026)
    q = sub.add_parser("annotation-import"); q.add_argument("--packets", type=Path, required=True)
    q.add_argument("--mapping", type=Path, required=True); q.add_argument("--output", type=Path, required=True)
    q = sub.add_parser("export-sft"); q.add_argument("--traces", type=Path, required=True)
    q.add_argument("--labels", type=Path, required=True); q.add_argument("--output", type=Path, required=True)
    q = sub.add_parser("judge-sft-config"); q.add_argument("--data", type=Path, required=True)
    q.add_argument("--output", type=Path, default=ROOT / "configs/generated")
    q.add_argument("--seed", type=int, choices=list(JUDGE_SFT_SEEDS))
    return p


def main(argv=None):
    args = cli_parser().parse_args(argv)
    load_dotenv(ROOT / ".env", override=False)
    cfg = config_at(args.config)
    rubric = yaml.safe_load((ROOT / cfg["rubric"]).read_text(encoding="utf-8"))
    try:
        execute(args, cfg, rubric)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def execute(args, cfg, rubric):
    cmd = args.command
    reference = ROOT / cfg["reference_path"]
    if cmd == "doctor":
        result = {"python": platform.python_version(), "python_3_12": sys.version_info[:2] == (3, 12), "root": str(ROOT),
                  "reference_available": (reference / "data/tau2/domains/retail/tasks.json").exists(), "roles": {}}
        for role in ("agent", "user", "judge", "reflection", "small_base", "small_sft", "strong"):
            try:
                result["roles"][role] = ModelEndpoint.from_env(role).public()
            except ValueError:
                result["roles"][role] = "not configured"
        print(json.dumps(result, ensure_ascii=False, indent=2)); return
    if cmd == "prepare-data":
        from .agent import load_tau
        load_tau(reference)
        m = prepare_splits(reference, ROOT / "data/manifests/splits.json", cfg["split_salt"], cfg["dev_tasks"])
        print({k: len(v) for k, v in m["splits"].items()}); return
    if cmd == "demo":
        output, manifest = new_run("demo", cfg)
        traces = traces_at(ROOT / "data/fixtures/traces.jsonl")
        labels = read(ROOT / "data/fixtures/labels.json")
        grades = [fixture_grade(t, labels) for t in traces]
        for t in traces:
            write_json(output / "raw" / (t.trace_id + ".json"), t.model_dump())
        traces = [clean_trace(t) for t in traces]
        write_jsonl(output / "traces.jsonl", traces); write_jsonl(output / "grades.jsonl", grades)
        make_report(traces, grades, output / "report")
        finish(output, manifest, status="complete", benchmark_complete=False, source="fixture")
        print(output); return
    if cmd == "freeze":
        print(freeze_run(args.run.resolve())); return
    if cmd in {"collect", "optimize"}:
        m = split_manifest()
        prompt = (ROOT / cfg["agent_prompt"]).read_text(encoding="utf-8")
        roles = ["agent", "user", "judge"] + (["reflection"] if cmd == "optimize" else [])
        public = endpoints(roles)  # Fail before creating an empty run if credentials are missing.
        if cmd == "collect":
            if args.group not in cfg["groups"]:
                raise ValueError("unknown registered group")
            if args.group.startswith(("A2", "A3")) and args.optimization_seed not in cfg["optimization_seeds"]:
                raise ValueError("optimized candidates require their registered optimization seed")
            if args.prompt:
                prompt = args.prompt.read_text(encoding="utf-8")
            frozen = read(args.frozen) if args.frozen else None
            if args.split == "test":
                if not frozen or args.limit is not None or args.trials != 3:
                    raise ValueError("formal test requires a frozen candidate, all 40 tasks and 3 trials")
                if args.prompt or args.group != frozen["group"] or args.optimization_seed != frozen["optimization_seed"]:
                    raise ValueError("test candidate identity mismatch")
                prompt = frozen["prompt"]
                if digest(prompt) != frozen["prompt_sha256"]:
                    raise ValueError("frozen prompt hash mismatch")
            if not 1 <= args.trials <= len(cfg["trial_seeds"]):
                raise ValueError("trial count out of range")
            if args.limit is not None and args.limit < 1:
                raise ValueError("limit must be positive")
            ids = m["splits"][args.split][:args.limit]
            assert_api_budget(cfg, len(ids) * args.trials, public)
            output, manifest = new_run("collect", cfg, roles, prompt)
            if frozen and protocol_signature(manifest) != frozen["protocol_signature"]:
                finish(output, manifest, status="rejected")
                raise ValueError("protocol/model/source changed since candidate freeze")
            manifest.update(group=args.group, split=args.split, optimization_seed=args.optimization_seed,
                            frozen_candidate=frozen)
            write_json(output / "manifest.json", manifest)
            traces, grades = [], []
            try:
                for task_id in ids:
                    for trial in range(args.trials):
                        t, g = collect_one(output, reference, task_id, args.split, prompt, args.group, trial,
                                           cfg["trial_seeds"][trial], cfg, rubric, args.optimization_seed)
                        traces.append(t); grades.append(g)
                assert_membership(traces, m)
                make_report(traces, grades, output / "report")
                complete = all(t.status == "complete" and t.reference.get("official_reward") is not None for t in traces) and all(g.overall not in {"error", "parse_error"} for g in grades)
                finish(output, manifest, status="complete", benchmark_complete=complete, expected_records=len(ids) * args.trials)
            except BaseException:
                finish(output, manifest, status="interrupted", benchmark_complete=False)
                raise
            print(output); return
        from .optimize import RetailAdapter, optimize_prompt
        assert_api_budget(cfg, cfg["max_metric_calls"], public)
        output, manifest = new_run("optimize", cfg, roles, prompt)
        manifest.update(group=args.group, optimization_seed=args.seed, split="dev")
        write_json(output / "manifest.json", manifest)
        def evaluate_one(item, text, call):
            return collect_one(output, reference, item["task_id"], item["split"], text, args.group,
                               0, cfg["trial_seeds"][0], cfg, rubric, args.seed, call)
        adapter = RetailAdapter(evaluate_one, cfg["groups"][args.group]["feedback"], output,
                                cfg["max_metric_calls"], cfg["max_feedback_chars"])
        try:
            result = optimize_prompt(adapter, prompt, [{"task_id": i, "split": "train"} for i in m["splits"]["train"]],
                                     [{"task_id": i, "split": "dev"} for i in m["splits"]["dev"]],
                                     ModelEndpoint.from_env("reflection"), cfg,
                                     (ROOT / cfg["feedback_prompt"]).read_text(encoding="utf-8"), args.seed)
            finish(output, manifest, status="complete", benchmark_complete=True, optimization=result)
        except BaseException:
            finish(output, manifest, status="interrupted", benchmark_complete=False, metric_calls=adapter.calls)
            raise
        print(output); return
    if cmd in {"judge", "judge-matrix"}:
        traces = traces_at(args.traces)
        if not traces or any(t.source != "live" for t in traces):
            raise ValueError("model judge experiments require live trajectories")
        assert_membership(traces, split_manifest())
        groups = cfg["judge_groups"] if cmd == "judge-matrix" else {args.version: {"model_role": args.role, "prompt": "generic" if args.generic else "layered"}}
        endpoints({v["model_role"] for v in groups.values()})
        output, manifest = new_run(cmd, cfg, {v["model_role"] for v in groups.values()})
        manifest["input_traces_sha256"] = digest([t.model_dump() for t in traces])
        write_jsonl(output / "traces.jsonl", traces)
        gold = human_gold(args.gold, traces) if cmd == "judge-matrix" and args.gold else None
        records = read_jsonl(args.gold) if cmd == "judge-matrix" and args.gold else None
        all_grades = {}
        for group, settings in groups.items():
            folder = output / group; folder.mkdir()
            write_jsonl(folder / "traces.jsonl", traces)
            grades = []
            for trace in traces:
                grade, raw = judge_trace(trace, rubric, (ROOT / cfg["judge_prompt"]).read_text(encoding="utf-8"),
                                         ModelEndpoint.from_env(settings["model_role"]), cfg, group, settings["prompt"] == "generic")
                grades.append(grade)
                write_json(folder / "raw" / (digest(trace.trace_id) + ".json"), raw)
                write_jsonl(folder / "grades.jsonl", grades)
            make_report(traces, grades, folder / "report", gold, gold_records=records)
            all_grades[group] = grades
        if gold is not None:
            compare_judges(all_grades, gold, output / "comparison")
        finish(output, manifest, status="complete")
        print(output); return
    if cmd == "judge-robustness":
        traces = traces_at(args.traces)
        if not traces or any(t.source != "live" for t in traces):
            raise ValueError("verbosity robustness requires live trajectories")
        assert_membership(traces, split_manifest())
        endpoint = ModelEndpoint.from_env(args.role)
        output, manifest = new_run("judge-robustness", cfg, [args.role])
        prompt = (ROOT / cfg["judge_prompt"]).read_text(encoding="utf-8")
        originals, variants = [], []
        for trace in traces:
            variant = verbosity_variant(trace)
            original_grade, raw_a = judge_trace(trace, rubric, prompt, endpoint, cfg, args.version + "-original")
            variant_grade, raw_b = judge_trace(variant, rubric, prompt, endpoint, cfg, args.version + "-verbose")
            originals.append(original_grade); variants.append(variant_grade)
            write_json(output / "raw" / (digest(trace.trace_id) + ".original.json"), raw_a)
            write_json(output / "raw" / (digest(trace.trace_id) + ".verbose.json"), raw_b)
        write_jsonl(output / "traces.jsonl", traces)
        write_jsonl(output / "variants.jsonl", [verbosity_variant(t) for t in traces])
        write_jsonl(output / "grades.jsonl", originals)
        write_jsonl(output / "grades_variant.jsonl", variants)
        summary = verbosity_consistency(originals, variants)
        write_json(output / "verbosity.json", summary)
        finish(output, manifest, status="complete", input_traces_sha256=digest([t.model_dump() for t in traces]),
               verbosity=summary)
        print(output); return
    if cmd == "report":
        traces = traces_at(args.run / "traces.jsonl")
        grades = [Grade.model_validate(r) for r in read_jsonl(args.run / "grades.jsonl")]
        index = {t.trace_id: t for t in traces}
        for g in grades:
            validate_grade(g, index[g.trace_id])
        gold, records = None, None
        if args.gold:
            gold = human_gold(args.gold, traces)
            records = read_jsonl(args.gold)
        output = args.run / "report"
        make_report(traces, grades, output, gold, gold_records=records)
        if gold is not None:
            write_json(output / "fixed_coverage.json", judge_metrics(grades, gold, args.coverage))
            write_json(output / "coverage_curve.json", [judge_metrics(grades, gold, c / 20) for c in range(1, 21)])
            compare_judges({grades[0].judge_version: grades}, gold, output)
        print(output); return
    if cmd == "compare":
        paths = args.a + args.b
        manifests = [read(p / "manifest.json") for p in paths]
        if any(m.get("split") != "test" or not m.get("benchmark_complete") or m["status"] != "complete" for m in manifests):
            raise ValueError("comparison requires complete formal test runs")
        if len({protocol_signature(m) for m in manifests}) != 1:
            raise ValueError("incompatible experimental protocols")
        a = [t for p in args.a for t in traces_at(p / "traces.jsonl")]
        b = [t for p in args.b for t in traces_at(p / "traces.jsonl")]
        if len({t.agent_version for t in a}) != 1 or len({t.agent_version for t in b}) != 1:
            raise ValueError("each arm must contain one method")
        expected = set(split_manifest()["splits"]["test"])
        if {t.task_id for t in a} != expected or {t.task_id for t in b} != expected:
            raise ValueError("all 40 fixed test tasks required")
        output, manifest = new_run("compare", cfg)
        result = paired_bootstrap(a, b, cfg["bootstrap_samples"])
        result["input_runs"] = [str(p.resolve()) for p in paths]
        write_json(output / "comparison.json", result)
        finish(output, manifest, status="complete"); print(output); return
    if cmd == "aggregate":
        manifests = [read(p / "manifest.json") for p in args.runs]
        if any(m.get("split") != "test" or not m.get("benchmark_complete") or m["status"] != "complete" for m in manifests):
            raise ValueError("aggregate requires complete formal test runs")
        if len({protocol_signature(m) for m in manifests}) != 1:
            raise ValueError("aggregate one model/protocol at a time")
        traces = [t for p in args.runs for t in traces_at(p / "traces.jsonl")]
        grades = [Grade.model_validate(r) for p in args.runs for r in read_jsonl(p / "grades.jsonl")]
        output, manifest = new_run("aggregate", cfg)
        write_jsonl(output / "traces.jsonl", traces); write_jsonl(output / "grades.jsonl", grades)
        make_report(traces, grades, output / "report")
        finish(output, manifest, status="complete", input_runs=[str(p.resolve()) for p in args.runs],
               input_protocol_signature=protocol_signature(manifests[0]))
        print(output); return
    if cmd == "annotation-export":
        from .data import stratified_sample
        traces = traces_at(args.traces)
        if any(t.source != "live" for t in traces):
            raise ValueError("human gold collection requires live traces")
        selected = stratified_sample(traces, args.count, args.seed) if args.count else traces
        if args.output.exists():
            raise ValueError("do not overwrite an annotation packet")
        blind_packets(selected, args.output)
        print(f"{len(selected)} blind packets -> {args.output}"); return
    if cmd == "pool":
        if args.output.exists():
            raise ValueError("pool output already exists")
        manifests = [read(p / "manifest.json") for p in args.runs]
        if any(m["kind"] != "collect" or m["status"] != "complete" for m in manifests):
            raise ValueError("pool requires completed collection runs")
        records = [t for p in args.runs for t in traces_at(p / "traces.jsonl")]
        if not records or any(t.source != "live" for t in records) or len({t.split for t in records}) != 1:
            raise ValueError("pool one live split at a time")
        if len({t.trace_id for t in records}) != len(records):
            raise ValueError("duplicate trace identity in pool")
        assert_membership(records, split_manifest())
        kept = [t for t in records if t.status == "complete"]
        write_jsonl(args.output, kept)
        write_json(args.output.with_suffix(".manifest.json"),
                   {"split": records[0].split, "input_records": len(records), "kept": len(kept),
                    "excluded_execution_errors": len(records) - len(kept), "pool_sha256": digest([t.model_dump() for t in kept]),
                    "input_runs": [{"path": str(p.resolve()), "manifest_sha256": digest(m)} for p, m in zip(args.runs, manifests)]})
        print(f"{len(kept)} traces -> {args.output}"); return
    if cmd == "annotation-import":
        if args.output.exists():
            raise ValueError("annotation output already exists")
        print(unblind_annotations(args.packets, args.mapping, args.output)); return
    if cmd == "export-sft":
        count = export_sft(traces_at(args.traces), read_jsonl(args.labels), args.output,
                           (ROOT / cfg["judge_prompt"]).read_text(encoding="utf-8"), split_manifest(), rubric,
                           cfg.get("judge_sft_max_trajectories", 2000))
        print(f"{count} train-only SFT rows -> {args.output}"); return
    if cmd == "judge-sft-config":
        seeds = [args.seed] if args.seed else list(JUDGE_SFT_SEEDS)
        for seed in seeds:
            judge_sft_config(seed, args.output, args.data.resolve())
        print(f"{len(seeds)} LlamaFactory config(s) -> {args.output}"); return
    raise ValueError("unhandled command")


if __name__ == "__main__":
    raise SystemExit(main())
