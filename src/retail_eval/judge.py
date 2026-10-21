"""Evidence-constrained model judging; deterministic fixtures are demo-only."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import httpx

from .schema import Grade, Trace, validate_grade


@dataclass(frozen=True)
class ModelEndpoint:
    role: str
    model: str
    base_url: str
    api_key: str

    @classmethod
    def from_env(cls, role: str):
        role = role.upper()
        model = os.getenv(f"{role}_MODEL", "").strip()
        base = (os.getenv(f"{role}_BASE_URL") or os.getenv("API_BASE_URL") or os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        key = os.getenv(f"{role}_API_KEY") or os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        if not model or not key:
            raise ValueError(f"Configure {role}_MODEL and {role}_API_KEY/API_KEY in .env (local servers may use a dummy key).")
        url = httpx.URL(base)
        if url.scheme not in {"http", "https"} or url.userinfo or url.query:
            raise ValueError("endpoint must be an http(s) base URL without credentials or query")
        return cls(role, model, base, key)

    def public(self):
        return {"role": self.role, "model": self.model, "base_url": self.base_url}

    def complete(self, messages: list[dict], config: dict, json_mode=False) -> tuple[str, dict]:
        body = {"model": self.model, "messages": messages, "temperature": config["temperature"],
                "max_tokens": config["max_output_tokens"]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        for attempt in range(config["transport_retries"] + 1):
            try:
                response = httpx.post(self.base_url + "/chat/completions", json=body,
                                      headers={"Authorization": "Bearer " + self.api_key}, timeout=config["api_timeout"])
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < config["transport_retries"]:
                        time.sleep(min(2 ** attempt, 4))
                        continue
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"], data.get("usage", {})
            except httpx.TransportError:
                if attempt == config["transport_retries"]:
                    raise RuntimeError("model transport failed after bounded retries") from None
                time.sleep(min(2 ** attempt, 4))
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(f"model endpoint returned HTTP {exc.response.status_code}") from None
        raise RuntimeError("model retry limit exhausted")


def judge_payload(trace: Trace, rubric: dict, version: str):
    return {"trace_id": trace.trace_id, "judge_version": version, "rubric": rubric,
            "output_schema": Grade.model_json_schema(), **trace.visible()}


def judge_trace(trace: Trace, rubric: dict, prompt: str, endpoint: ModelEndpoint, config: dict, version: str,
                generic=False) -> tuple[Grade, dict]:
    if trace.status == "error":
        return Grade(trace_id=trace.trace_id, judge_version=version, overall="error", error="agent_run_error"), {}
    started = time.perf_counter()
    payload = judge_payload(trace, rubric, version)
    if generic:
        # Same business criteria/output contract, without the explicit funnel instruction.
        prompt = "Evaluate whether this retail execution satisfies the supplied business criteria. Return JSON matching output_schema, cite event IDs, and abstain if evidence is insufficient."
    raw = {}
    try:
        text, usage = endpoint.complete([{"role": "system", "content": prompt},
                                         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}], config, json_mode=True)
        raw = {"content": text, "usage": usage}
        try:
            grade = Grade.model_validate_json(text)
            if grade.judge_version != version:
                raise ValueError("judge version mismatch")
            validate_grade(grade, trace)
        except (ValueError, TypeError):
            grade = Grade(trace_id=trace.trace_id, judge_version=version, overall="parse_error",
                          error="invalid JSON, evidence, funnel semantics or output contract")
        grade.usage = usage
    except Exception as exc:
        grade = Grade(trace_id=trace.trace_id, judge_version=version, overall="error", error=type(exc).__name__)
        raw = {"error_type": type(exc).__name__}
    grade.elapsed_seconds = time.perf_counter() - started
    return grade, raw


def fixture_grade(trace: Trace, fixture_labels: dict[str, dict], version="fixture-rule-v1"):
    if trace.source != "fixture":
        raise ValueError("fixture grading cannot score live traces")
    grade = Grade.model_validate({**fixture_labels[trace.trace_id], "trace_id": trace.trace_id, "judge_version": version})
    return validate_grade(grade, trace)
