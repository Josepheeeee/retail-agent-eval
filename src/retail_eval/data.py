"""Provenance, deterministic task splits, blind annotation and SFT export."""
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


def blind_packets(traces: list[Trace], output: Path):
    if len({t.trace_id for t in traces}) != len(traces):
        raise ValueError("duplicate annotation trace IDs")
    packets, mapping = [], {}
    for trace in traces:
        bid = hashlib.sha256(("blind-v1:" + trace.trace_id).encode()).hexdigest()[:16]
        mapping[bid] = trace.trace_id
        packets.append({"blind_id": bid, "input": trace.visible(), "annotation": None,
                        "instructions": "Fill annotation with complete Grade fields except trace_id/judge_version. Do not consult automatic scores."})
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
        rows.append({"trace_id": grade.trace_id, "label_source": "human", "grade": grade.model_dump()})
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


def export_sft(traces: list[Trace], labels: list[dict], output: Path, system_prompt: str, manifest: dict, rubric: dict):
    if output.exists():
        raise ValueError("SFT export already exists")
    assert_membership(traces, manifest)
    if len({t.trace_id for t in traces}) != len(traces):
        raise ValueError("duplicate input training traces")
    index = {t.trace_id: t for t in traces}
    rows, seen = [], set()
    for row in labels:
        trace = index[row["trace_id"]]
        if trace.split != "train" or trace.source != "live":
            raise ValueError("SFT export accepts only live train traces; demo/dev/test forbidden")
        if trace.status != "complete":
            raise ValueError("infrastructure errors are not SFT targets")
        if row["trace_id"] in seen:
            raise ValueError("duplicate training trace")
        seen.add(row["trace_id"])
        if row.get("label_source") not in {"human", "teacher"}:
            raise ValueError("label_source must explicitly be human or teacher")
        grade = validate_grade(Grade.model_validate(row["grade"]), trace)
        if grade.overall in {"parse_error", "error"}:
            raise ValueError("invalid label for SFT")
        target = grade.model_dump(exclude={"usage", "elapsed_seconds", "error"})
        # Identity placeholders prevent memorizing per-run trace IDs.
        target["trace_id"], target["judge_version"] = "input", "candidate"
        payload = {"trace_id": "input", "judge_version": "candidate", "rubric": rubric, **trace.visible()}
        rows.append({"messages": [{"role": "system", "content": system_prompt},
                                  {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                                  {"role": "assistant", "content": json.dumps(target, ensure_ascii=False)}],
                     "provenance": {"trace_id": trace.trace_id, "parent_task_id": trace.parent_task_id or trace.task_id,
                                    "split": trace.split, "label_source": row["label_source"],
                                    "trace_sha256": digest(trace.model_dump()), "label_sha256": digest(row)}})
    write_jsonl(output, [{"messages": r["messages"]} for r in rows])
    write_jsonl(output.with_suffix(".provenance.jsonl"), [r["provenance"] for r in rows])
    write_json(output.with_suffix(".manifest.json"), {"rows": len(rows), "split": "train", "sha256": digest(rows),
                                                      "source_manifest_sha256": digest(manifest)})
    return len(rows)
