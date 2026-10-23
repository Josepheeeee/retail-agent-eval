# 批准计划归档：面向零售服务 Agent 的分层评测与失败归因驱动优化

来源：用户在本对话中批准并要求实施的计划。此文件按原六部分保存全部要求；**它是目标规格，不是完成声明**。实际完成情况见[逐项验收表](PLAN_CHECKLIST.md)，执行细节见[实验预注册](EXPERIMENTS.md)，最新事实见[STATE.md](STATE.md)。后续新增的四篇论文列在第4部分，不更改已批准的实验预算和数据划分。

项目位于`C:\Users\33969\Documents\retail-agent-eval`，独立管理Git、依赖与实验结果。交付包括完整工程基座、参考项目、研究目标、论文依据、改进方法、可复现主实验和消融实验。

## 1. 完整工程基座

采用DeepAgents运行被测Agent，轻量评测运行器管理实验，形成：

**任务准备→Agent执行→轨迹清洗→分层评分→失败归因→优化→独立测试→版本报告。**

```text
retail-agent-eval/
├── README.md
├── AGENTS.md
├── pyproject.toml
├── requirements.lock.txt
├── references.lock.yaml
├── .env.example
├── .gitignore
├── configs/experiment.yaml
├── prompts/
│   ├── agent.md
│   ├── judge.md
│   └── feedback.md
├── rubrics/retail.yaml
├── docs/
│   ├── REFERENCES.md
│   ├── EXPERIMENTS.md
│   ├── CONTRIBUTIONS.md
│   └── STATE.md
├── src/retail_eval/
│   ├── __init__.py
│   ├── schema.py
│   ├── data.py
│   ├── agent.py
│   ├── judge.py
│   ├── optimize.py
│   ├── report.py
│   └── run.py
├── scripts/fetch_references.py
├── data/
│   ├── fixtures/
│   └── manifests/
├── tests/test_contracts.py
├── external/
└── runs/
```

工程规则：

1. 固定Python3.12，验证依赖兼容性后冻结版本。
2. 提示词、Rubric、实验参数分别维护；每次运行保存快照。
3. 保留原始轨迹；清洗后记录可追溯到原始记录。
4. 输出任务、模型、Agent/Judge版本、证据、异常、耗时和Token。
5. STATE.md保存项目记忆；开发助手按AGENTS.md读取和更新。
6. 被测Agent只接触允许的业务信息；项目笔记、评分标签和测试答案隔离。
7. 每个任务重置环境与会话；首版使用会话内状态，跨任务长期记忆属于独立扩展。

## 2. 完整参考项目

REFERENCES.md对每个项目记录官方地址、固定版本、许可证、采用部分、适配方式、运行步骤及区别。参考源码由脚本获取至external/，不纳入本项目Git。

| 来源 | 职责 |
|---|---|
| 淘宝评测实践及用户提供的《淘宝评测.pdf》 | 数据清洗、分层评测、人工校准、归因及修复验证的总体闭环 |
| [DeepAgents](https://github.com/langchain-ai/deepagents) | 高Star被测对象，接入零售政策与工具 |
| [τ-bench v1.0.1](https://github.com/sierra-research/tau2-bench/tree/v1.0.1) | 零售任务、用户模拟器、工具、状态与官方评分 |
| [DSPy](https://github.com/stanfordnlp/dspy) / [GEPA](https://github.com/gepa-ai/gepa) | 自动提示词优化方法与正常使用的对照基线 |
| 固定 Judge | prompts/judge.md 与 rubrics/retail.yaml；当前不训练小 Judge |

淘宝方法来源：[原文](https://mp.weixin.qq.com/s/blMjReLQZUuSK6bl6Bt3yA)。PDF保留在用户原目录，不随项目重新分发。上游依赖归属保持不变，明确区分直接复用、适配实现与个人改进。

## 3. 实验目的与预期结果

| 问题 | 预期检验方向 | 最终产物 |
|---|---|---|
| 尺子是否可信 | 测试 40 上 v1 与最终版的人机一致、误放行和最早错误 | 盲标金标与固定 Judge 的对照 |
| 助手是否改好了订单 | 只改尺子时官方终态通过率几乎不动 | 同一测试 40 的官方终态通过率 |

预期收益仅作假设，不预填提升数字。无显著提升、局部退化、跨版本失效均保留并分析。

业务落点：零售服务Agent发布前回归，发现退换货流程中的执行失败、政策违规和回复失实，验证修复效果。结论限于所构建环境，不扩展为未经测量的线上收益。

## 4. 论文支持

| 论文 | 方法依据与采用方式 |
|---|---|
| [τ-bench，ICLR2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b126cc38b8638e07bef37e7b2bb72bf-Abstract-Conference.html) | 用户/工具/政策交互、终态核验、重复运行可靠性 |
| [AgentRewardBench](https://arxiv.org/abs/2504.08942) | 自动评分器需要独立人工校验；分析成功、副作用与重复行为误判 |
| 模拟题 | 只从训练 54 派生；构建与筛选见 EXPERIMENTS 第 12 章 |
| [GEPA，ICLR2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/0e9e708b6f48e14fd0ac29e167413f76-Abstract-Conference.html) | 从轨迹与文字反馈学习提示词改进，作为正常优化基线 |
| [AWM，ICML2026](https://proceedings.mlr.press/v306/wang26jh.html) | 合成任务需可执行环境、状态与验证，指导train扩充及质量检查 |

用户后续追加：

| 论文 | 对本项目的支撑 |
|---|---|
| [Agentic CLEAR](https://aclanthology.org/2026.acl-demo.74/) | 系统、轨迹、节点三个评测粒度 |
| [AgentEval](https://arxiv.org/abs/2604.23581v1) | 依赖图、错误类型与传播分析的扩展依据 |
| [AgentDebug](https://arxiv.org/abs/2509.25370v1) | 失败诊断、定位和针对性反馈改进 |
| [Who&When](https://proceedings.mlr.press/v267/zhang25cq.html) | 责任位置与归因标注、评测；单Agent迁移需调整 |

论文提供方法逻辑；组合有效性由本项目验证。业务维度、评测粒度、失败原因分类不同；发现错误不等于证明根因，论文不证明淘宝六层划分最优。完整采用边界见REFERENCES.md。

## 5. 创新点与验证条件

个人改进聚焦：**用官方终态做锚，把尺子变化和 Agent 变化分开。** 当前进步不看 A3−A2。模拟题的构建与筛选见 [EXPERIMENTS.md](EXPERIMENTS.md) 第 12 章。

反馈包含失败层级、具体业务规则、可定位的轨迹证据、可修改的Agent提示位置及建议。区分数据缺失、Rubric错误与Agent错误；仅确认属于Agent提示或执行要求的问题进入Agent优化。

验证条件是相同预算下，相比正常GEPA产生稳定独立测试收益。GEPA本身已有文字反思能力，基线应获得正常轨迹与反馈；区别限定为分层组织，而非是否提供有用反馈。

CONTRIBUTIONS.md分别记录淘宝流程复现、开源适配、个人反馈实现，以及结果能否支持改进与创新主张。不声称首次提出分层评测或失败归因。

## 6. 完整实验设计

### 6.1 数据与划分

- 固定τ-bench v1.0.1零售域114任务。
- 保留官方test40；官方train74划为train54/dev20。
- 使用固定盐值的任务ID哈希排序，保存清单；[官方划分](https://github.com/sierra-research/tau2-bench/blob/v1.0.1/data/tau2/domains/retail/split_tasks.json)。
- 合成扩充只基于train；同源样本跟随parent_task_id划分。
- test任务、轨迹、反馈不得进入提示词修改、模拟题派生或水位判断。
- 数据库核验、官方综合评分、人工语义判断分别保存，标明官方评分中的模型判断。
- 人工目标480轨迹：train240/dev80/test160；按任务/结果分层抽样，隐藏模型、版本、自动评分；test标注在候选冻结后完成。

### 6.2 主实验

| 组别 | 定义 |
|---|---|
| A0 | 基础DeepAgents＋零售政策与工具 |
| A1 | 根据dev失败案例人工修订提示词 |
| A2 | 正常GEPA，提供轨迹与自然语言反馈 |
| A3 | GEPA＋分层归因、规则与证据反馈 |

- 只优化Agent提示词，固定环境、政策、工具与评分器。
- A2/A3各运行42/43/44三个优化种子；每种子最多150次任务评分调用。
- 反思模型、上下文限制、反馈长度上限一致，实际消耗可对账。
- A1最多检查20个dev任务，修订上限2小时，保存过程。
- 按dev选择候选；正式test前登记模型角色、预算、选择规则并冻结。
- 每个最终候选在全部40个test任务上运行3次。

### 6.3 消融与泛化

GEPA 消融和第二模型对照仍留在代码里，不排进当前步骤，也不作为 v1 与最终版的进步。模拟题只从训练父任务派生，见 EXPERIMENTS 第 12 章。

### 6.4 固定 Judge

当前只用 `prompts/judge.md` 和 `rubrics/retail.yaml`。不训练小 Judge，也不设 J0–J4。只有 `label_source=human` 进入一致率。teacher 行不能算进这份一致率。

### 6.5 指标、统计与结果

尺子：总体一致率；每一层的一致率，以及人标失败里 Judge 找回来的比例，该层没有失败就不报；误放行；最早错误事件对上的比例。

助手：官方终态通过率。只在助手改完并重做之后才用来声称订单做得更好。只改尺子时，这个数应几乎不动。

比较只在测试 40 的 v1 和最终版之间做。Judge 自己的通过率、模拟题涨幅和训练 54 涨幅不是进步。API 和评分异常单独记账。

### 6.6 实施顺序与验收

1. 工程约定、引用清单、预注册、固定样例。
2. 固定样例闭环，再跑至少 5 个真实零售任务。
3. 未修改的助手跑出 v1 轨迹，盲标并封存测试。
4. 按 EXPERIMENTS 第 12 章构建并筛选模拟题，在训练侧做 v2、v3…，水位看开发 20。
5. 测试 40 再跑最终版并另做盲标；变差记负结果。

验收包括：环境隔离、无同源泄漏、有效证据引用、异常可对账、评分版本固定、真实结果可追溯、另一位使用者可按文档复现。**只有上述实验、标注和最终结果也有可核查产物后，才可将整体计划标为完成。**
