"""DeepAgents as a constrained retail participant in the official tau runner.

Business tools are exposed to the model but executed by tau, preserving its
turn-taking, environment reset and official outcome evaluators. Filesystem,
sub-agent and planning tools are not exposed in this preregistered profile.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from .judge import ModelEndpoint
from .schema import Event, Trace


def build_retail_graph(model, tool_schemas: list[dict], policy: str, prompt: str):
    from deepagents import create_deep_agent
    from langchain.agents.middleware import wrap_model_call

    allowed = {t["function"]["name"] for t in tool_schemas}

    @wrap_model_call
    def business_only(request, handler):
        def name(t):
            return t.get("name", t.get("function", {}).get("name")) if isinstance(t, dict) else t.name
        return handler(request.override(tools=[t for t in request.tools if name(t) in allowed]))

    protocol = "\nEach turn must contain either business tool calls OR a message to the user, never both. Only the provided retail tools are available."
    return create_deep_agent(model=model, tools=tool_schemas, system_prompt=prompt + protocol + "\n<policy>\n" + policy + "\n</policy>",
                             middleware=[business_only], memory=[], skills=[], subagents=[])


def make_tau_agent_class(prompt: str, endpoint: ModelEndpoint, config: dict, model_factory=None):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage as LCToolMessage
    from langchain_openai import ChatOpenAI
    from tau2.agent.base_agent import HalfDuplexAgent
    from tau2.data_model.message import AssistantMessage, MultiToolMessage, ToolCall

    class RetailDeepAgent(HalfDuplexAgent):
        def __init__(self, tools, domain_policy, **kwargs):
            super().__init__(tools, domain_policy)
            self.model = (model_factory or ChatOpenAI)(model=endpoint.model, api_key=endpoint.api_key, base_url=endpoint.base_url,
                                    temperature=config["temperature"], max_tokens=config["max_output_tokens"],
                                    timeout=config["api_timeout"], max_retries=config["transport_retries"])
            self.graph = build_retail_graph(self.model, [t.openai_schema for t in tools], domain_policy, prompt)

        def get_init_state(self, message_history=None):
            # tau injects its standard opening greeting even for a fresh task.
            # Copy only this task's supplied history; never load prior sessions.
            messages = []
            for m in message_history or []:
                if m.role == "assistant":
                    calls = [{"id": c.id, "name": c.name, "args": c.arguments} for c in m.tool_calls or []]
                    messages.append(AIMessage(content=m.content or "", tool_calls=calls))
                elif m.role == "user":
                    messages.append(HumanMessage(content=m.content or ""))
                elif m.role == "tool":
                    messages.append(LCToolMessage(content=m.content or "", tool_call_id=m.id))
                else:
                    raise ValueError("unsupported private/system history")
            return {"messages": messages}

        def set_seed(self, seed):
            if hasattr(self.model, "seed"):
                self.model.seed = seed

        @classmethod
        def is_stop(cls, message):
            return bool(message.content and "###STOP###" in message.content)

        def generate_next_message(self, message, state):
            incoming = message.tool_messages if isinstance(message, MultiToolMessage) else [message]
            for m in incoming:
                if m.role == "tool":
                    state["messages"].append(LCToolMessage(content=m.content or "", tool_call_id=m.id))
                else:
                    state["messages"].append(HumanMessage(content=m.content or ""))
            # Pause before business tools: tau is the sole owner of environment writes.
            result = self.graph.invoke({"messages": state["messages"]}, interrupt_before=["tools"],
                                       config={"recursion_limit": config["max_steps"]})
            last = result["messages"][-1]
            if not isinstance(last, AIMessage):
                raise RuntimeError("DeepAgents did not emit an assistant message")
            state["messages"].append(last)
            calls = [ToolCall(id=c["id"], name=c["name"], arguments=c["args"], requestor="assistant") for c in last.tool_calls]
            content = last.content if isinstance(last.content, str) else "".join(b.get("text", "") for b in last.content if isinstance(b, dict))
            if calls:
                content = None  # tau protocol disallows prose alongside tool calls.
            usage = last.usage_metadata or {}
            return AssistantMessage(role="assistant", content=content, tool_calls=calls or None,
                                    usage=usage), state

    return RetailDeepAgent


def reference_version(reference: Path):
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=reference, text=True).strip()


def load_tau(reference: Path):
    import sys
    expected = subprocess.check_output(["git", "rev-parse", "v1.0.1^{commit}"], cwd=reference, text=True).strip()
    if reference_version(reference) != expected:
        raise ValueError("tau reference must be checked out at v1.0.1")
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=reference, text=True).strip():
        raise ValueError("tracked tau reference files have changed")
    os.environ["TAU2_DATA_DIR"] = str(reference / "data")
    src = str(reference / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def run_tau_task(reference: Path, task_id: str, split: str, prompt: str, group: str, trial: int, seed: int,
                 config: dict, optimization_seed: int | None = None, raw_callback=None) -> tuple[Trace, dict]:
    agent_ep, user_ep, judge_ep = (ModelEndpoint.from_env(r) for r in ("agent", "user", "judge"))
    load_tau(reference)
    from tau2.data_model.simulation import TextRunConfig
    from tau2.evaluator.evaluator import EvaluationType, evaluate_simulation
    from tau2.registry import registry
    from tau2.run import get_tasks
    from tau2.runner.build import build_orchestrator
    import tau2.evaluator.evaluator_nl_assertions as nl

    # Pin the upstream NL evaluator to the configured judge, not its implicit default.
    nl.DEFAULT_LLM_NL_ASSERTIONS = "openai/" + judge_ep.model.removeprefix("openai/")
    nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS = {"api_base": judge_ep.base_url, "api_key": judge_ep.api_key,
                                      "temperature": config["temperature"], "timeout": config["api_timeout"],
                                      "num_retries": config["transport_retries"], "max_tokens": config["max_output_tokens"]}
    cls = make_tau_agent_class(prompt, agent_ep, config)
    factory_name = "retail_deepagents"
    # Registration is changed only between serial tasks; concurrent collection is prohibited.
    registry._agent_factories.pop(factory_name, None)
    registry.register_agent_factory(lambda tools, domain_policy, **kw: cls(tools, domain_policy), name=factory_name)
    tau_config = TextRunConfig(domain="retail", agent=factory_name, user="user_simulator", llm_agent=agent_ep.model,
                              llm_user="openai/" + user_ep.model.removeprefix("openai/"),
                              llm_args_agent={}, llm_args_user={"api_base": user_ep.base_url, "api_key": user_ep.api_key,
                                                              "temperature": config["temperature"], "max_tokens": config["max_output_tokens"],
                                                              "timeout": config["api_timeout"], "num_retries": config["transport_retries"]},
                              max_steps=config["max_steps"], max_errors=3, num_trials=1, seed=seed,
                              auto_review=False, verbose_logs=False)
    task = get_tasks("retail", task_ids=[task_id])[0]
    policy = (reference / "data/tau2/domains/retail/policy.md").read_text(encoding="utf-8")
    tid = f"{group}-s{optimization_seed}-t{task_id}-r{trial}"
    started = time.perf_counter()
    raw, orchestrator = {}, None
    official_responses = []
    original_generate = nl.generate
    def audited_nl_generate(*args, **kwargs):
        message = original_generate(*args, **kwargs)
        official_responses.append(message.model_dump(mode="json"))
        results = json.loads(message.content)["results"]
        expected = task.evaluation_criteria.nl_assertions or []
        if len(results) != len(expected) or sorted(r["expectedOutcome"] for r in results) != sorted(expected):
            raise ValueError("official NL evaluator omitted or invented assertions")
        if any(not isinstance(r.get("metExpectation"), bool) for r in results):
            raise ValueError("official NL evaluator returned non-boolean judgments")
        return message
    try:
        # Same official builder/evaluator, split at the persistence boundary so
        # an NL evaluator outage cannot erase an already executed trajectory.
        orchestrator = build_orchestrator(tau_config, task, seed=seed)
        sim = orchestrator.run()
        sim.policy = orchestrator.environment.get_policy()
        raw = sim.model_dump(mode="json")
        if raw_callback:
            raw_callback("execution", raw)
        if raw.get("termination_reason") in {"agent_error", "user_error", "infrastructure_error", "unexpected_error", "timeout", "context_window_exceeded"}:
            raise RuntimeError("simulation ended in an execution exception")
        nl.generate = audited_nl_generate
        sim.reward_info = evaluate_simulation(simulation=sim, task=task, evaluation_type=EvaluationType.ALL,
                                              solo_mode=False, domain="retail")
        raw = sim.model_dump(mode="json")
        raw["official_judge_responses"] = official_responses
        if raw_callback:
            raw_callback("scored", raw)
        events = []
        for i, m in enumerate(raw.get("messages", [])):
            role = m.get("role")
            if role not in {"user", "assistant", "tool"}:
                continue
            events.append(Event(id=f"e{i}", role=role, content=m.get("content") or "",
                                tool_calls=m.get("tool_calls") or [], tool_call_id=m.get("id") if role == "tool" else None,
                                turn=m.get("turn_idx") or i))
        reward = raw.get("reward_info") or {}
        reference_info = {"official_reward": reward.get("reward"), "components": reward,
                          "reward_basis": [getattr(r, "value", str(r)) for r in task.evaluation_criteria.reward_basis],
                          "nl_assertions_use_model": bool(task.evaluation_criteria.nl_assertions) and any(getattr(r, "value", str(r)) == "NL_ASSERTION" for r in task.evaluation_criteria.reward_basis),
                          "reference_commit": reference_version(reference)}
        return Trace(trace_id=tid, task_id=task_id, split=split, source="live", agent_version=group,
                     model=agent_ep.model, trial=trial, optimization_seed=optimization_seed, policy=policy,
                     events=events, reference=reference_info, elapsed_seconds=time.perf_counter() - started,
                     usage={"agent_cost": raw.get("agent_cost"), "user_cost": raw.get("user_cost"),
                            "official_judge": [{"usage": m.get("usage"), "cost": m.get("cost")} for m in official_responses],
                            "messages": [{"role": m.get("role"), "usage": m.get("usage")} for m in raw.get("messages", []) if m.get("usage")]},
                     metadata={"seed": seed, "termination_reason": raw.get("termination_reason"),
                               "mutating_tools": [t.name for t in orchestrator.environment.get_tools() if orchestrator.environment.tools.tool_mutates_state(t.name)],
                               "endpoints": [e.public() for e in (agent_ep, user_ep, judge_ep)]}), raw
    except Exception as exc:
        if not raw and orchestrator is not None:
            try:
                raw = {"messages": [m.model_dump(mode="json") for m in orchestrator.get_messages()]}
            except Exception:
                pass
        raw["error_type"] = type(exc).__name__
        raw["official_judge_responses"] = official_responses
        if raw_callback:
            raw_callback("error", raw)
        return Trace(trace_id=tid, task_id=task_id, split=split, source="live", agent_version=group,
                     model=agent_ep.model, trial=trial, optimization_seed=optimization_seed, policy=policy,
                     events=[Event(id=f"e{i}", role=m["role"], content=m.get("content") or "", tool_calls=m.get("tool_calls") or [])
                             for i, m in enumerate(raw.get("messages", [])) if m.get("role") in {"assistant", "user", "tool"}],
                     status="error", error=type(exc).__name__, elapsed_seconds=time.perf_counter() - started), raw
    finally:
        nl.generate = original_generate
