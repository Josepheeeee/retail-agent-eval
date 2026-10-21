from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from retail_eval.data import assert_membership, clean_trace, export_sft, prepare_splits, stratified_sample
from retail_eval.judge import ModelEndpoint, fixture_grade, judge_payload, judge_trace
from retail_eval.optimize import BudgetExhausted, RetailAdapter, feedback, optimize_prompt
from retail_eval.report import judge_metrics, make_report, paired_bootstrap
from retail_eval.run import ROOT, config_at, freeze_run, main
from retail_eval.schema import Grade, Trace, digest, read_jsonl, validate_grade


@pytest.fixture
def fixtures():
    traces = [Trace.model_validate(r) for r in read_jsonl(ROOT / "data/fixtures/traces.jsonl")]
    labels = json.loads((ROOT / "data/fixtures/labels.json").read_text(encoding="utf-8"))
    return traces, [fixture_grade(t, labels) for t in traces]


@pytest.fixture
def rubric():
    return yaml.safe_load((ROOT / "rubrics/retail.yaml").read_text(encoding="utf-8"))


def live_copy(t, split="train"):
    return t.model_copy(update={"source": "live", "split": split, "task_id": "1", "reference": {"official_reward": 1}})


def test_funnel_abstention_and_parallel_red(fixtures):
    traces, grades = fixtures
    assert {g.overall for g in grades} == {"pass", "fail", "abstain", "parse_error", "error"}
    for t, g in zip(traces, grades):
        validate_grade(g, t)
    privacy = next(g for g in grades if "privacy" in g.trace_id)
    assert privacy.layers["CTX"].status == "abstain"
    assert privacy.layers["TCC"].status == "blocked"
    assert privacy.layers["RED"].status == "fail"
    assert privacy.overall == "fail"


def test_fabricated_evidence_and_false_pass_rejected(fixtures):
    traces, grades = fixtures
    g = grades[1].model_copy(deep=True)
    g.layers["TCC"].evidence = ["nonexistent"]
    with pytest.raises(ValueError, match="fabricated"):
        validate_grade(g, traces[1])
    g = grades[1].model_copy(update={"overall": "pass"})
    with pytest.raises(ValueError, match="overall"):
        validate_grade(g, traces[1])


def test_no_answer_or_version_leakage(fixtures, rubric):
    trace = fixtures[0][0].model_copy(deep=True)
    trace.reference = {"SECRET_GOLD": "correct answer"}
    trace.metadata = {"SECRET_NOTE": "project memory"}
    trace.model = "SECRET_MODEL"
    payload = json.dumps(judge_payload(trace, rubric, "fixed"))
    assert all(token not in payload for token in ("SECRET_GOLD", "SECRET_NOTE", "SECRET_MODEL"))


def test_cleaning_is_immutable_and_auditable(fixtures):
    trace = fixtures[0][0].model_copy(deep=True)
    trace.events[2].content = '{"status":"submitted","nested":{"internal_system_prompt":"hidden"}}'
    before = trace.model_dump()
    cleaned = clean_trace(trace)
    assert trace.model_dump() == before
    assert len(cleaned.events) == len(trace.events)
    assert "hidden" not in cleaned.events[2].content
    assert cleaned.metadata["cleaning"]["raw_sha256"] == digest(before)
    assert cleaned.metadata["cleaning"]["removed_fields"] == ["e2.nested.internal_system_prompt"]


def test_split_pins_and_parent_isolation(tmp_path, fixtures):
    ref = ROOT / "external/tau-bench"
    if not ref.exists():
        pytest.skip("fetch tau reference for integration split checks")
    a = prepare_splits(ref, tmp_path / "a.json")
    b = prepare_splits(ref, tmp_path / "b.json")
    assert a == b
    assert {k: len(v) for k, v in a["splits"].items()} == {"train": 54, "dev": 20, "test": 40}
    t = live_copy(fixtures[0][0]).model_copy(update={"parent_task_id": a["splits"]["test"][0]})
    with pytest.raises(ValueError, match="parent"):
        assert_membership([t], a)


def test_sft_rejects_test_and_teacher_is_not_human(fixtures, rubric, tmp_path):
    t, g = fixtures[0][0], fixtures[1][0]
    manifest = {"splits": {"train": ["1"], "dev": [], "test": ["2"]}}
    test = live_copy(t, "test").model_copy(update={"task_id": "2"})
    label = {"trace_id": t.trace_id, "label_source": "teacher", "grade": g.model_dump()}
    with pytest.raises(ValueError, match="train"):
        export_sft([test], [label], tmp_path / "bad.jsonl", "judge", manifest, rubric)
    target = tmp_path / "sft.jsonl"
    assert export_sft([live_copy(t)], [label], target, "judge", manifest, rubric) == 1
    row = read_jsonl(target)[0]
    assert set(row) == {"messages"}
    assert read_jsonl(target.with_suffix(".provenance.jsonl"))[0]["label_source"] == "teacher"
    assert "official_reward" not in row["messages"][1]["content"]


def test_judge_parse_error_and_transport_are_not_pass(fixtures, rubric):
    class FakeEndpoint:
        def complete(self, *a, **kw):
            return "not JSON", {"total_tokens": 7}
    t = live_copy(fixtures[0][0])
    grade, raw = judge_trace(t, rubric, "judge", FakeEndpoint(), config_at(), "v1")
    assert grade.overall == "parse_error" and grade.usage["total_tokens"] == 7
    assert raw["content"] == "not JSON"
    class Broken:
        def complete(self, *a, **kw):
            raise TimeoutError("private details")
    grade, raw = judge_trace(t, rubric, "judge", Broken(), config_at(), "v1")
    assert grade.overall == "error"
    assert "private" not in json.dumps(raw)


def test_fixed_coverage_rejects_abstain_gaming():
    gold = {str(i): "fail" for i in range(10)}
    grades = [Grade(trace_id=str(i), judge_version="j", overall="fail" if i == 0 else "abstain", confidence=1) for i in range(10)]
    metrics = judge_metrics(grades, gold, .8)
    assert metrics["accuracy_decided"] == 1
    assert metrics["coverage"] == .1
    assert not metrics["coverage_target_met"]
    assert metrics["abstain"] == 9


def test_paired_bootstrap_preserves_task_trials_and_missing_rejected(fixtures):
    t = live_copy(fixtures[0][0], "test")
    def group(score):
        return [t.model_copy(update={"task_id": str(task), "trial": trial, "optimization_seed": seed,
                                     "reference": {"official_reward": score}})
                for task in range(4) for trial in range(3) for seed in (42, 43, 44)]
    a, b = group(0), group(1)
    r = paired_bootstrap(a, b, samples=100)
    assert r["difference"] == 1 and r["ci95"] == [1, 1]
    assert r["tasks"] == 4 and len(r["per_seed_difference"]) == 3
    with pytest.raises(ValueError, match="exactly"):
        paired_bootstrap(a[:-1], b, samples=10)


def test_feedback_equal_information_and_ablations(fixtures):
    t, g = live_copy(fixtures[0][1]), fixtures[1][1]
    natural, layered = feedback(t, g, "natural"), feedback(t, g, "layered")
    assert natural["Inputs"] == layered["Inputs"]
    assert natural["recommendation"] == layered["recommendation"]
    failed = g.layers["TCC"]
    for information in (failed.rule, failed.reason, failed.evidence[0]):
        assert information in natural["feedback"]
    assert "layer" not in json.dumps(feedback(t, g, "no_layer")["feedback"])
    assert all("evidence" not in r for r in feedback(t, g, "no_evidence")["feedback"])
    t.split = "test"
    with pytest.raises(ValueError, match="never test"):
        feedback(t, g, "layered")


def test_gepa_hard_budget_and_actual_public_api(fixtures, tmp_path):
    """Run real GEPA against an offline evaluator; it is not an Agent benchmark."""
    pytest.importorskip("gepa")
    t, g = live_copy(fixtures[0][1]), fixtures[1][1]
    t.reference = {"official_reward": 0}
    def evaluate(item, prompt, call):
        return t.model_copy(update={"task_id": item["task_id"], "split": item["split"]}), g
    adapter = RetailAdapter(evaluate, "layered", tmp_path, budget=4)
    class Reflection:
        def complete(self, *a, **kw):
            return "```\nKeep the original safe retail prompt.\n```", {}
    result = optimize_prompt(adapter, "safe prompt", [{"task_id": "1", "split": "train"}],
                             [{"task_id": "2", "split": "dev"}], Reflection(), config_at(), "prompt only", 42)
    assert adapter.calls <= 4
    assert result["development_score"] == 0
    assert list((tmp_path / "reflections").glob("*.json"))
    assert (tmp_path / "selected_prompt.md").exists()
    exhausted = RetailAdapter(evaluate, "layered", tmp_path / "other", budget=1)
    with pytest.raises(BudgetExhausted):
        exhausted.evaluate([{"split": "train"}] * 2, {"agent_prompt": "p"})
    assert exhausted.calls == 0


def test_freeze_rejects_incomplete_or_nondev(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"status": "complete", "split": "test", "benchmark_complete": True}))
    with pytest.raises(ValueError, match="development"):
        freeze_run(tmp_path)


def test_report_accounts_for_every_record_and_never_claims_fixtures(fixtures, tmp_path):
    traces, grades = fixtures
    r = make_report(traces, grades, tmp_path)
    assert r["not_a_benchmark"]
    assert sum(v["n"] for v in r["versions"]) == 9
    assert r["versions"][0]["official_success_complete"] is None
    assert sum(r["versions"][0][k] for k in ("judge_pass", "judge_fail", "abstain", "parse_error", "error")) == 9
    with pytest.raises(ValueError, match="every"):
        make_report(traces, grades[:-1], tmp_path)


def test_annotation_strata_and_model_identity_hidden(fixtures, tmp_path):
    from retail_eval.data import blind_packets
    ts = [live_copy(t) for t in fixtures[0]]
    sampled = stratified_sample(ts, 5)
    assert len(sampled) == 5 and sampled == stratified_sample(ts, 5)
    path = tmp_path / "blind.jsonl"
    blind_packets(sampled, path)
    content = path.read_text(encoding="utf-8")
    assert "no-model" not in content and "fixture-v1" not in content


def test_deepagents_tau_tool_roundtrip_and_fresh_state():
    pytest.importorskip("deepagents")
    from retail_eval.agent import load_tau, make_tau_agent_class
    ref = ROOT / "external/tau-bench"
    if not ref.exists():
        pytest.skip("fetch tau reference")
    load_tau(ref)
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    from pydantic import PrivateAttr
    from tau2.data_model.message import UserMessage, ToolMessage
    from tau2.domains.retail.environment import get_environment
    env = get_environment()
    uid = next(iter(env.tools.db.users))
    class Scripted(FakeMessagesListChatModel):
        _names: list = PrivateAttr(default_factory=list)
        def bind_tools(self, tools, **kwargs):
            self._names.append([t.get("function", {}).get("name", t.get("name")) if isinstance(t, dict) else t.name for t in tools])
            return self
    def factory(**kwargs):
        return Scripted(responses=[AIMessage(content="", tool_calls=[{"id": "c1", "name": "get_user_details", "args": {"user_id": uid}}]), AIMessage(content="I found your account.")])
    cls = make_tau_agent_class("retail prompt", ModelEndpoint("agent", "scripted", "http://localhost/v1", "dummy"), config_at(), factory)
    agent = cls(env.get_tools(), env.get_policy())
    state = agent.get_init_state()
    message, state = agent.generate_next_message(UserMessage(role="user", content="Find my account " + uid), state)
    assert message.tool_calls[0].name == "get_user_details"
    assert state["messages"][-1].tool_calls
    # Environment, not the DeepAgents tool node, executes the actual retail tool.
    result = env.use_tool("get_user_details", user_id=uid)
    result_text = result.model_dump_json() if hasattr(result, "model_dump_json") else json.dumps(result)
    response, _ = agent.generate_next_message(ToolMessage(role="tool", id="c1", content=result_text), state)
    assert response.content == "I found your account."
    assert agent.get_init_state()["messages"] == []
    assert all(set(names) <= {t.name for t in env.get_tools()} for names in agent.model._names)
    assert not any(name in {"read_file", "write_file", "task", "execute", "write_todos"} for names in agent.model._names for name in names)
    other = get_environment()
    original = other.get_db_hash()
    env.tools.db.users[uid].name.first_name = "CHANGED_TEST_ONLY"
    assert other.get_db_hash() == original and env.get_db_hash() != original


def test_missing_model_fails_before_run_creation(monkeypatch):
    for k in ("API_KEY", "OPENAI_API_KEY", "AGENT_API_KEY", "AGENT_MODEL"):
        monkeypatch.delenv(k, raising=False)
    assert main(["collect", "--split", "train", "--limit", "5", "--trials", "1"]) == 2


@pytest.mark.parametrize("index,outage", [(i, False) for i in range(5)] + [(4, True)])
def test_official_runner_with_scripted_models_is_only_an_integration_check(index, outage, monkeypatch):
    """Real task/retail environment and evaluator; scripted models, no benchmark claim."""
    import ast
    import retail_eval.agent as adapter
    ref = ROOT / "external/tau-bench"
    if not ref.exists():
        pytest.skip("fetch tau reference")
    adapter.load_tau(ref)
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    from tau2.registry import registry
    from tau2.user.user_simulator_base import HalfDuplexUser, STOP
    from tau2.data_model.message import UserMessage, AssistantMessage
    from tau2.domains.retail.environment import get_environment
    import tau2.evaluator.evaluator_nl_assertions as nl
    uid = next(iter(get_environment().tools.db.users))
    class Scripted(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self
    def factory(**kwargs):
        return Scripted(responses=[AIMessage(content="", tool_calls=[{"id": "c1", "name": "get_user_details", "args": {"user_id": uid}}]), AIMessage(content="Account retrieved.")])
    original_class = adapter.make_tau_agent_class
    monkeypatch.setattr(adapter, "make_tau_agent_class", lambda prompt, endpoint, config: original_class(prompt, endpoint, config, factory))
    class User(HalfDuplexUser):
        def __init__(self, tools=None, instructions=None, **kwargs):
            super().__init__(instructions=instructions, tools=tools)
        def get_init_state(self, message_history=None):
            return 0
        def generate_next_message(self, message, state):
            return UserMessage(role="user", content=("Find my account " + uid) if state == 0 else STOP), state + 1
        @classmethod
        def is_stop(cls, message):
            return message.content == STOP
    monkeypatch.setitem(registry._users, "user_simulator", User)
    def fake_nl(**kwargs):
        if outage:
            raise TimeoutError("scripted NL evaluator outage")
        expected = ast.literal_eval(kwargs["messages"][-1].content.split("expectedOutcomes:")[-1].strip())
        return AssistantMessage(role="assistant", content=json.dumps({"results": [{"expectedOutcome": e, "metExpectation": False, "reasoning": "Scripted integration check"} for e in expected]}))
    monkeypatch.setattr(nl, "generate", fake_nl)
    for role in ("AGENT", "USER", "JUDGE"):
        monkeypatch.setenv(role + "_MODEL", "scripted-not-a-model")
        monkeypatch.setenv(role + "_API_KEY", "dummy")
        monkeypatch.setenv(role + "_BASE_URL", "http://localhost:1/v1")
    train_ids = json.loads((ROOT / "data/manifests/splits.json").read_text())["splits"]["train"]
    tasks = json.loads((ref / "data/tau2/domains/retail/tasks.json").read_text())
    with_nl = [t["id"] for t in tasks if t["id"] in train_ids and t["evaluation_criteria"].get("nl_assertions")]
    task_id = (train_ids[:3] + with_nl[:2])[index]
    stages = []
    trace, raw = adapter.run_tau_task(ref, task_id, "train", "retail prompt", "integration-test", 0, 100,
                                      config_at(), raw_callback=lambda stage, raw: stages.append(stage))
    if outage:
        assert trace.status == "error" and raw["messages"]
        assert stages == ["execution", "error"]
        assert trace.reference.get("official_reward") is None
        return
    assert trace.status == "complete", raw
    assert trace.reference["official_reward"] in (0, 1)
    assert any(e.role == "tool" for e in trace.events)
    assert stages == ["execution", "scored"]
    assert "evaluation_criteria" not in json.dumps(trace.visible())


def test_formal_test_requires_frozen_candidate(monkeypatch):
    import retail_eval.run as runner
    with pytest.raises(ValueError, match="formal test"):
        for role in ("AGENT", "USER", "JUDGE"):
            monkeypatch.setenv(role + "_MODEL", "dummy")
            monkeypatch.setenv(role + "_API_KEY", "dummy")
        args = runner.cli_parser().parse_args(["collect", "--split", "test"])
        runner.execute(args, config_at(), {})


def test_freeze_binds_prompt_and_fixed_protocol(fixtures, tmp_path):
    from retail_eval.run import protocol_signature
    from retail_eval.schema import write_json, write_jsonl
    prompt = "registered candidate"
    manifest = {"status": "complete", "benchmark_complete": True, "split": "dev", "group": "A0",
                "config": config_at(), "hashes": {"agent.md": digest(prompt), "retail.yaml": "rubric-v1"},
                "endpoints": {}, "source_hashes": {}, "packages": {}}
    write_json(tmp_path / "manifest.json", manifest)
    write_json(tmp_path / "snapshots/splits.json", {"splits": {"dev": [str(i) for i in range(20)]}})
    (tmp_path / "snapshots/agent.md").write_text(prompt, encoding="utf-8")
    trace = live_copy(fixtures[0][0], "dev")
    rows = [trace.model_copy(update={"trace_id": str(i), "task_id": str(i), "metadata": {"candidate_sha256": digest({"agent_prompt": prompt})}}) for i in range(20)]
    write_jsonl(tmp_path / "traces.jsonl", rows)
    frozen = json.loads(freeze_run(tmp_path).read_text(encoding="utf-8"))
    assert frozen["prompt_sha256"] == digest(prompt)
    assert frozen["protocol_signature"] == protocol_signature(manifest)
    manifest["hashes"]["retail.yaml"] = "changed"
    assert protocol_signature(manifest) != frozen["protocol_signature"]
    with pytest.raises(ValueError, match="already frozen"):
        freeze_run(tmp_path)


def test_judge_comparison_preserves_fixed_coverage_and_cost(fixtures, tmp_path):
    from retail_eval.report import compare_judges
    grades = fixtures[1][:7]
    gold = {g.trace_id: g.overall for g in grades}
    result = compare_judges({"J1": grades, "J3": grades}, gold, tmp_path)
    assert len(result) == 2
    assert all(r["accuracy_decided"] == 1 and r["mean_known_tokens"] is None for r in result)
    assert (tmp_path / "judge_reliability_cost.png").exists()
    assert not all(p["coverage_target_met"] for p in json.loads((tmp_path / "J1.coverage.json").read_text()))


def test_annotation_pool_rejects_duplicates_and_keeps_error_counts(fixtures, tmp_path):
    import retail_eval.run as runner
    from retail_eval.schema import write_json, write_jsonl
    task_id = json.loads((ROOT / "data/manifests/splits.json").read_text())["splits"]["train"][0]
    trace = live_copy(fixtures[0][0]).model_copy(update={"task_id": task_id})
    r1, r2 = tmp_path / "r1", tmp_path / "r2"
    for p in (r1, r2):
        write_json(p / "manifest.json", {"kind": "collect", "status": "complete"})
        write_jsonl(p / "traces.jsonl", [trace])
    target = tmp_path / "pool.jsonl"
    args = runner.cli_parser().parse_args(["pool", "--runs", str(r1), str(r2), "--output", str(target)])
    with pytest.raises(ValueError, match="duplicate"):
        runner.execute(args, config_at(), {})
    assert not target.exists()
    write_jsonl(r2 / "traces.jsonl", [trace.model_copy(update={"trace_id": "other", "status": "error", "error": "SyntheticError"})])
    runner.execute(args, config_at(), {})
    assert len(read_jsonl(target)) == 1
    provenance = json.loads(target.with_suffix(".manifest.json").read_text())
    assert provenance["excluded_execution_errors"] == 1 and provenance["input_records"] == 2
