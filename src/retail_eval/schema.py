"""Small explicit contracts shared by collection, scoring and analysis."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

LAYERS = ("CTX", "OOSR", "OOC", "TCC", "CNT", "RED")
Split = Literal["demo", "train", "dev", "test"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Event(Contract):
    id: str
    role: Literal["user", "assistant", "tool"]
    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_call_id: str | None = None
    turn: int = 0


class Trace(Contract):
    schema_version: int = 1
    trace_id: str
    task_id: str
    parent_task_id: str | None = None
    split: Split
    source: Literal["fixture", "live"]
    agent_version: str
    model: str
    trial: int = 0
    optimization_seed: int | None = None
    policy: str
    events: list[Event]
    reference: dict[str, Any] = Field(default_factory=dict)
    status: Literal["complete", "error"] = "complete"
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    elapsed_seconds: float = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_events(self):
        ids = [e.id for e in self.events]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate event IDs")
        if self.source == "fixture" and self.split != "demo":
            raise ValueError("fixtures belong to demo, never benchmark splits")
        return self

    def visible(self) -> dict[str, Any]:
        """Deliberately excludes reference labels, private metadata and version IDs."""
        return {"policy": self.policy, "events": [e.model_dump() for e in self.events]}


class LayerGrade(Contract):
    status: Literal["pass", "fail", "abstain", "blocked"]
    rule: str
    reason: str
    evidence: list[str] = Field(default_factory=list)


class Grade(Contract):
    trace_id: str
    judge_version: str
    overall: Literal["pass", "fail", "abstain", "parse_error", "error"]
    layers: dict[str, LayerGrade] = Field(default_factory=dict)
    cause: Literal["data", "prompt", "rubric", "agent", "unknown"] = "unknown"
    suggested_location: str = ""
    recommendation: str = ""
    confidence: float = Field(default=0.0, ge=0, le=1)
    error: str | None = None
    usage: dict[str, Any] = Field(default_factory=dict)
    elapsed_seconds: float = 0


def validate_grade(grade: Grade, trace: Trace) -> Grade:
    if grade.trace_id != trace.trace_id:
        raise ValueError("grade/trace identity mismatch")
    if grade.overall in {"parse_error", "error"}:
        return grade
    if set(grade.layers) != set(LAYERS):
        raise ValueError("all six layers must be present")
    visible_ids = {e.id for e in trace.events}
    blocked = False
    for key in LAYERS:
        layer = grade.layers[key]
        if not set(layer.evidence) <= visible_ids:
            raise ValueError(f"fabricated evidence in {key}")
        if key == "RED":
            if layer.status == "blocked":
                raise ValueError("RED is independent and cannot be blocked")
        else:
            if blocked and layer.status != "blocked":
                raise ValueError("sequential layers after fail/abstain must be blocked")
            if not blocked and layer.status == "blocked":
                raise ValueError("unjustified blocked layer")
            blocked |= layer.status in {"fail", "abstain"}
        if key == "CTX" and layer.status == "fail":
            raise ValueError("insufficient evidence must abstain")
        if layer.status == "fail" and not layer.evidence:
            raise ValueError("failure requires observed evidence")
    statuses = [s.status for s in grade.layers.values()]
    expected = "fail" if "fail" in statuses else "abstain" if "abstain" in statuses else "pass"
    if grade.overall != expected:
        raise ValueError(f"overall must be {expected}")
    return grade


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(s) for s in path.read_text(encoding="utf-8-sig").splitlines() if s.strip()]


def write_json(path: Path, value: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r.model_dump() if isinstance(r, BaseModel) else r, ensure_ascii=False, default=str) + "\n" for r in rows), encoding="utf-8")
