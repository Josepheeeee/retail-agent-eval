"""Provenance, deterministic task splits and blind annotation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .schema import Grade, Trace, digest, read_jsonl, validate_grade, write_json, write_jsonl


def prepare_splits(reference: Path, output: Path, salt="retail-eval-v1", dev_count=20):
    domain = reference / "data/tau2/domains/retail"
    tasks = json.loads((domain / "tasks.json").read_text(encoding="utf-8"))
    official = json.loads((domain / "split_tasks.json").read_text(encoding="utf-8"))
    if (len(tasks), len(official["train"]), len(official["test"])) != (114, 74, 40):
        raise ValueError("expected tau-bench v1.0.1 retail 114/74/40; verify reference pin")
    ordered = sorted(official["train"], key=lambda t: hashlib.sha256(f"{salt}:{t}".encode()).hexdigest())
    splits = {"dev": ordered[:dev_count], "train": ordered[dev_count:], "test": official["test"]}
    all_ids = [t for ids in splits.values() for t in ids]
    if len(set(all_ids)) != len(all_ids) or set(all_ids) != {t["id"] for t in tasks}:
        raise ValueError("split overlap or missing tasks")
    manifest = {"source": "sierra-research/tau2-bench", "ref": "v1.0.1", "salt": salt,
                "tasks_sha256": digest(tasks), "official_splits_sha256": digest(official), "splits": splits}
    write_json(output, manifest)
    return manifest


def assert_membership(traces: list[Trace], manifest: dict):
    for t in traces:
        parent = t.parent_task_id or t.task_id
        if t.split == "demo":
            continue
        if parent not in manifest["splits"][t.split]:
            raise ValueError(f"{t.trace_id}: parent task violates split")


def clean_trace(trace: Trace) -> Trace:
    """Only removes known tool-internal instruction fields; never drops turns."""
    cleaned = trace.model_copy(deep=True)
    removed = []
    internal = {"internal_system_prompt", "internal_developer_prompt", "api_key", "authorization"}

    def scrub(obj, path):
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                if k.lower() in internal:
                    removed.append(path + "." + k)
                else:
                    result[k] = scrub(v, path + "." + k)
            return result
        if isinstance(obj, list):
            return [scrub(v, f"{path}[{i}]") for i, v in enumerate(obj)]
        return obj

    for event in cleaned.events:
        if event.role != "tool":
            continue
        try:
            obj = json.loads(event.content)
        except (ValueError, TypeError):
            continue
        event.content = json.dumps(scrub(obj, event.id), ensure_ascii=False)
    cleaned.metadata["cleaning"] = {"raw_sha256": digest(trace.model_dump()), "removed_fields": removed}
    return cleaned


def verbosity_variant(trace: Trace) -> Trace:
    """Semantics-preserving verbosity perturbation for Judge robustness.

    The final assistant message is restated with the identical facts, prefixed
    and suffixed with neutral restatement text. Tool events and all evidence IDs
    are unchanged; this is a heuristic, not a semantic equivalence proof.
    """
    variant = trace.model_copy(deep=True)
    variant.trace_id = trace.trace_id + "-verbose"
    variant.metadata = {**trace.metadata, "verbosity_of": trace.trace_id,
                        "perturbation": "final_assistant_restatement"}
    for event in reversed(variant.events):
        if event.role == "assistant" and event.content.strip() and not event.tool_calls:
            original = event.content.strip()
            event.content = (f"To restate the same outcome without adding facts: {original}\n\n"
                             f"In other words, the observed outcome remains: {original}")
            return variant
    raise ValueError("trace has no non-empty final assistant message to restate")


def blind_packets(traces: list[Trace], output: Path):
    if len({t.trace_id for t in traces}) != len(traces):
        raise ValueError("duplicate annotation trace IDs")
    packets, mapping = [], {}
    for trace in traces:
        bid = hashlib.sha256(("blind-v1:" + trace.trace_id).encode()).hexdigest()[:16]
        mapping[bid] = trace.trace_id
        packets.append({"blind_id": bid, "input": trace.visible(), "annotation": None,
                        "review": None,
                        "instructions": "Fill annotation with complete Grade fields except trace_id/judge_version: overall, all six layers, cause, error_type, earliest_error_event, attribution_uncertainty, confidence. Cite only visible event IDs and record support (direct/inferred/none). Add review with reviewer_id, round, status and notes. Do not consult automatic scores."})
    write_jsonl(output, packets)
    write_json(output.with_suffix(".mapping.json"), mapping)


def unblind_annotations(packets: Path, mapping: Path, output: Path):
    ids = json.loads(mapping.read_text(encoding="utf-8"))
    rows = []
    for packet in read_jsonl(packets):
        if packet.get("annotation") is None:
            continue
        annotation = dict(packet["annotation"])
        annotation.update(trace_id=ids[packet["blind_id"]], judge_version="human-v1")
        grade = Grade.model_validate(annotation)
        if grade.overall not in {"pass", "fail", "abstain"}:
            raise ValueError("human annotation must be pass/fail/abstain")
        visible = packet["input"]
        check = Trace(trace_id=grade.trace_id, task_id="annotation-contract", split="demo", source="fixture",
                      agent_version="hidden", model="hidden", policy=visible["policy"], events=visible["events"])
        validate_grade(grade, check)
        review = packet.get("review")
        if not isinstance(review, dict) or not review.get("reviewer_id"):
            raise ValueError("human annotation needs a review record with reviewer_id")
        if review.get("status") not in {"first", "recheck", "adjudicated"}:
            raise ValueError("review.status must be first/recheck/adjudicated")
        if not review.get("round"):
            raise ValueError("review.round is required")
        rows.append({"trace_id": grade.trace_id, "label_source": "human", "grade": grade.model_dump(),
                     "review": {**review, "annotation_sha256": digest(annotation)}})
    write_jsonl(output, rows)
    return len(rows)


def stratified_sample(traces: list[Trace], count: int, seed=2026):
    """Round-robin task/outcome strata; only the packet organizer sees outcomes."""
    import random
    from collections import defaultdict
    if not 0 < count <= len(traces):
        raise ValueError("annotation count exceeds available trajectories")
    if len({t.trace_id for t in traces}) != len(traces):
        raise ValueError("duplicate annotation trace IDs")
    if len({t.split for t in traces}) != 1:
        raise ValueError("sample each split separately using its registered quota")
    strata = defaultdict(list)
    for trace in traces:
        strata[(trace.parent_task_id or trace.task_id, str(trace.reference.get("official_reward")))].append(trace)
    rng = random.Random(seed)
    groups = [strata[k] for k in sorted(strata)]
    for group in groups:
        group.sort(key=lambda t: t.trace_id); rng.shuffle(group)
    rng.shuffle(groups)
    selected = []
    while len(selected) < count:
        for group in groups:
            if group and len(selected) < count:
                selected.append(group.pop())
    return selected
