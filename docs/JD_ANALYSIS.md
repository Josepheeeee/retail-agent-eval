# 70 条评测算法岗位：原文证据、项目落点与剩余缺口

复核日期：2026-10-22（Asia/Shanghai）。原文见 [JD_RAW.md](JD_RAW.md)；机器可读来源、30 家公司覆盖与排除记录见 [jd_sources.json](../data/manifests/jd_sources.json)；逐条分类与能力标签见 [jd_review.json](../data/manifests/jd_review.json)。

**范围**：70 条去重官网完整正文，来自 19 家公司；另登记 11 家未取得合格评测 JD 的公司。本文件不把招聘启事当作能力证明，也不把项目实现写成已有效果。

## 1. 复核口径

- **核心评测（core）**：岗位主职责就是评测体系、Benchmark、指标、评分/裁判、诊断或评测驱动的数据闭环。
- **相邻研究（adjacent）**：评测是重要组成，但岗位同时以数据、训练、安全或具身算法为主；只把评测部分纳入映射。
- **待核验（unverified）**：取得完整正文，但不能仅凭正文确认独立评测职责或算法属性。
- **排除项**：完整正文已取得但属于重复角色、非评测方向或截图身份不明；不计入 70 条主样本。

分类计数：核心 51 条，相邻 18 条，待核验 1 条；实习 28 条，校招 14 条，社招 28 条。能力统计优先看实习/校招样本，社招用于补充方法边界。

## 2. 能力统计（实习/校招优先）

| 能力 | 全部 | 实习/校招 | 核心岗位 | 对应项目 |
|---|---:|---:|---:|---|
| Benchmark/评测集构建 | 56 | 33 | 44 | foundation: 任务清单/样本级评测；retail: 固定任务与划分 |
| 指标与评分标准 | 39 | 17 | 31 | foundation: 分任务原生指标；retail: 官方 reward 与分层 Grade |
| LLM Judge/自动评分 | 27 | 15 | 24 | retail: 轨迹 Judge + 人工校准；foundation: 仅辅助错误分析 |
| Agent/轨迹/多轮评测 | 49 | 27 | 36 | retail: τ/DeepAgents 轨迹与失败定位 |
| 校准/统计/一致性 | 32 | 17 | 23 | retail: 置信度/ECE/人工金标；foundation: Bootstrap/种子方差 |
| 污染/泄漏/去重 | 8 | 4 | 6 | foundation: 精确/近重复与同源分组 |
| 安全/隐私/对抗 | 30 | 17 | 22 | retail: RED 层与隐私违规；foundation: 安全检查（不作为主终点） |
| 多模态/语音/视觉 | 37 | 21 | 23 | 不声称覆盖；仅作为相邻岗位背景 |
| 长上下文/长文本 | 7 | 5 | 5 | foundation: RULER 4K/8K/16K 固定诊断 |
| 代码/功能正确性 | 45 | 28 | 32 | foundation: HumanEval+ 受限执行 |
| 数据质量/数据选择/标注 | 29 | 17 | 19 | foundation: 错误诊断加权选样；retail: 盲标导入导出，当前不导出微调数据 |
| 训练-评测闭环/后训练 | 42 | 25 | 30 | foundation: B0/B1/B2 LoRA 对照；retail: 当前不包含模型微调 |
| 评测平台/工具链 | 58 | 35 | 41 | 两项目均只做薄 Harness，不建平台 |
| 错误归因/诊断 | 27 | 11 | 23 | retail: 最早错误事件/证据支持；foundation: 训练集错误诊断 |

读法：`全部` 是该能力在 70 条中出现的次数，不是岗位数；`实习/校招` 是其中实习或校招岗位的出现次数。多标签合计大于 70。

## 3. 岗位要求 → 原文证据 → 项目实现 → 验证结果 → 剩余缺口

| 岗位要求（合并同类） | 原文证据（代表性 JD） | 项目实现 | 验证结果 | 剩余缺口 |
|---|---|---|---|---|
| 定义能力维度与可比较指标，拒绝单一总分 | JD-21、JD-46、JD-51 要求多维能力、指标与评测体系 | retail 六层 Grade 与官方 reward 分开；foundation 分任务原生指标，不合成总分 | 两项目离线契约/测试；真实模型结果待执行 | 维度权重与业务效用仍需真实数据验证 |
| 构建/维护 Benchmark 与评测集 | JD-01、JD-08、JD-13、JD-28 | retail 固定 τ 114 任务 54/20/40；foundation GSM8K/SVAMP/MMLU-Pro/BBH/IFEval/HumanEval+/RULER | 划分与数据清单已生成并测试；上游样本未全量下载 | 真实数据版本、许可与污染证据需在 H20 记录 |
| LLM-as-Judge、自动评分与人工校准 | JD-09、JD-20、JD-45、JD-54 | retail 证据约束的固定 Judge、盲标/复核；foundation 只用 Judge 做辅助错误分析 | 契约、覆盖率、校准与定位指标已实现；无人工金标结果 | 需 480 条人工标注；当前不训练 Judge |
| Agent/轨迹/多轮/长程评测 | JD-02、JD-16、JD-24、JD-49、JD-54 | retail τ 轨迹、工具调用、状态重置、最早错误事件；foundation 不把 Agent 评测混入基座主终点 | τ 真实工具往返与脚本模型集成检查通过 | 真实 API 轨迹与修复案例待执行 |
| 错误归因、诊断与评测驱动数据闭环 | JD-01、JD-16、JD-28、JD-51、JD-59 | retail 分层反馈、cause、error_type、earliest_error_event；foundation 训练池错误诊断加权 B2 | 消融入口与选样逻辑已测试；无真实增益 | A3−A2、B2−B1 的真实差值与 CI 未产生 |
| 统计校准、一致性与不确定性 | JD-41、JD-46、JD-51、JD-62 | 任务/种子配对 Bootstrap、ECE/Brier、人工一致性、种子方差 | 统计入口与缺失拒绝已有测试 | 真实重复标注与正式 test 未运行 |
| 污染、泄漏与数据隔离 | JD-13、JD-28、JD-38 | retail 同源分组与 test 禁入；foundation 精确/近重复、同源分组、few-shot 检查 | 隔离与导出拒绝测试通过 | 只能检查本项目可见数据，不能证明预训练语料无污染 |
| 安全/隐私/对抗评测 | JD-24、JD-32、JD-33、JD-35、JD-37、JD-40、JD-60 | retail RED 并行层与隐私违规；foundation 仅作辅助检查 | 隐私并行判定与证据校验通过 | 不是安全专项 benchmark，不声称覆盖对抗评测 |
| 多模态/语音/视觉评测 | JD-05、JD-09、JD-36、JD-42、JD-50、JD-53、JD-57 | 不在两项目主终点；仅保留为岗位背景 | 未实现 | 明确的非目标，不用文本项目冒充多模态能力 |
| 长上下文评测 | JD-13、JD-28、JD-38 | foundation RULER 4K/8K/16K 固定种子诊断 | 生成器与评分入口离线测试 | 需在 H20 用目标 tokenizer 生成并跑真实模型 |
| 代码功能正确性 | JD-13、JD-20、JD-34 | foundation HumanEval+ 受限容器执行 | 解析/执行契约测试；容器脚本待 H20 验证 | 需 Docker/Apptainer 与真实模型生成 |
| 训练-评测闭环与后训练数据选择 | JD-14、JD-29、JD-38、JD-45、JD-51、JD-58、JD-67 | foundation B0/B1/B2、GSM8K dev500、长度分层、错误加权；retail 当前不包含模型微调 | 零售侧已去掉微调入口 | 零售当前实验不把微调当步骤 |
| 评测平台/工具链工程 | JD-02、JD-03、JD-13、JD-28、JD-39、JD-46 | 两项目薄 Harness：版本、清单、原始输出、报告；不建 Web 平台 | 离线闭环与产物审计已测试 | 不声称平台化、调度或可视化产品能力 |

## 4. 逐条复核（70 条）

| JD | 公司 | 岗位（截断） | 层级 | 分类 | 能力标签 | 原文证据（截断） | 项目落点 | 验证 | 缺口 |
|---|---|---|---|---|---|---|---|---|---|
| JD-01 | 腾讯 | 混元大模型评测算法研究员（北京） | 社招 | 核心 | benchmark,metric,multimodal,platform,diagnosis | 岗位职责 1.负责通用AI大模型相关的评测与应用的规划、落地以及平台化能力建设，包括但不限于：； | retail: trajectory judge/diagnosis; foundation: task/metric protocol; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-02 | 腾讯 | 微信小程序-大模型评测工程师-智能体方向 | 社招 | 核心 | benchmark,metric,judge,agent,calibration | 岗位职责 1.设计微信小程序智能体（Agent）的质量评测方法学，建立可量化、可追踪的评测指标体系； | retail: trajectory judge/diagnosis; foundation: task/metric protocol | offline-tested | real model run pending |
| JD-03 | 腾讯 | 企业微信-评测算法工程师-（北京/成都） | 社招 | 核心 | benchmark,multimodal,diagnosis | 岗位职责 1.针对企业微信AI模型的特点，持续构建完善的评测基准，包括但不限于NLP、ASR、MLLM等领域，有效指… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-04 | 腾讯 | 企业微信协作工具-评测算法工程师 | 社招 | 核心 | benchmark,multimodal,diagnosis | 岗位职责 1.针对文档/微盘/邮箱等应用需求AI模型的特点，持续构建完善的评测基准，包括但不限于NLP、ASR、ML… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-05 | 腾讯 | 混元语音大模型agentic评测（北京/上海） | 社招 | 核心 | benchmark,agent,calibration,contamination,multimodal | 岗位职责 1.主导 Agent 方向评测体系整体设计与落地实施，完成模型能力定义，搭建面向复杂智能体场景的评测任务体… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-06 | 腾讯 | 具身大模型评测与数据工程师 | 社招 | 相邻 | benchmark,metric,judge,calibration,multimodal | 岗位职责 1.评测体系搭建：构建覆盖感知、推理、操作、长时程任务的多层级仿真与真机评测体系，制定评测指标体系，主导自… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; multimodal: not claimed | protocol-only | multimodal not implemented; real run pending |
| JD-07 | 字节跳动 | 大模型算法工程师（视频/图片创作-评估方向）-剪映CapCut（北京… | 社招 | 核心 | benchmark,metric,judge,agent,safety | 职位描述 1、负责视频/图片创作Agent的核心研发与应用，聚焦自动化评测能力建设，应用Prompt Enginee… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed; retail: RED layer | offline-tested | multimodal not implemented; real run pending |
| JD-08 | 百度 | 大模型评测算法工程师（J100902） | 社招 | 核心 | benchmark,metric,judge,agent,calibration | 工作职责： -负责医疗健康场景下 LLM / VLM / Agent 等模型评测体系建设，设计数据驱动、可复现、可扩… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-09 | 百度 | 大模型智能标注与智能评测算法工程师（全模态方向）（J105943） | 社招 | 相邻 | benchmark,metric,judge,agent,calibration | 工作职责： -负责面向文本、图片、音频、视频及多轮交互的智能标注与智能评测平台建设 -建设全模态数据生产链路，包括数… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; multimodal: not claimed; retail: RED layer | protocol-only | multimodal not implemented; real run pending |
| JD-10 | 百度 | 大模型智能标注与评测算法工程师（J105767） | 社招 | 核心 | benchmark,metric,judge,agent,calibration | 工作职责： -负责大模型智能标注与智能评测平台的整体设计、研发和业务落地 -建设自动标注、弱监督标注、模型协同标注、… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT | offline-tested | real model run pending |
| JD-11 | MiniMax | 大模型算法评测实习生 | 实习 | 核心 | benchmark,multimodal,code,platform | 2.深入理解大规模语言模型/多模态模型，参与自动化评测框架的开发、评测方案的制定与评测数据集的建设。 | foundation: task/metric protocol; foundation: HumanEval+; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-12 | 小红书 | Dots-预训练评估策略 | 社招 | 核心 | metric,calibration,code,data,training | 工作职责 1、预训练评估体系建设：设计覆盖语言理解、知识、推理、代码、数学等多维能力的预训练阶段评估体系（Eval … | foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+ | offline-tested | real model run pending |
| JD-13 | 小红书 | 【Ace顶尖实习生】Dots-大模型评测算法研究员 | 实习 | 核心 | benchmark,judge,agent,calibration,contamination | 工作职责 1、设计并迭代 dots 模型的多维度能力评测体系，覆盖通用能力（推理、数学、代码、语言理解）、指令遵循、… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; foundation: RULER; multimodal: not claimed; retail: RED layer | offline-tested | multimodal not implemented; real run pending |
| JD-14 | 小红书 | 【Ace顶尖实习生】大模型后训练泛化性研究 | 实习 | 相邻 | calibration,multimodal,code,training | 工作职责 本课题聚焦小红书通用基座模型在真实业务 OOD 场景下的泛化性问题，围绕三个方向展开： 1）研究如何在训练… | foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed | protocol-only | multimodal not implemented; real run pending |
| JD-15 | 美团 | 基座大模型研究分析实习生 | 实习 | 相邻 | calibration,safety,multimodal,code,training | 部门介绍 基础研发平台是美团的核心技术平台，立足于“零售+科技”的战略定位，通过打造人工智能、大数据、云计算、安全等… | foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed; retail: RED layer | protocol-only | multimodal not implemented; real run pending |
| JD-16 | 美团 | 【基座大模型北斗实习】开放域智能体交互与自动化评测演进机制研究 | 实习 | 核心 | benchmark,judge,agent,calibration,code | 岗位职责 简介：随着 OpenClaw、Claude Code 等 Agent 进入实战领域，传统的静态评测已无法衡… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: HumanEval+ | offline-tested | real model run pending |
| JD-17 | DeepSeek | Agent Harness 团队（仅深度学习研究员方向进入分析） | 实习 | 待核验 | benchmark,metric,agent,calibration,multimodal | 加入 DeepSeek Harness 团队，探索 Agent Harness 方向的未知前沿。 | no direct project claim; monitor only | not-claimed | algorithm attribute unverified |
| JD-18 | 京东 | 算法开发岗（具身大模型评测研究） | 社招 | 相邻 | benchmark,metric,agent,contamination,safety | 在具体实践中，我们面向多语言、多模态大模型训练，开展数据清洗、去重、打标等关键算法与方法建设，并系统性构建预训练与后… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed; retail: RED layer | protocol-only | multimodal not implemented; real run pending |
| JD-19 | 阶跃星辰 | 大模型评测算法实习生 | 实习 | 核心 | benchmark,agent,longctx,code,data | 我们是专注于基座模型测评的团队，本职位承担模型基础能力与 Agent 能力相关的评测算法工作，探索前沿、科学的评测体… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; foundation: RULER | offline-tested | real model run pending |
| JD-20 | 智谱 | GLM-Code Agent算法评测工程师 | 社招 | 核心 | benchmark,metric,agent,code,platform | 【岗位职责】 Code Agent 框架开发与迭代：参与公司自研或开源Code Agent框架的设计、开发与迭代，优… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: HumanEval+ | offline-tested | real model run pending |
| JD-21 | 商汤 | 【27届校招】大模型评测算法工程师 | 校招 | 核心 | benchmark,metric,judge,agent,contamination | 职位描述 1、评测体系设计： 设计面向 LLM Agent 的多维度评测框架，覆盖任务规划、工具调用、记忆管理、多轮… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; retail: RED layer | offline-tested | not a security benchmark; real run pending |
| JD-22 | 商汤 | 大模型评测实习生（AI PPT） | 实习 | 核心 | benchmark,judge,agent,multimodal,code | 职位描述 岗位职责 1、Benchmark研究与构建：负责AI PPT生成及大模型能力评测体系建设，围绕PPT内容生… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: HumanEval+; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-23 | 网易 | AI应用工程师（评测方向） | 社招 | 核心 | benchmark,metric,judge,agent,safety | 岗位职责 我们正在构建内部 Agent Benchmark 评测体系，聚焦 Coding Agent 方向，系统性地… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; retail: RED layer | offline-tested | not a security benchmark; real run pending |
| JD-24 | 网易 | 易盾-Agent安全算法实习生 | 实习 | 相邻 | benchmark,metric,agent,safety,platform | 岗位职责 1、负责 Agent 安全防护体系建设，包括但不限于 Agent 在规划、推理、工具调用、外部环境交互等过… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; retail: RED layer | protocol-only | not a security benchmark; real run pending |
| JD-25 | 科大讯飞 | AI研究院-中级研究算法工程师-评测方向 | 社招 | 核心 | metric,judge,agent,calibration,safety | 工作职责 1.深耕评测与优化的算法工程师，聚焦大语言模型（LLM）、智能体及相关多模态模型的性能评估、能力边界探索及… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed; retail: RED layer | offline-tested | multimodal not implemented; real run pending |
| JD-26 | 阿里巴巴 | 算法工程师-大模型评测 | 校招 | 核心 | benchmark,judge,agent,safety,multimodal | 职位描述 1. 深度挖掘大模型在复杂任务、长尾场景中的弱点，设计并构建具有可扩展性的自动化评测方案及高质量数据集； | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed; retail: RED layer | offline-tested | multimodal not implemented; real run pending |
| JD-27 | 阿里巴巴 | 算法工程师-预训练评测 | 校招 | 核心 | benchmark,metric,agent,longctx,code | 职位描述 1. 针对预训练（含mid-training）模型在coding，cowork，长尾知识，长文本能力等方面… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; foundation: RULER | offline-tested | real model run pending |
| JD-28 | 阿里巴巴 | 日常实习生-Agentic评测算法工程师-Qwen基础模型 | 实习 | 核心 | benchmark,metric,judge,agent,safety | 职位描述 随着大模型从对话助手快速演进为能够理解复杂需求、调用工具、记忆、操作真实环境并持续完成任务的智能体，传统基… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed; retail: RED layer | offline-tested | multimodal not implemented; real run pending |
| JD-29 | 阿里巴巴 | 日常实习生-Pre-training/Mid-training 评测… | 实习 | 核心 | benchmark,metric,agent,calibration,longctx | 职位描述 1. 评测数据挖掘 （1） 针对预训练（含mid-training，下同）模型在coding，cowork… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; foundation: RULER | offline-tested | real model run pending |
| JD-30 | 阿里巴巴 | 日常实习生-大模型应用评测算法-未来生活实验室 | 实习 | 核心 | benchmark,metric,judge,calibration,code | 职位描述 1. 协助团队开展大模型核心应用的评测算法研发工作，参与benchmark构建和评测框架搭建工作； | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+ | offline-tested | real model run pending |
| JD-31 | 阿里巴巴 | 日常实习生-数据智多星-数据评测算法方向 | 实习 | 相邻 | benchmark,agent,code,data,training | 我们的研究方向覆盖： 1. 多智能体协作式数据合成算法 2. 高质量训练数据筛选算法 3. RL算法创新 4. 通用… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+ | protocol-only | real model run pending |
| JD-32 | 阿里巴巴 | 智能体运行时安全评测与防御关键技术研究-阿里星 | 校招 | 核心 | benchmark,agent,safety,platform,diagnosis | 职位描述 1.负责智能体运行时安全评测体系的构建，围绕真实工具调用（Function Call）、多步任务执行、跨系… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; retail: RED layer | offline-tested | not a security benchmark; real run pending |
| JD-33 | 阿里巴巴 | 云安全大模型智能体对抗评测与能力边界定义-阿里星/A Star | 校招 | 核心 | judge,agent,safety,platform | 职位描述 1、设计面向云安全场景（入侵检测、自动化渗透、合规审计）的大模型评测体系，定义“懂安全的 AI”量化标准； | retail: trajectory judge/diagnosis; retail: RED layer | offline-tested | not a security benchmark; real run pending |
| JD-34 | 阿里巴巴 | AI Coding 数据分析与评测-阿里星 | 校招 | 核心 | benchmark,contamination,code,data,platform | 职位描述 1.构建大规模数据回流体系：设计并实现高效的数据采集、清洗、标注 pipeline，从线上真实交互中挖掘高… | foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+ | offline-tested | real model run pending |
| JD-35 | 阿里巴巴 | 阿里巴巴日常实习生-智能体安全评测 | 实习 | 相邻 | benchmark,agent,safety,code,platform | 职位描述 1. 参与智能体前沿安全风险研究，重点关注失控风险（Loss of Control）方向，跟踪学术与行业动… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: HumanEval+; retail: RED layer | protocol-only | not a security benchmark; real run pending |
| JD-36 | 阿里巴巴 | 日常实习生-多模态及视觉生成大模型安全评测与原生安全机制研究 | 实习 | 相邻 | calibration,safety,multimodal,code,platform | 职位描述 1、参与多模态大模型与视觉生成大模型端到端安全评测体系建设，围绕内容安全、对抗鲁棒性、越狱攻击、防御有效性… | foundation: task/metric protocol; foundation: HumanEval+; multimodal: not claimed; retail: RED layer | protocol-only | multimodal not implemented; real run pending |
| JD-37 | 阿里巴巴 | 日常实习生-大模型安全评测与原生安全机制研究 | 实习 | 相邻 | safety,multimodal,code,platform | 职位描述 1、参与大模型端到端安全评测体系建设，围绕内容安全、对抗鲁棒性、越狱攻击、防御有效性等方向设计并执行系统化… | foundation: HumanEval+; multimodal: not claimed; retail: RED layer | protocol-only | multimodal not implemented; real run pending |
| JD-38 | 阿里巴巴 | 日常实习生-大模型数据评测-Qwen基础模型 | 实习 | 相邻 | benchmark,metric,agent,calibration,contamination | 我们通过 RL、SFT、RFT 等技术探索大模型潜能，并致力于提升其 Agent 能力，让大模型真正服务于真实世界。 | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed | protocol-only | multimodal not implemented; real run pending |
| JD-39 | 阿里巴巴 | AI评测工程师 | 实习 | 核心 | benchmark,metric,judge,agent,multimodal | 职位描述 作为大模型评测研发工程师，将负责“大模型通用Benchmark评测体系”与“业务领域Benchmark构建… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-40 | 阿里巴巴 | 日常实习生-大模型安全评测实习生 | 实习 | 相邻 | benchmark,metric,judge,calibration,safety | 职位描述 1、参与大模型安全评测体系的设计与建设，围绕内容安全、价值观对齐与越狱攻击等方向，搭建多维度、多场景、多语… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; retail: RED layer | protocol-only | not a security benchmark; real run pending |
| JD-41 | 蚂蚁集团 | 蚂蚁集团-大模型评测专家-北京/杭州【AGI专项】 | 社招 | 核心 | benchmark,code,training | 基于AIGC等技术建设高质量评测数据集，与业界公开评测集有机结合，深入大模型预训练、后训练、深度思考等各个阶段，利用… | foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+ | offline-tested | real model run pending |
| JD-42 | 蚂蚁集团 | 蚂蚁集团-多模态大模型评测-杭州/北京【AGI专项】 | 社招 | 核心 | benchmark,metric,agent,safety,multimodal | 职位描述 1、评测体系设计与搭建: 负责设计和搭建业界领先的全模态（图文、音视频）大模型评测体系，建立科学、全面、高… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: HumanEval+; multimodal: not claimed; retail: RED layer | offline-tested | multimodal not implemented; real run pending |
| JD-43 | 蚂蚁集团 | 蚂蚁集团-AI算法评测工程师-支付宝技术 | 社招 | 核心 | benchmark,metric,judge,agent,calibration | 职位描述 1. 评测体系建设：面向大模型、智能体及多智能体协作场景，设计客观、可量化的评测方案，建立覆盖任务完成质量… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; retail: RED layer | offline-tested | not a security benchmark; real run pending |
| JD-44 | 蚂蚁集团 | 蚂蚁集团-AI算法评测工程师-端智能 | 社招 | 核心 | benchmark,metric,judge,agent,calibration | 职位描述 1. 评测体系与标准构建：负责AI Agent、LLM（大语言模型）及VLM（视觉语言模型）的效果与性能评… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-45 | 蚂蚁集团 | 蚂蚁集团-大模型应用算法（自动化评测与benchmark）-健康事业… | 社招 | 核心 | benchmark,metric,judge,agent,calibration | 职位描述 职位概述 探索行业前沿的大模型技术，建立科学、全面的评测体系，支持模型演进、产品落地、竞对分析评估，通过自… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; foundation: RULER; retail: RED layer | offline-tested | not a security benchmark; real run pending |
| JD-46 | 蚂蚁集团 | 蚂蚁集团-大模型 Benchmark 与评测体系工程师 / 专家-杭… | 社招 | 核心 | benchmark,agent,safety,multimodal,data | 职位描述 1. 评测洞察与缺陷定位：基于对抗性分析、错误归因、能力边界挖掘等方法，系统定位模型在金融、医疗等场景的核… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; multimodal: not claimed; retail: RED layer | offline-tested | multimodal not implemented; real run pending |
| JD-47 | 蚂蚁集团 | 蚂蚁集团-垂类模型评测科学家-北京/杭州/上海【AGI专项】 | 社招 | 核心 | metric,agent,calibration,safety,code | 职位描述 1、定义垂类行业大模型的"黄金标准"，构建涵盖合规性、事实性、逻辑推理及安全性的多维度评测体系； | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; retail: RED layer | offline-tested | not a security benchmark; real run pending |
| JD-48 | 蚂蚁集团 | 蚂蚁集团-模型与评测算法专家-北京/杭州【CIO技术】 | 社招 | 核心 | metric,agent,calibration,code,training | 职位描述 1. Code Agent模型Badcase分析与优化 深入分析Code Agent在真实研发场景中产生的… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+ | offline-tested | real model run pending |
| JD-49 | 蚂蚁集团 | 蚂蚁集团-Agent 评测研发工程师-健康事业群 | 社招 | 核心 | benchmark,metric,agent,calibration,safety | 职位描述 1. 负责大模型 Agent 系统的全流程评测工作，涵盖功能评测、性能评测、效果评测及稳定性评测，重点关注… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; retail: RED layer | offline-tested | not a security benchmark; real run pending |
| JD-50 | 蚂蚁集团 | 蚂蚁集团-语音大模型评测工程师-健康事业群 | 社招 | 核心 | benchmark,metric,agent,safety,multimodal | 职位描述 团队介绍 负责医疗语音大模型的研发和应用，覆盖语音前端DSP、3A、VAD、ASR、TTS等核心技术方向，… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; multimodal: not claimed; retail: RED layer | offline-tested | multimodal not implemented; real run pending |
| JD-51 | 蚂蚁集团 | 【Plan A】大模型动态评测与评测诊断方向（AGI蓝军）-27届 | 校招 | 核心 | metric,agent,calibration,training,platform | 职位描述 1. 面向基座模型、领域模型、应用系统与智能体，研究如何将不断涌现的智能能力转化为可测量、可复现的科学问题… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT | offline-tested | real model run pending |
| JD-52 | 蚂蚁集团 | 大模型评测研究实习生 | 实习 | 核心 | benchmark,multimodal,code,training,platform | 职位描述 1. 设计与开发评测方案： 围绕大语言模型和多模态大模型的各项能力，设计科学、公正、全面的评测（Bench… | foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-53 | 蚂蚁集团 | 【蚂蚁星】多模态理解与生成评测算法研究（实习） | 实习 | 核心 | benchmark,metric,judge,agent,calibration | 职位描述 我们聚焦实时多模态交互、数字人、虚拟环境、音视频生成等前沿 AI 场景，建设面向下一代多模态模型的评测算法… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-54 | 蚂蚁集团 | 智能体评测理论实习生 | 实习 | 核心 | benchmark,metric,calibration,safety | 职位描述 1. 指标体系的统计学优化：引入评测理论方法，评估现有指标的区分度和鲁棒性，提出改进方案； | foundation: task/metric protocol; retail: RED layer | offline-tested | not a security benchmark; real run pending |
| JD-55 | 蚂蚁集团 | 【蚂蚁星】AI工程师-大模型评测-百灵-27届 | 校招 | 核心 | benchmark,metric,agent,calibration,training | 基模评测关注的不只是 benchmark 分数本身，而是这些分数能否真实反映： * 模型的极限深度思考能力，是否被评… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT | offline-tested | real model run pending |
| JD-56 | 蚂蚁集团 | 财富AI Lab-大模型评测工程师 | 实习 | 核心 | benchmark,metric,judge,agent,calibration | 职位描述 一、评测体系设计与环境构建 ● 面向大模型应用、大模型基座、Agent、多模态和复杂业务场景，设计评测基准… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed; retail: RED layer | offline-tested | multimodal not implemented; real run pending |
| JD-57 | 蚂蚁集团 | 【蚂蚁星】AI工程师-大模型评测-27届 | 校招 | 核心 | benchmark,agent,safety,multimodal,data | 职位描述 1. 评测体系设计与平台化落地：主导设计数据驱动的LLM/多模态/Agent评测体系，建设自动化评测分析能… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; multimodal: not claimed; retail: RED layer | offline-tested | multimodal not implemented; real run pending |
| JD-58 | 蚂蚁集团 | CTO-大模型-评测体系建设 | 实习 | 核心 | benchmark,safety,multimodal,code,training | 在本课题中： 1. 我们希望通过引入业界SOTA Benchmark以及自建高质量benchmark，构建全面、高效… | foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed; retail: RED layer | offline-tested | multimodal not implemented; real run pending |
| JD-59 | 蚂蚁集团 | 研究型实习生- 医疗大模型评测方案的研究和应用 | 实习 | 核心 | benchmark,metric,judge,calibration,multimodal | 职位描述 研究领域： 大模型 项目简介： 随着阿福逐步从“文本问答”走向“多模态医疗服务”（如检验检查单解读、影像/… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed | offline-tested | multimodal not implemented; real run pending |
| JD-60 | 蚂蚁集团 | 【蚂蚁星】算法工程师-评测方向-大安全（实习） | 实习 | 核心 | platform | 2. 熟悉PyTorch/TensorFlow等框架，有数据处理和算法实现能力； | no direct claim | not-claimed | real model run pending |
| JD-61 | 米哈游 | AI 模型评测专家 - 星布谷地 | 社招 | 核心 | benchmark,metric,judge,agent,calibration | 岗位职责 1）评测体系搭建：负责游戏体验与角色扮演场景下大模型的全链路评测体系建设，设计覆盖多维度的评测指标体系（如… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; retail: RED layer | offline-tested | not a security benchmark; real run pending |
| JD-62 | 米哈游 | 大模型-LLM Evaluation算法研究员 | 校招 | 核心 | benchmark,judge,agent,safety,code | 岗位职责 1、面向代码智能体能力构建评测体系，覆盖代码库理解、Issue 修复、跨文件修改、测试生成、调试定位、命令… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; retail: RED layer | offline-tested | not a security benchmark; real run pending |
| JD-63 | 米哈游 | 大模型算法实习生（评测方向） | 实习 | 核心 | benchmark,platform | 2、协助优化评测框架，保证评测任务的可靠和公允； | foundation: task/metric protocol | offline-tested | real model run pending |
| JD-64 | 米哈游 | LLM Evaluation算法实习生 | 实习 | 核心 | benchmark,metric,judge,code,data | 岗位职责 1. 对大语言模型评估结果做深入数据分析，理解不同评估指标与用户体验、需求之间的关联，对模型训练迭代提供指… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+ | offline-tested | real model run pending |
| JD-65 | 百川智能 | 【源点顶尖人才计划】大模型算法工程师 | 校招 | 相邻 | benchmark,agent,multimodal,longctx,data | 职位描述 1、参与大语言模型核心算法研发，覆盖预训练、后训练（SFT/RL）、模型架构创新与能力评测全链路； | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: RULER; multimodal: not claimed | protocol-only | multimodal not implemented; real run pending |
| JD-66 | 滴滴 | 大模型算法工程师-北京 | 社招 | 相邻 | benchmark,agent,multimodal,longctx,code | 岗位职责 负责生活类智能体算法研发与优化, 使用大模型实现用户需求理解与分析、规划、执行、反思等核心agent 参与… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; foundation: RULER; multimodal: not claimed | protocol-only | multimodal not implemented; real run pending |
| JD-67 | 小米 | 顶尖应届-MiMo后训练Agent研究员-MiMo | 校招 | 相邻 | agent,code,platform | 职位描述 我们是小米大模型团队的 Post-training Agent Group，专注于 AI Agent 的研… | retail: trajectory judge/diagnosis; foundation: HumanEval+ | protocol-only | real model run pending |
| JD-68 | 小米 | 大模型算法专家 | 社招 | 相邻 | metric,agent,multimodal,code,data | 职位描述 1. 面向Agentic OS，参与端侧大模型架构设计、预训练、后训练、端侧部署和推理加速； | retail: trajectory judge/diagnosis; foundation: task/metric protocol; foundation: diagnostic selection/SFT; foundation: HumanEval+; multimodal: not claimed | protocol-only | multimodal not implemented; real run pending |
| JD-69 | 小米 | 大模型agent算法工程师 | 校招 | 相邻 | agent,multimodal,data,training,platform | 职位描述 探索 Agent Harness 研究与应用的前沿技术，构建可进化的 Agent Harness 技术底座… | retail: trajectory judge/diagnosis; foundation: diagnostic selection/SFT; multimodal: not claimed | protocol-only | multimodal not implemented; real run pending |
| JD-70 | 小米 | 顶尖应届-具身大模型算法研究员-具身模型与应用部 | 校招 | 相邻 | benchmark,agent,calibration,multimodal,platform | 职位描述 1、设计并实现 VLA / Embodied VLM / World Model 的训练目标、分布式训练方… | retail: trajectory judge/diagnosis; foundation: task/metric protocol; multimodal: not claimed | protocol-only | multimodal not implemented; real run pending |

## 5. 排除项与缺失（不进入 70 条主样本）

| 对象 | 标题 | 原因 |
|---|---|---|
| 蚂蚁集团 / 蚂蚁集团-260826011707588 | 【蚂蚁星】多模态理解与生成评测算法研究-27届 | 与JD-53同一角色的校招版本重复，合并到JD-53。 |
| 蚂蚁集团 / 蚂蚁集团-26032609330453 | 【蚂蚁星】AI工程师-大模型评测（实习） | 与JD-57同一角色的实习版本重复，合并到JD-57。 |
| 蚂蚁集团 / 蚂蚁集团-26051209984609 | 【蚂蚁星】算法工程师-评测方向-大安全-27届 | 与JD-60同一角色的校招版本重复，合并到JD-60。 |
| 米哈游 / 米哈游-9690 | LLM Evaluation算法研究员 | 与JD-62同一角色的社招版本重复，合并到JD-62。 |
| 阿里巴巴 / 199909720005 | 大模型评测实习生（通用方向） | 取得完整正文但算法属性待核验；未进入70条主样本。 |
| 月之暗面 / careers.kimi.com | Eval岗位 | 职责为工程/产品方向，非评测算法研究。 |
| 用户截图 / SC-01/SC-02/SC-03/SC-04/SC-05-10/SC-06-07/SC-08/SC-09/SC-11 | 截图补充材料 | 单独标注来源与截断，不并入官网完整样本统计。 |

另有 11 家公司未取得合格评测 JD：快手、拼多多、哔哩哔哩、携程、360、月之暗面、零一万物、华为、蔚来、小鹏、理想汽车。其中快手、携程、360、零一万物、华为、理想汽车属于检索/动态站点未取得完整正文；拼多多、哔哩哔哩、月之暗面、蔚来、小鹏属于已取得正文但职责不是评测算法。“没有取得合格全文”不等于“该公司没有相关岗位”。快手、携程、360、零一万物、华为、理想汽车六家已在 2026-10-22 重新检索，仍未取得合格评测 JD；重检 URL 与结论记录在 jd_sources.json 各公司条目中。

## 6. 两个项目的分别映射

| 项目 | 主要对应能力 | 主要 JD | 不声称 |
|---|---|---|---|
| retail-agent-eval | 轨迹 Judge、证据定位、人工校准、失败归因驱动提示优化 | JD-02、JD-10、JD-16、JD-21、JD-28、JD-49、JD-51、JD-54 | 不声称六层划分最优、不声称已完成因果根因分析 |
| foundation-model-eval | 基座能力测量、污染检查、错误诊断、等预算数据选择、训练前后比较 | JD-13、JD-15、JD-27、JD-29、JD-38、JD-45、JD-51、JD-58 | 不声称完成预训练研究、不合成无依据总分 |

## 7. 复核结论

- 70 条中有 51 条以评测为主职责，18 条为相邻研究，1 条待核验；实习/校招样本 42 条，社招 28 条。
- 最高频能力是 Benchmark/评测集、指标、LLM Judge、Agent 轨迹与训练-评测闭环；两项目分别覆盖轨迹侧和基座侧。
- 明确不覆盖：多模态/语音/视觉专项、生产评测平台、对抗安全 benchmark、预训练本身。
- 所有“验证”列只描述离线工程检查；真实模型、训练和人工标注结果必须由 H20 运行后回填，不能用本文替代。

## 8. 修订记录

| 日期 | 变更 | 影响 |
|---|---|---|
| 2026-10-22 | 建立70条官网完整正文档案、正文SHA-256与来源URL | 初始归档；19家公司 |
| 2026-10-22 | 补30家公司检索覆盖、4条同角色去重、11家缺失/排除记录 | 新增jd_sources.json；不改变正文 |
| 2026-10-22 | 对快手/携程/360/零一万物/华为/理想汽车重新检索 | 仍无合格评测JD，记录重检URL与结论 |
| 2026-10-22 | 增加核心/相邻/待核验分类、能力标签和项目映射 | 新增jd_review.json、jd_capability_stats.json、本文件 |

正文修改必须保留旧正文哈希、来源与原因；本档案只做追加式修订，不静默覆盖原文。

