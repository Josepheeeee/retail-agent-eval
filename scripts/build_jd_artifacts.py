"""Build the machine-readable JD source manifest and the 70-row audit table.

Inputs are the frozen research artifacts in runs/20261022-jd-research. The
script never re-fetches pages, so the published manifest stays reproducible.
Run from the repository root:

    python scripts/build_jd_artifacts.py
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "runs/20261022-jd-research"
RAW = ROOT / "docs/JD_RAW.md"

KEYWORDS: dict[str, list[str]] = {}

CAPABILITIES = [
    ("benchmark", "Benchmark/评测集构建", ["benchmark", "基准", "评测集", "题库", "数据集"]),
    ("metric", "指标与评分标准", ["指标", "评分标准", "度量", "rubric", "评分机制"]),
    ("judge", "LLM Judge/自动评分", ["judge", "评分模型", "自动评分", "打分", "评估模型", "llm-as-judge"]),
    ("agent", "Agent/轨迹/多轮评测", ["agent", "智能体", "轨迹", "trajectory", "多轮", "工具调用", "长程"]),
    ("calibration", "校准/统计/一致性", ["校准", "偏差", "一致性", "显著性", "置信", "统计", "kappa", "icc", "bootstrap", "方差"]),
    ("contamination", "污染/泄漏/去重", ["污染", "泄漏", "泄露", "抗污染", "去重"]),
    ("safety", "安全/隐私/对抗", ["安全", "隐私", "对抗", "红队", "越狱", "鲁棒"]),
    ("multimodal", "多模态/语音/视觉", ["多模态", "视觉", "语音", "图像", "视频"]),
    ("longctx", "长上下文/长文本", ["长上下文", "长文本", "long context", "长序列"]),
    ("code", "代码/功能正确性", ["代码", "coding", "humaneval", "mbpp", "编程"]),
    ("data", "数据质量/数据选择/标注", ["数据质量", "数据选择", "数据配比", "标注", "数据评测", "数据构建", "数据清洗"]),
    ("training", "训练-评测闭环/后训练", ["后训练", "预训练", "sft", "rlhf", "微调", "训练策略", "数据配比"]),
    ("platform", "评测平台/工具链", ["平台", "工具链", "框架", "harness", "自动化评测系统", "pipeline"]),
    ("diagnosis", "错误归因/诊断", ["归因", "诊断", "bad case", "badcase", "根因", "缺陷"]),
]

KEYWORDS = {key: words for key, _, words in CAPABILITIES}

# Companies where evaluation is one component rather than the primary duty.
ADJACENT = {
    "JD-06", "JD-09", "JD-14", "JD-15", "JD-18", "JD-24", "JD-31",
    "JD-35", "JD-36", "JD-37", "JD-38", "JD-40", "JD-65", "JD-66",
    "JD-67", "JD-68", "JD-69", "JD-70",
}
UNVERIFIED = {"JD-17"}

# A short, auditable reason for every excluded corpus record or missing company.
COMPANY_NOTES = {
    "字节跳动": ("covered", "1条完整评测JD；视频/图片创作评估方向。", ""),
    "腾讯": ("covered", "6条完整JD；覆盖混元、企微、小程序、语音与具身评测。", ""),
    "阿里巴巴": ("covered", "15条完整JD；含Qwen基础模型、预训练、Agentic、安全与数据评测。", ""),
    "百度": ("covered", "3条完整JD；含智能标注与智能评测。", ""),
    "美团": ("covered", "2条完整JD；基座研究分析与开放域智能体评测。", ""),
    "京东": ("covered", "1条完整JD；具身大模型评测研究。", ""),
    "快手": ("missing", "官方详情返回40404，只取得招聘首页；未取得合格评测JD全文。", "needs_recheck"),
    "网易": ("covered", "2条完整JD；AI应用评测与Agent安全。", ""),
    "蚂蚁集团": ("covered", "20条完整JD；从23条完整正文中排除3条同角色校招/实习重复（见excluded）。", ""),
    "滴滴": ("covered", "1条完整JD；通用Agent评测链路是职责之一。", ""),
    "拼多多": ("missing", "检索到的完整JD为AI Infra，非评测算法；排除。", "verified_exclusion"),
    "小红书": ("covered", "3条完整JD；预训练评估与后训练泛化。", ""),
    "哔哩哔哩": ("missing", "只有LLM算法实习JD，评测工具是附带职责；非评测核心，排除。", "verified_exclusion"),
    "携程": ("missing", "检索无结果；未取得官网评测JD。", "needs_recheck"),
    "米哈游": ("covered", "4条完整JD；从5条中合并1条重复社招角色（9690 -> JD-62）。", ""),
    "360": ("missing", "官网列表未见评测算法岗位；未取得完整JD。", "needs_recheck"),
    "科大讯飞": ("covered", "1条完整JD；AI研究院评测方向。", ""),
    "智谱": ("covered", "1条完整JD；GLM-Code Agent评测。另有截图Agent评测实习，身份未核验，不入主样本。", ""),
    "月之暗面": ("missing", "检索到的Eval岗位为工程/产品方向，非评测算法；排除。", "verified_exclusion"),
    "MiniMax": ("covered", "1条完整JD；大模型算法评测实习。", ""),
    "DeepSeek": ("covered", "1条招聘启事；仅深度学习研究员方向进入分析，未给出独立评测JD细节。", ""),
    "阶跃星辰": ("covered", "1条完整JD；大模型评测算法实习。", ""),
    "百川智能": ("covered", "1条完整JD；通用大模型算法，评测为相邻职责。", ""),
    "零一万物": ("missing", "只取得职位列表，未取得评测JD全文。", "needs_recheck"),
    "商汤": ("covered", "2条完整JD；校招评测与AI PPT评测实习。", ""),
    "华为": ("missing", "只取得校招门户，未取得评测JD全文。", "needs_recheck"),
    "小米": ("covered", "4条完整JD；MiMo后训练Agent、通用算法与具身算法，评测为相邻职责。", ""),
    "蔚来": ("missing", "检索到的JD为AI推理引擎开发，非评测；排除。", "verified_exclusion"),
    "小鹏": ("missing", "检索到的JD为具身智能算法，非评测；排除。", "verified_exclusion"),
    "理想汽车": ("missing", "只取得内推落地页，未取得评测JD全文。", "needs_recheck"),
}

RECHECK = {
    "快手": {
        "date": "2026-10-22",
        "sources": ["https://jy.cumtb.edu.cn/Zhaopin/xiaozhao.html?type=1&id=6761632a-414c-01cd-4588-f1e0ad220942",
                    "https://cug.91wllm.cn/campus/view/id/1005664"],
        "result": "仅检索到校招公告/落地页，仍无官方评测JD完整正文；保留为缺失。"},
    "携程": {
        "date": "2026-10-22",
        "sources": ["https://www.mianshima.com/job/10/MJ036648"],
        "result": "只检索到算法实习（大模型与机器翻译）转载，非评测岗位；仍无合格评测JD。"},
    "360": {
        "date": "2026-10-22",
        "sources": ["https://360campus.zhiye.com/campus/jobs?shareId=92cfb7e8-2ae3-49dc-b960-cf7ce3c1a6c7&shareSource=2",
                    "https://cqut.cqbys.com/attachment/cqut/ueditor/file/20261012/7993_360%e9%9b%86%e5%9b%a22027%e7%a7%8b%e5%ad%a3%e6%a0%a1%e6%8b%9b.pdf"],
        "result": "校招职位页与宣传PDF均未列评测算法岗；仍无合格评测JD。"},
    "零一万物": {
        "date": "2026-10-22",
        "sources": ["https://www.lingyiwanwu.com/careers.html",
                    "https://www.liepin.com/job/1978127835.shtml"],
        "result": "官网只给职位入口；第三方转载为大模型数据科学家，非评测算法；仍无合格评测JD。"},
    "华为": {
        "date": "2026-10-22",
        "sources": ["https://career.huawei.com/reccampportal/portal5/campus-recruitment-detail.html?jobId=30858&dataSource=1&jobType=1&recruitType=CR&sourceType=001"],
        "result": "检索到端侧大模型岗位，非评测算法；仍无合格评测JD。"},
    "理想汽车": {
        "date": "2026-10-22",
        "sources": ["https://li.jobs.feishu.cn/referral/campus/position"],
        "result": "只取得内推职位列表入口，无公开评测JD正文；保留为缺失。"},
}

EXCLUDED = {
    "蚂蚁集团-260826011707588": ("【蚂蚁星】多模态理解与生成评测算法研究-27届", "与JD-53同一角色的校招版本重复，合并到JD-53。"),
    "蚂蚁集团-26032609330453": ("【蚂蚁星】AI工程师-大模型评测（实习）", "与JD-57同一角色的实习版本重复，合并到JD-57。"),
    "蚂蚁集团-26051209984609": ("【蚂蚁星】算法工程师-评测方向-大安全-27届", "与JD-60同一角色的校招版本重复，合并到JD-60。"),
    "米哈游-9690": ("LLM Evaluation算法研究员", "与JD-62同一角色的社招版本重复，合并到JD-62。"),
}
EXTRA_EXCLUDED = [
    {"company": "阿里巴巴", "ref": "199909720005", "title": "大模型评测实习生（通用方向）",
     "reason": "取得完整正文但算法属性待核验；未进入70条主样本。"},
    {"company": "月之暗面", "ref": "careers.kimi.com", "title": "Eval岗位",
     "reason": "职责为工程/产品方向，非评测算法研究。"},
    {"company": "用户截图", "ref": "SC-01/SC-02/SC-03/SC-04/SC-05-10/SC-06-07/SC-08/SC-09/SC-11",
     "title": "截图补充材料", "reason": "单独标注来源与截断，不并入官网完整样本统计。"},
]


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()


def parse_raw(text: str):
    headings = {}
    pattern = re.compile(r"^### (JD-\d+) · ([^·]+) · (.+)$", re.M)
    for match in pattern.finditer(text):
        jd, company, title = match.groups()
        tail = text[match.end():match.end() + 800]
        sha = re.search(r"正文SHA-256：`([0-9a-f]{64})`", tail)
        headings[jd] = {"company": company.strip(), "title": title.strip(), "body_sha256": sha.group(1) if sha else None}
    return headings


def first_url(text: str):
    match = re.search(r"https?://[^\s\)\]，]+", text)
    return match.group(0).rstrip("。，;；") if match else None


def sentence_evidence(body: str, tags: list[str], limit=110):
    normalized = re.sub(r"\s+", " ", body)
    pieces = re.split(r"(?<=[。；;！!？?])", normalized)
    keywords = {kw.lower() for tag in tags for kw in dict(KEYWORDS)[tag]}
    for piece in pieces:
        if any(kw in piece.lower() for kw in keywords):
            return piece.strip()[:limit]
    return normalized[:limit]


def normalize_level(value) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("parent", {}).get("name") or value.get("name") or "校招/正式"
    return "校招/正式"


def route_for(tags: list[str], category: str) -> str:
    if category == "unverified":
        return "no direct project claim; monitor only"
    parts = []
    if {"agent", "judge", "diagnosis"} & set(tags):
        parts.append("retail: trajectory judge/diagnosis")
    if {"benchmark", "metric", "calibration", "contamination"} & set(tags):
        parts.append("foundation: task/metric protocol")
    if "data" in tags or "training" in tags:
        parts.append("foundation: diagnostic selection/SFT")
    if "code" in tags:
        parts.append("foundation: HumanEval+")
    if "longctx" in tags:
        parts.append("foundation: RULER")
    if "multimodal" in tags:
        parts.append("multimodal: not claimed")
    if "safety" in tags:
        parts.append("retail: RED layer")
    return "; ".join(dict.fromkeys(parts)) or "no direct claim"


def validation_for(tags: list[str], category: str) -> str:
    if category == "unverified":
        return "not-claimed"
    if set(tags) <= {"multimodal", "platform"}:
        return "not-claimed"
    if category == "adjacent":
        return "protocol-only"
    return "offline-tested"


def gap_for(tags: list[str], category: str) -> str:
    if category == "unverified":
        return "algorithm attribute unverified"
    if "multimodal" in tags:
        return "multimodal not implemented; real run pending"
    if "safety" in tags:
        return "not a security benchmark; real run pending"
    return "real model run pending"


def level_kind(level: str):
    if "实习" in level:
        return "intern"
    if any(k in level for k in ("校招", "应届", "27届", "毕业")):
        return "campus"
    return "social"


def main():
    corpus = json.loads((RUN / "corpus.json").read_text(encoding="utf-8"))
    searches = json.loads((RUN / "company_searches.json").read_text(encoding="utf-8"))
    catalog = json.loads((RUN / "catalog.json").read_text(encoding="utf-8"))
    entries = json.loads((RUN / "entries.json").read_text(encoding="utf-8"))
    checks = json.loads((RUN / "company_checks.json").read_text(encoding="utf-8"))
    raw_text = RAW.read_text(encoding="utf-8")
    jd_meta = parse_raw(raw_text)
    by_sha = {rec["body_sha256"]: rec for rec in corpus}
    jd_records = []
    for jd, meta in sorted(jd_meta.items()):
        rec = by_sha.get(meta["body_sha256"])
        if rec is None:
            raise SystemExit(f"{jd}: body hash not found in corpus")
        tags = [key for key, _, words in CAPABILITIES if any(word in rec["body"].lower() for word in words)]
        category = "core" if jd not in ADJACENT and jd not in UNVERIFIED else ("unverified" if jd in UNVERIFIED else "adjacent")
        level_text = normalize_level(rec["recruitment_level"])
        jd_records.append({
            "jd_id": jd,
            "company": rec["company"],
            "title": rec["title"],
            "recruitment_level": level_text,
            "level_kind": level_kind(level_text),
            "record_id": rec["record_id"],
            "source_url": rec["source_url"],
            "body_sha256": rec["body_sha256"],
            "retrieved_at": rec["retrieved_at"],
            "category": category,
            "capabilities": tags,
            "evidence": sentence_evidence(rec["body"], tags),
            "project_route": route_for(tags, category),
            "validation": validation_for(tags, category),
            "gap": gap_for(tags, category),
        })

    selected_by_company = Counter(r["company"] for r in jd_records)
    search_by_company = {s["company"]: s for s in searches}
    catalog_by_company = {c["company"]: c["entry"] for c in catalog}
    entry_by_company = {e["company"]: e for e in entries}
    companies = []
    for company in catalog_by_company:
        status, note, recheck = COMPANY_NOTES[company]
        search = search_by_company.get(company, {})
        entry = entry_by_company.get(company, {})
        evidence = entry.get("evidence", {})
        companies.append({
            "company": company,
            "portal": catalog_by_company[company],
            "search_query": search.get("query"),
            "search_domains": search.get("domains", []),
            "search_first_url": first_url(search.get("result", "")),
            "search_result_chars": len(search.get("result", "")),
            "portal_http_status": evidence.get("status_code"),
            "portal_snapshot": evidence.get("snapshot"),
            "portal_sha256": evidence.get("sha256"),
            "coverage": status,
            "complete_official_records": selected_by_company.get(company, 0),
            "selected_jd_ids": [r["jd_id"] for r in jd_records if r["company"] == company],
            "notes": note,
            "recheck": recheck,
            "recheck_sources": RECHECK.get(company, {}).get("sources", []),
            "recheck_result": RECHECK.get(company, {}).get("result", "no recheck needed; historical evidence complete"),
            "checked_at": "2026-10-22",
        })

    exclusions = []
    for record_id, (title, reason) in EXCLUDED.items():
        rec = next((r for r in corpus if r["record_id"] == record_id), None)
        exclusions.append({"record_id": record_id, "company": record_id.split("-")[0],
                           "title": title, "reason": reason,
                           "body_sha256": rec["body_sha256"] if rec else None})
    exclusions.extend(EXTRA_EXCLUDED)

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "companies_checked": len(companies),
            "official_records_retrieved": len(corpus),
            "official_complete_jds_selected": len(jd_records),
            "companies_with_selected_jd": len(selected_by_company),
            "companies_without_selected_jd": len(companies) - len(selected_by_company),
            "screenshots": 11,
            "statement": "70条去重官网完整正文，来自19家公司；不声称穷尽30家公司的全部职位。",
        },
        "method": {
            "selection": "核心职责包含模型能力/指标定义、Benchmark、评分算法、偏差校准、受控实验或评测指导训练。",
            "inclusion": "标题含算法也可能排除；标题为工程师但明确研发评测方法可纳入；混合岗位只分析算法研究部分。",
            "exclusion": "纯Infra、产品、运营、人工测评执行与测试执行不进入主分析。",
            "dedup_keys": ["company + official job id", "body_sha256", "same-role campus/social merge"],
            "query_template": "{company} 大模型 评测 算法 研究 实习 校招 社招",
            "retrieval_window": "2026-10-22",
        },
        "dedup": {
            "input_records": len(corpus),
            "selected_records": len(jd_records),
            "removed_records": len(corpus) - len(jd_records),
            "duplicate_urls": len(corpus) - len({r["source_url"] for r in corpus}),
            "duplicate_body_hashes": len(corpus) - len({r["body_sha256"] for r in corpus}),
            "merged_same_role": [
                "蚂蚁集团-260826011707588 -> JD-53",
                "蚂蚁集团-26032609330453 -> JD-57",
                "蚂蚁集团-26051209984609 -> JD-60",
                "米哈游-9690 -> JD-62",
            ],
            "excluded_records": [row for row in exclusions if "record_id" in row],
            "other_excluded_candidates": [row for row in exclusions if "record_id" not in row],
        },
        "companies": companies,
        "missing_or_excluded_companies": [c["company"] for c in companies if c["coverage"] != "covered"],
        "provenance": {
            "raw_document": "docs/JD_RAW.md",
            "raw_sha256": hashlib.sha256(raw_text.replace("\r\n", "\n").encode("utf-8")).hexdigest(),
            "corpus_sha256": hashlib.sha256((RUN / "corpus.json").read_bytes()).hexdigest(),
            "research_run": "runs/20261022-jd-research",
            "generator": "scripts/build_jd_artifacts.py",
            "note": "runs/ is git-ignored; the manifest records hashes and URLs so JD_RAW.md remains the distributable source.",
        },
    }
    out = ROOT / "data/manifests/jd_sources.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    review = {"schema_version": 1, "generated_at": manifest["generated_at"],
              "records": jd_records, "excluded": exclusions}
    (ROOT / "data/manifests/jd_review.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Aggregate capability statistics, prioritizing intern/campus samples.
    stats = {}
    for key, label, _ in CAPABILITIES:
        rows = [r for r in jd_records if key in r["capabilities"]]
        stats[key] = {
            "label": label,
            "all": len(rows),
            "intern_campus": sum(r["level_kind"] in {"intern", "campus"} for r in rows),
            "core": sum(r["category"] == "core" for r in rows),
            "jd_ids": [r["jd_id"] for r in rows],
        }
    summary = {
        "category_counts": dict(Counter(r["category"] for r in jd_records)),
        "level_counts": dict(Counter(r["level_kind"] for r in jd_records)),
        "company_counts": dict(selected_by_company),
        "capability_stats": stats,
    }
    (ROOT / "data/manifests/jd_capability_stats.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    write_analysis(manifest, review, summary)
    print(f"wrote {out} ({len(companies)} companies, {len(jd_records)} JDs)")
    print(json.dumps(summary["category_counts"], ensure_ascii=False), summary["level_counts"])


def write_analysis(manifest, review, summary):
    records = review["records"]
    level = Counter(r["level_kind"] for r in records)
    category = Counter(r["category"] for r in records)
    lines = [
        "# 70 条评测算法岗位：原文证据、项目落点与剩余缺口",
        "",
        "复核日期：2026-10-22（Asia/Shanghai）。原文见 [JD_RAW.md](JD_RAW.md)；机器可读来源、30 家公司覆盖与排除记录见 "
        "[jd_sources.json](../data/manifests/jd_sources.json)；逐条分类与能力标签见 "
        "[jd_review.json](../data/manifests/jd_review.json)。",
        "",
        "**范围**：70 条去重官网完整正文，来自 19 家公司；另登记 11 家未取得合格评测 JD 的公司。"
        "本文件不把招聘启事当作能力证明，也不把项目实现写成已有效果。",
        "",
        "## 1. 复核口径",
        "",
        "- **核心评测（core）**：岗位主职责就是评测体系、Benchmark、指标、评分/裁判、诊断或评测驱动的数据闭环。",
        "- **相邻研究（adjacent）**：评测是重要组成，但岗位同时以数据、训练、安全或具身算法为主；只把评测部分纳入映射。",
        "- **待核验（unverified）**：取得完整正文，但不能仅凭正文确认独立评测职责或算法属性。",
        "- **排除项**：完整正文已取得但属于重复角色、非评测方向或截图身份不明；不计入 70 条主样本。",
        "",
        "分类计数："
        f"核心 {category['core']} 条，相邻 {category['adjacent']} 条，待核验 {category['unverified']} 条；"
        f"实习 {level['intern']} 条，校招 {level['campus']} 条，社招 {level['social']} 条。"
        "能力统计优先看实习/校招样本，社招用于补充方法边界。",
        "",
        "## 2. 能力统计（实习/校招优先）",
        "",
        "| 能力 | 全部 | 实习/校招 | 核心岗位 | 对应项目 |",
        "|---|---:|---:|---:|---|",
    ]
    route = {
        "benchmark": "foundation: 任务清单/样本级评测；retail: 固定任务与划分",
        "metric": "foundation: 分任务原生指标；retail: 官方 reward 与分层 Grade",
        "judge": "retail: 轨迹 Judge + 人工校准；foundation: 仅辅助错误分析",
        "agent": "retail: τ/DeepAgents 轨迹与失败定位",
        "calibration": "retail: 置信度/ECE/人工金标；foundation: Bootstrap/种子方差",
        "contamination": "foundation: 精确/近重复与同源分组",
        "safety": "retail: RED 层与隐私违规；foundation: 安全检查（不作为主终点）",
        "multimodal": "不声称覆盖；仅作为相邻岗位背景",
        "longctx": "foundation: RULER 4K/8K/16K 固定诊断",
        "code": "foundation: HumanEval+ 受限执行",
        "data": "foundation: 错误诊断加权选样；retail: 盲标与 SFT 导出",
        "training": "foundation: B0/B1/B2 LoRA 对照；retail: Judge SFT",
        "platform": "两项目均只做薄 Harness，不建平台",
        "diagnosis": "retail: 最早错误事件/证据支持；foundation: 训练集错误诊断",
    }
    for key, values in summary["capability_stats"].items():
        lines.append(f"| {values['label']} | {values['all']} | {values['intern_campus']} | {values['core']} | {route[key]} |")
    lines += [
        "",
        "读法：`全部` 是该能力在 70 条中出现的次数，不是岗位数；`实习/校招` 是其中实习或校招岗位的出现次数。"
        "多标签合计大于 70。",
        "",
        "## 3. 岗位要求 → 原文证据 → 项目实现 → 验证结果 → 剩余缺口",
        "",
        "| 岗位要求（合并同类） | 原文证据（代表性 JD） | 项目实现 | 验证结果 | 剩余缺口 |",
        "|---|---|---|---|---|",
        "| 定义能力维度与可比较指标，拒绝单一总分 | JD-21、JD-46、JD-51 要求多维能力、指标与评测体系 | retail 六层 Grade 与官方 reward 分开；foundation 分任务原生指标，不合成总分 | 两项目离线契约/测试；真实模型结果待执行 | 维度权重与业务效用仍需真实数据验证 |",
        "| 构建/维护 Benchmark 与评测集 | JD-01、JD-08、JD-13、JD-28 | retail 固定 τ 114 任务 54/20/40；foundation GSM8K/SVAMP/MMLU-Pro/BBH/IFEval/HumanEval+/RULER | 划分与数据清单已生成并测试；上游样本未全量下载 | 真实数据版本、许可与污染证据需在 H20 记录 |",
        "| LLM-as-Judge、自动评分与人工校准 | JD-09、JD-20、JD-45、JD-54 | retail 证据约束 Judge、J0–J4、盲标/复核；foundation 只用 Judge 做辅助错误分析 | 契约、覆盖率、校准与定位指标已实现；无人工金标结果 | 需 480 条人工标注与 Judge SFT 真实运行 |",
        "| Agent/轨迹/多轮/长程评测 | JD-02、JD-16、JD-24、JD-49、JD-54 | retail τ 轨迹、工具调用、状态重置、最早错误事件；foundation 不把 Agent 评测混入基座主终点 | τ 真实工具往返与脚本模型集成检查通过 | 真实 API 轨迹与修复案例待执行 |",
        "| 错误归因、诊断与评测驱动数据闭环 | JD-01、JD-16、JD-28、JD-51、JD-59 | retail 分层反馈、cause、error_type、earliest_error_event；foundation 训练池错误诊断加权 B2 | 消融入口与选样逻辑已测试；无真实增益 | A3−A2、B2−B1 的真实差值与 CI 未产生 |",
        "| 统计校准、一致性与不确定性 | JD-41、JD-46、JD-51、JD-62 | 任务/种子配对 Bootstrap、ECE/Brier、人工一致性、种子方差 | 统计入口与缺失拒绝已有测试 | 真实重复标注与正式 test 未运行 |",
        "| 污染、泄漏与数据隔离 | JD-13、JD-28、JD-38 | retail 同源分组与 test 禁入；foundation 精确/近重复、同源分组、few-shot 检查 | 隔离与导出拒绝测试通过 | 只能检查本项目可见数据，不能证明预训练语料无污染 |",
        "| 安全/隐私/对抗评测 | JD-24、JD-32、JD-33、JD-35、JD-37、JD-40、JD-60 | retail RED 并行层与隐私违规；foundation 仅作辅助检查 | 隐私并行判定与证据校验通过 | 不是安全专项 benchmark，不声称覆盖对抗评测 |",
        "| 多模态/语音/视觉评测 | JD-05、JD-09、JD-36、JD-42、JD-50、JD-53、JD-57 | 不在两项目主终点；仅保留为岗位背景 | 未实现 | 明确的非目标，不用文本项目冒充多模态能力 |",
        "| 长上下文评测 | JD-13、JD-28、JD-38 | foundation RULER 4K/8K/16K 固定种子诊断 | 生成器与评分入口离线测试 | 需在 H20 用目标 tokenizer 生成并跑真实模型 |",
        "| 代码功能正确性 | JD-13、JD-20、JD-34 | foundation HumanEval+ 受限容器执行 | 解析/执行契约测试；容器脚本待 H20 验证 | 需 Docker/Apptainer 与真实模型生成 |",
        "| 训练-评测闭环与后训练数据选择 | JD-14、JD-29、JD-38、JD-45、JD-51、JD-58、JD-67 | foundation B0/B1/B2、GSM8K dev500、长度分层、错误加权、LlamaFactory 配置；retail Judge SFT | 选样/预算匹配/配置导出已测试；无训练结果 | 真实 4 卡 LoRA 与三次种子训练待执行 |",
        "| 评测平台/工具链工程 | JD-02、JD-03、JD-13、JD-28、JD-39、JD-46 | 两项目薄 Harness：版本、清单、原始输出、报告；不建 Web 平台 | 离线闭环与产物审计已测试 | 不声称平台化、调度或可视化产品能力 |",
        "",
        "## 4. 逐条复核（70 条）",
        "",
        "| JD | 公司 | 岗位（截断） | 层级 | 分类 | 能力标签 | 原文证据（截断） | 项目落点 | 验证 | 缺口 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    level_label = {"intern": "实习", "campus": "校招", "social": "社招"}
    for r in records:
        title = r["title"].replace("|", "/")
        if len(title) > 34:
            title = title[:34] + "…"
        evidence = r["evidence"].replace("|", "/").replace("\n", " ")
        if len(evidence) > 58:
            evidence = evidence[:58] + "…"
        tags = ",".join(r["capabilities"][:5]) or "—"
        lines.append(
            f"| {r['jd_id']} | {r['company']} | {title} | {level_label[r['level_kind']]} | "
            f"{ {'core': '核心', 'adjacent': '相邻', 'unverified': '待核验'}[r['category']] } | {tags} | "
            f"{evidence} | {r['project_route']} | {r['validation']} | {r['gap']} |")
    lines += [
        "",
        "## 5. 排除项与缺失（不进入 70 条主样本）",
        "",
        "| 对象 | 标题 | 原因 |",
        "|---|---|---|",
    ]
    for item in review["excluded"]:
        title = item.get("title", "").replace("|", "/")
        reason = item.get("reason", "").replace("|", "/")
        lines.append(f"| {item.get('company', '')} / {item.get('record_id', item.get('ref', ''))} | {title} | {reason} |")
    lines += [
        "",
        "另有 11 家公司未取得合格评测 JD："
        + "、".join(manifest["missing_or_excluded_companies"])
        + "。其中快手、携程、360、零一万物、华为、理想汽车属于检索/动态站点未取得完整正文；"
        "拼多多、哔哩哔哩、月之暗面、蔚来、小鹏属于已取得正文但职责不是评测算法。"
        "“没有取得合格全文”不等于“该公司没有相关岗位”。"
        "快手、携程、360、零一万物、华为、理想汽车六家已在 2026-10-22 重新检索，仍未取得合格评测 JD；"
        "重检 URL 与结论记录在 jd_sources.json 各公司条目中。",
        "",
        "## 6. 两个项目的分别映射",
        "",
        "| 项目 | 主要对应能力 | 主要 JD | 不声称 |",
        "|---|---|---|---|",
        "| retail-agent-eval | 轨迹 Judge、证据定位、人工校准、失败归因驱动提示优化 | JD-02、JD-10、JD-16、JD-21、JD-28、JD-49、JD-51、JD-54 | 不声称六层划分最优、不声称已完成因果根因分析 |",
        "| foundation-model-eval | 基座能力测量、污染检查、错误诊断、等预算数据选择、训练前后比较 | JD-13、JD-15、JD-27、JD-29、JD-38、JD-45、JD-51、JD-58 | 不声称完成预训练研究、不合成无依据总分 |",
        "",
        "## 7. 复核结论",
        "",
        f"- 70 条中有 {category['core']} 条以评测为主职责，{category['adjacent']} 条为相邻研究，"
        f"{category['unverified']} 条待核验；实习/校招样本 {level['intern'] + level['campus']} 条，社招 {level['social']} 条。",
        "- 最高频能力是 Benchmark/评测集、指标、LLM Judge、Agent 轨迹与训练-评测闭环；两项目分别覆盖轨迹侧和基座侧。",
        "- 明确不覆盖：多模态/语音/视觉专项、生产评测平台、对抗安全 benchmark、预训练本身。",
        "- 所有“验证”列只描述离线工程检查；真实模型、训练和人工标注结果必须由 H20 运行后回填，不能用本文替代。",
        "",
        "## 8. 修订记录",
        "",
        "| 日期 | 变更 | 影响 |",
        "|---|---|---|",
        "| 2026-10-22 | 建立70条官网完整正文档案、正文SHA-256与来源URL | 初始归档；19家公司 |",
        "| 2026-10-22 | 补30家公司检索覆盖、4条同角色去重、11家缺失/排除记录 | 新增jd_sources.json；不改变正文 |",
        "| 2026-10-22 | 对快手/携程/360/零一万物/华为/理想汽车重新检索 | 仍无合格评测JD，记录重检URL与结论 |",
        "| 2026-10-22 | 增加核心/相邻/待核验分类、能力标签和项目映射 | 新增jd_review.json、jd_capability_stats.json、本文件 |",
        "",
        "正文修改必须保留旧正文哈希、来源与原因；本档案只做追加式修订，不静默覆盖原文。",
        "",
    ]
    (ROOT / "docs/JD_ANALYSIS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
