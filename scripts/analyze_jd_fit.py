"""Quantify retail-agent-eval against the 70 archived evaluation JDs.

Deterministic and offline: reads only committed JD artifacts and source files,
then writes data/manifests/jd_fit.json and docs/JD_FIT.md. No model calls.

The coverage levels are an explicit author mapping from docs/JD_ANALYSIS.md
section 3 to this repository's implemented scope. They are not inferred from JD
text by a model, and they measure design coverage, not hiring probability or
live-model evidence.
"""
from __future__ import annotations

import itertools
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVIEW_PATH = ROOT / "data/manifests/jd_review.json"
OUT_JSON = ROOT / "data/manifests/jd_fit.json"
OUT_MD = ROOT / "docs/JD_FIT.md"

NON_GOALS = {"multimodal", "longctx", "code"}

# 1.0 = first-class implementation in this repository
# 0.5 = one layer or one sub-case only
# 0.0 = explicit non-goal for this project
COVERAGE: dict[str, tuple[float, str]] = {
    "benchmark": (1.0, "τ 零售 114 任务、54/20/40 划分、清单与哈希可追溯"),
    "metric": (1.0, "官方 reward 与六层 Grade 分开保存，不合成单一总分"),
    "judge": (1.0, "证据约束的固定 Judge、盲标与复核协议；当前不训练小 Judge"),
    "agent": (1.0, "τ 轨迹、工具调用、环境重置、最早错误事件"),
    "calibration": (1.0, "任务/种子配对 Bootstrap、ECE/Brier、人工一致性入口"),
    "contamination": (1.0, "父任务同源分组；test 不进入优化、水位或模拟题"),
    "safety": (0.5, "只有 RED 隐私/越权层，不是对抗安全 benchmark"),
    "multimodal": (0.0, "明确非目标，不用文本项目冒充多模态能力"),
    "longctx": (0.0, "明确非目标；由另一个基座评测项目负责 RULER"),
    "code": (0.0, "明确非目标；由另一个基座评测项目负责 HumanEval+"),
    "data": (0.75, "盲标导入导出；480 条标注尚未执行；模拟题规则已写、尚未生成"),
    "training": (0.0, "当前实验不包含模型微调"),
    "platform": (0.4, "CLI、manifest、报告、冻结/比较；不是调度/看板平台"),
    "diagnosis": (1.0, "六层、cause、error_type、earliest_error_event、证据支持"),
}

UPSTREAM_ROOTS = {
    "tau2", "deepagents", "gepa", "dspy", "langchain", "langchain_core",
    "langchain_openai", "litellm",
}

# Normalised attribution estimate. The point estimates sum to 100; each row is
# a judgement with roughly +/-3-5pp uncertainty, not a code-line measurement.
ESTIMATES = [
    ("τ-bench v1.0.1", "零售环境、114 任务、政策、数据库、模拟用户、官方 reward；agent.py 以 217 行适配",
     26, "external/tau-bench 固定 commit；官方 evaluator 与 user simulator 直接运行"),
    ("DeepAgents", "Agent 循环、消息状态、middleware；一处 create_deep_agent 接线",
     10, "agent.py 只做工具过滤、会话桥接与中断，不重写 agent loop"),
    ("GEPA", "optimize 循环、反思器、候选搜索；146 行 adapter",
     9, "gepa.optimize 直接调用；候选选择与预算边界为本项目补充"),
    ("淘宝文章", "六层判定、人工校准、修复回归闭环；落到 rubrics/retail.yaml",
     9, "方法来源；六层顺序、证据契约与离线实现为本项目工作"),
    ("AgentDebug", "失败分类 → 定位 → 可执行纠错反馈",
     3.5, "方法映射；未复用其任务、架构或数据"),
    ("Agentic CLEAR", "system / trace / node 三粒度",
     2.5, "方法映射；不移植其 UI 平台"),
    ("AgentRewardBench", "评分器独立校验、失败误放行与弃判统计",
     2.5, "盲标与 Judge 校准的方法依据"),
    ("AgentEval", "步骤依赖与错误传播（当前未建 DAG）",
     1.5, "仅设计参考；不声称实现 DAG 根因分析"),
    ("Who&When", "归因标注与验证；区分候选归因和已验证根因",
     1.5, "仅设计参考；当前为单 Agent，不复用其 who 准确率"),
    ("DSPy", "GEPA 集成与模块化优化的方法对照",
     0.5, "仅引用与版本记录，不进入运行路径"),
    ("AWM", "合成环境的可执行性与质量门槛",
     0.5, "仅扩展设想；未生成环境、未训练"),
    ("自研", "六层 rubric、证据契约、划分隔离、盲标、统计报告、预算门禁、模拟题筛选规则",
     33.5, "src 与 tests 的行数以本次脚本测量为准；当前不包含 Judge 微调"),
]


def mean(values):
    return sum(values) / len(values) if values else float("nan")


def score(record, levels):
    caps = record["capabilities"]
    return sum(levels[c] for c in caps) / len(caps)


def conditional_score(record, levels):
    kept = [c for c in record["capabilities"] if c not in NON_GOALS]
    if not kept:
        return None
    return sum(levels[c] for c in kept) / len(kept)


def fmt_pct(value):
    return f"{value * 100:.1f}%"


def module_imports_upstream(path: Path):
    text = path.read_text(encoding="utf-8")
    roots = set()
    for line in text.splitlines():
        match = re.match(r"\s*(?:from|import)\s+([A-Za-z0-9_.]+)", line)
        if match:
            roots.add(match.group(1).split(".")[0])
    return bool(roots & UPSTREAM_ROOTS)


def git_tracked_external():
    try:
        result = subprocess.run(
            ["git", "ls-files", "external"], cwd=ROOT, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return [line for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        pass
    return []


def build():
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    records = review["records"]
    levels = {cap: value[0] for cap, value in COVERAGE.items()}

    rows = []
    for record in records:
        rows.append({
            "jd_id": record["jd_id"],
            "company": record["company"],
            "title": record["title"],
            "category": record["category"],
            "level_kind": record["level_kind"],
            "capabilities": record["capabilities"],
            "score": score(record, levels),
            "conditional_score": conditional_score(record, levels),
        })

    all_scores = [row["score"] for row in rows]
    core_scores = [row["score"] for row in rows if row["category"] == "core"]
    adjacent_scores = [row["score"] for row in rows if row["category"] == "adjacent"]
    ic_scores = [row["score"] for row in rows if row["level_kind"] in {"intern", "campus"}]
    ic_core_scores = [
        row["score"] for row in rows
        if row["level_kind"] in {"intern", "campus"} and row["category"] == "core"
    ]
    cond_all = [row["conditional_score"] for row in rows if row["conditional_score"] is not None]
    cond_core = [
        row["conditional_score"] for row in rows
        if row["category"] == "core" and row["conditional_score"] is not None
    ]

    bands = {"ge_90": 0, "75_90": 0, "50_75": 0, "30_50": 0, "lt_30": 0}
    for value in all_scores:
        if value >= 0.9:
            bands["ge_90"] += 1
        elif value >= 0.75:
            bands["75_90"] += 1
        elif value >= 0.5:
            bands["50_75"] += 1
        elif value >= 0.3:
            bands["30_50"] += 1
        else:
            bands["lt_30"] += 1

    thresholds = []
    for threshold in (0.8, 0.7, 0.6, 0.5):
        n = sum(1 for row in rows if row["score"] >= threshold)
        n_core = sum(1 for row in rows if row["score"] >= threshold and row["category"] == "core")
        thresholds.append({"at_least": fmt_pct(threshold), "n": n, "core": n_core})

    frequencies = {}
    for record in records:
        for cap in record["capabilities"]:
            frequencies[cap] = frequencies.get(cap, 0) + 1
    tags = sum(frequencies.values())
    covered = sum(frequencies[cap] * levels[cap] for cap in frequencies)
    capability_loss = [
        {
            "capability": cap,
            "frequency": frequencies[cap],
            "level": levels[cap],
            "lost": frequencies[cap] * (1 - levels[cap]),
        }
        for cap in sorted(frequencies, key=lambda item: (-frequencies[item] * (1 - levels[item]), item))
    ]

    scenarios = {}
    scenario_specs = {
        "base": {},
        "platform_0.8": {"platform": 0.8},
        "training_0.9": {"training": 0.9},
        "safety_0.8": {"safety": 0.8},
        "three_weak_spots": {"platform": 0.8, "training": 0.9, "safety": 0.8},
        "all_but_non_goals": {"platform": 1.0, "training": 1.0, "safety": 1.0, "data": 1.0},
    }
    for name, changes in scenario_specs.items():
        adjusted = dict(levels)
        adjusted.update(changes)
        scenarios[name] = {
            "changes": changes,
            "mean": mean([score(record, adjusted) for record in records]),
        }

    sensitivity_values = []
    for platform, training, data, safety in itertools.product(
        (0.0, 0.4, 0.6), (0.25, 0.5, 0.75), (0.5, 0.75, 1.0), (0.25, 0.5, 0.75)
    ):
        adjusted = dict(levels)
        adjusted.update({"platform": platform, "training": training, "data": data, "safety": safety})
        sensitivity_values.append(mean([score(record, adjusted) for record in records]))

    src_files = sorted((ROOT / "src/retail_eval").glob("*.py"))
    src_lines = 0
    upstream_lines = 0
    upstream_files = []
    for path in src_files:
        lines = len(path.read_text(encoding="utf-8").splitlines())
        src_lines += lines
        if module_imports_upstream(path):
            upstream_lines += lines
            upstream_files.append(path.name)
    tests_lines = sum(
        len(path.read_text(encoding="utf-8").splitlines())
        for path in sorted((ROOT / "tests").glob("*.py"))
    )
    vendored = git_tracked_external()

    estimate_total = sum(row[2] for row in ESTIMATES)
    assert abs(estimate_total - 100) < 1e-9, estimate_total

    top = sorted(rows, key=lambda row: (-row["score"], row["jd_id"]))[:8]
    bottom = sorted(rows, key=lambda row: (row["score"], row["jd_id"]))[:5]
    non_goal_jds = sum(
        1 for record in records if set(record["capabilities"]) & NON_GOALS
    )

    payload = {
        "schema_version": 1,
        "analysis_date": "2026-10-22",
        "scope": {
            "records": len(records),
            "tags": tags,
            "note": "Design coverage of the current repository, not hiring probability or live-model evidence.",
        },
        "coverage_levels": {
            cap: {"level": value, "rationale": reason}
            for cap, (value, reason) in COVERAGE.items()
        },
        "summary": {
            "n": len(rows),
            "mean_all": mean(all_scores),
            "mean_core": mean(core_scores),
            "mean_adjacent": mean(adjacent_scores),
            "mean_intern_campus": mean(ic_scores),
            "mean_intern_campus_core": mean(ic_core_scores),
            "mean_conditional_all": mean(cond_all),
            "mean_conditional_core": mean(cond_core),
            "tags": tags,
            "tags_covered": covered,
            "tags_lost": tags - covered,
            "jds_with_non_goal": non_goal_jds,
            "jds_without_non_goal": len(rows) - non_goal_jds,
        },
        "bands": bands,
        "thresholds": thresholds,
        "capability_loss": capability_loss,
        "scenarios": scenarios,
        "sensitivity": {
            "min": min(sensitivity_values),
            "max": max(sensitivity_values),
            "base": mean(all_scores),
            "grid": {
                "platform": [0.0, 0.4, 0.6],
                "training": [0.25, 0.5, 0.75],
                "data": [0.5, 0.75, 1.0],
                "safety": [0.25, 0.5, 0.75],
            },
        },
        "top": top,
        "bottom": bottom,
        "records": rows,
        "external_dependency": {
            "code": {
                "src_files": len(src_files),
                "src_lines": src_lines,
                "upstream_import_files": upstream_files,
                "upstream_import_lines": upstream_lines,
                "upstream_import_share": upstream_lines / src_lines,
                "vendored_files": len(vendored),
                "vendored_lines": 0,
                "tests_lines": tests_lines,
            },
            "runtime_roles": [
                {"role": "环境、任务、官方评分、模拟用户", "provider": "τ-bench v1.0.1"},
                {"role": "被测 Agent 决策循环", "provider": "DeepAgents"},
                {"role": "提示优化与候选搜索", "provider": "GEPA"},
                {"role": "六层评分、证据校验、归因与报告", "provider": "本项目"},
            ],
            "estimates": [
                {"source": source, "what": what, "share": share, "evidence": evidence}
                for source, what, share, evidence in ESTIMATES
            ],
            "estimate_total_external": 100 - ESTIMATES[-1][2],
            "estimate_note": "Normalised capability-share estimate, +/-3-5pp per row; code share is measured separately.",
        },
    }
    return payload


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "/") for cell in row) + " |")
    return lines


def render(payload):
    summary = payload["summary"]
    code = payload["external_dependency"]["code"]
    top_rows = [
        (row["jd_id"], row["company"], row["title"][:32] + ("…" if len(row["title"]) > 32 else ""),
         fmt_pct(row["score"]))
        for row in payload["top"]
    ]
    bottom_rows = [
        (row["jd_id"], row["company"], row["title"][:32] + ("…" if len(row["title"]) > 32 else ""),
         fmt_pct(row["score"]))
        for row in payload["bottom"]
    ]
    level_rows = [
        (cap, data["level"], data["rationale"])
        for cap, data in payload["coverage_levels"].items()
    ]
    loss_rows = [
        (item["capability"], item["frequency"], item["level"], f"{item['lost']:.1f}")
        for item in payload["capability_loss"]
    ]
    band_rows = [
        ("≥ 90%", payload["bands"]["ge_90"]),
        ("75–90%", payload["bands"]["75_90"]),
        ("50–75%", payload["bands"]["50_75"]),
        ("30–50%", payload["bands"]["30_50"]),
        ("< 30%", payload["bands"]["lt_30"]),
    ]
    threshold_rows = [
        (item["at_least"], item["n"], item["core"]) for item in payload["thresholds"]
    ]
    scenario_rows = [
        ("当前口径", "—", fmt_pct(payload["scenarios"]["base"]["mean"])),
        ("平台 0.4 → 0.8", "调度/看板/CI 工具链", fmt_pct(payload["scenarios"]["platform_0.8"]["mean"])),
        ("训练 0 → 0.9", "若以后另做模型微调", fmt_pct(payload["scenarios"]["training_0.9"]["mean"])),
        ("安全 0.5 → 0.8", "独立安全/对抗评测", fmt_pct(payload["scenarios"]["safety_0.8"]["mean"])),
        ("平台 + 训练 + 安全", "三项都补", fmt_pct(payload["scenarios"]["three_weak_spots"]["mean"])),
        ("再补多模态/代码", "非目标也覆盖", fmt_pct(payload["scenarios"]["all_but_non_goals"]["mean"])),
    ]
    estimate_rows = [
        (item["source"], item["what"], f"{item['share']:g}%") for item in payload["external_dependency"]["estimates"]
    ]

    lines = [
        "# 70 条评测 JD 的能力匹配、差距与外部依赖盘点",
        "",
        "复核日期：2026-10-22（Asia/Shanghai）。逐条原文、分类与能力标签见 "
        "[JD_ANALYSIS.md](JD_ANALYSIS.md)、[jd_review.json](../data/manifests/jd_review.json)；"
        "本文的机器可读结果见 [jd_fit.json](../data/manifests/jd_fit.json)；复现命令见第 6 节。",
        "",
        "**范围**：只回答两个问题——当前仓库的能力画像与 70 条 JD 有多重合，以及各外部项目被借鉴了多少。"
        "这是**设计覆盖**，不是录用概率，也不是效果证据；真实 API 与人工金标尚未执行，当前不包含模型微调，"
        "因此“落地效果”证据为 0。",
        "",
        "## 1. 口径",
        "",
        f"70 条 JD 共 {summary['tags']} 个能力标签（多标签，合计大于 70）。给当前仓库的 14 类能力各打一个覆盖等级："
        "1.0 = 本仓库有一等实现；0.5 = 只覆盖一个子场景；0 = 明确非目标。每条 JD 的得分是它全部标签等级的"
        "算术平均，70 条再平均；不按公司、级别或标签数量加权。",
        "",
    ]
    lines += md_table(("能力", "等级", "依据"), level_rows)
    lines += [
        "",
        "benchmark / metric / judge / agent / calibration / diagnosis 六项核心方法学均为 1.0；"
        "差距主要来自岗位广度（多模态/代码）、平台化程度和真实训练闭环。",
        "",
        f"敏感区间为 {fmt_pct(payload['sensitivity']['min'])}–{fmt_pct(payload['sensitivity']['max'])}："
        "把 platform、training、data、safety 四个判断项在严/宽口径间变动（见 jd_fit.json 的 sensitivity）。"
        "“条件覆盖”是剔除 multimodal/code/longctx 后的覆盖，只用于诊断差距是否来自岗位广度，不作为主分数。",
        "",
        "## 2. 结果",
        "",
    ]
    lines += md_table(
        ("口径", "相似度"),
        [
            ("全部 70 条", fmt_pct(summary["mean_all"])),
            ("核心 51 条", fmt_pct(summary["mean_core"])),
            ("相邻 18 条", fmt_pct(summary["mean_adjacent"])),
            ("实习/校招 42 条", fmt_pct(summary["mean_intern_campus"])),
            ("实习/校招中的核心岗", fmt_pct(summary["mean_intern_campus_core"])),
            ("剔除三项非目标（多模态/代码/长上下文）", fmt_pct(summary["mean_conditional_all"])),
            ("核心岗剔除后", fmt_pct(summary["mean_conditional_core"])),
        ],
    )
    lines += ["", "分数分布：", ""]
    lines += md_table(("区间", "条数"), band_rows)
    lines += ["", "累计阈值：", ""]
    lines += md_table(("至少达到", "全部", "核心"), threshold_rows)
    lines += [
        "",
        f"70 条中有 {summary['jds_with_non_goal']} 条至少要求一项本项目明确不做的能力"
        f"（多模态/代码/长上下文）；这是 {fmt_pct(summary['mean_all'])} 最主要的拉低项。",
        "",
        "**最像的岗位**（能力标签几乎都有对应实现）：",
        "",
    ]
    lines += md_table(("JD", "公司", "岗位", "相似度"), top_rows)
    lines += ["", "**最不像的岗位**：", ""]
    lines += md_table(("JD", "公司", "岗位", "相似度"), bottom_rows)
    lines += [
        "",
        "## 3. 差距结构",
        "",
        "| 能力 | JD 频次 | 项目等级 | 损失份额 |",
        "|---|---:|---:|---:|",
    ]
    for capability, frequency, level, lost in loss_rows:
        lines.append(f"| {capability} | {frequency} | {level:g} | {lost} |")
    lines += [
        "",
        f"合计 {summary['tags']} 个标签，覆盖 {summary['tags_covered']:.1f} 个，"
        f"损失 {summary['tags_lost']:.1f} 个（{summary['tags_lost'] / summary['tags'] * 100:.1f}%）。"
        "平台看似只差 0.6，但出现 58 次。训练不在当前实验里。安全只有 RED 一层，不是专项评测。",
        "",
        "补短板的敏感度（每项单独调整等级）：",
        "",
    ]
    lines += md_table(("调整", "含义", "相似度"), scenario_rows)
    lines += [
        "",
        "## 4. 外部依赖盘点",
        "",
        "先给能直接量到的代码事实：",
        "",
        f"- 仓库内 **0 行 vendored 上游源码**：`external/` 被 Git 忽略，τ-bench 以 editable 安装后直接调用；"
        f"当前 tracked external 文件 {code['vendored_files']} 个。",
        f"- `src/retail_eval` 共 {code['src_lines']} 行；直接 import 上游框架的模块为 "
        f"{'、'.join(f'`{name}`' for name in code['upstream_import_files'])}，共 {code['upstream_import_lines']} 行，"
        f"占 {code['upstream_import_share'] * 100:.1f}%；其余 {code['src_lines'] - code['upstream_import_lines']} 行"
        f"（{100 - code['upstream_import_share'] * 100:.1f}%）只依赖标准库/httpx/pydantic。",
        f"- tests 共 {code['tests_lines']} 行。",
        "- `references.lock.yaml` 固定 5 个源码 commit；τ/DeepAgents/GEPA/DSPy 为 MIT；"
        "AWM 锁定树未声明 LICENSE，因此未并入代码。当前锁文件不含 Judge 微调框架。",
        "",
        "运行时职责：",
        "",
    ]
    lines += md_table(
        ("职责", "提供方"),
        [(item["role"], item["provider"]) for item in payload["external_dependency"]["runtime_roles"]],
    )
    lines += [
        "",
        "按“能力份额”归一化的借鉴估值（**作者估计**，单项约 ±3–5pp；不是代码行测量）：",
        "",
    ]
    lines += md_table(("来源", "借了什么 / 复用方式", "占整体"), estimate_rows)
    lines += [
        "",
        "合计：**运行时框架 45%**（τ-bench 26 + DeepAgents 10 + GEPA 9）、**方法/论文 20.5%**、"
        "**仅参照 1%**、**自研 33.5%**；即外部约 66.5%、自研约 33.5%。",
        "",
        f"两个口径不矛盾：按代码行，自研 {100 - code['upstream_import_share'] * 100:.1f}%；按能力份额，自研 33.5%。框架提供可运行骨架，"
        "自研提供评测协议、证据契约、隔离与治理。引用时请同时给出两个口径，避免把“用了框架”说成"
        "“自研框架”，也避免把“代码自己写”说成“能力全部自研”。",
        "",
        "## 5. 使用边界",
        "",
        "- 可以写：“基于 τ-bench v1.0.1 零售环境与 DeepAgents 被测 Agent，用官方终态和盲标区分尺子变化与订单终态，"
        "自研六层 Rubric、证据约束 Judge、任务隔离和模拟题筛选规则。”",
        "- 不要写：“自研 benchmark / 自研 Agent 框架 / 自研优化算法 / 自研评测平台”。",
        "- 不要写：“提升 X%”——真实实验尚未执行；本文只描述设计覆盖。",
        "- 相似度是设计覆盖，不是录用概率；真实 API、人工金标与测试 40 上的 v1/最终版必须另行回填。",
        "",
        "## 6. 复现",
        "",
        "```powershell",
        "& .venv/Scripts/python.exe scripts/analyze_jd_fit.py",
        "```",
        "",
        "脚本只读 `data/manifests/jd_review.json` 与 `src/retail_eval`，不联网、不调用模型；"
        "输出 `data/manifests/jd_fit.json` 与本文，可重复生成。",
        "",
        "## 7. 修订记录",
        "",
        "| 日期 | 变更 |",
        "|---|---|",
        "| 2026-10-22 | 初始：14 类能力覆盖表、70 条 JD 得分、差距与提升场景、外部依赖代码测量与份额估值 |",
        "| 2026-10-23 | 当前实验去掉 Judge 微调：训练等级改为 0，份额表去掉 JudgeLM、LlamaFactory 与 Qwen3-4B |",
        "",
    ]
    return "\n".join(lines) + "\n"


def main():
    payload = build()
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render(payload), encoding="utf-8")
    summary = payload["summary"]
    print(f"70 JD fit: all={summary['mean_all']:.4f} core={summary['mean_core']:.4f} "
          f"ic={summary['mean_intern_campus']:.4f} conditional={summary['mean_conditional_all']:.4f}")
    print(f"wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
