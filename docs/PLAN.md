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
| [JudgeLM](https://github.com/baaivision/JudgeLM) | 专用Judge训练与评估方法参考 |

淘宝方法来源：[原文](https://mp.weixin.qq.com/s/blMjReLQZUuSK6bl6Bt3yA)。PDF保留在用户原目录，不随项目重新分发。上游依赖归属保持不变，明确区分直接复用、适配实现与个人改进。

## 3. 实验目的与预期结果

| 问题 | 预期检验方向 | 最终产物 |
|---|---|---|
| 分层评测是否可信 | 识别任务失败、业务违规、证据不足 | Judge校验表、混淆矩阵与错误案例 |
| 分层归因是否帮助优化 | 相同搜索预算下提高独立任务表现或减少尝试 | 主实验表、优化曲线、失败类型变化 |
| 小Judge是否值得微调 | 可靠性与调用开销之间的权衡 | 原始小模型、SFT模型与强模型对照 |

预期收益仅作假设，不预填提升数字。无显著提升、局部退化、跨版本失效均保留并分析。

业务落点：零售服务Agent发布前回归，发现退换货流程中的执行失败、政策违规和回复失实，验证修复效果。结论限于所构建环境，不扩展为未经测量的线上收益。

## 4. 论文支持

| 论文 | 方法依据与采用方式 |
|---|---|
| [τ-bench，ICLR2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b126cc38b8638e07bef37e7b2bb72bf-Abstract-Conference.html) | 用户/工具/政策交互、终态核验、重复运行可靠性 |
| [AgentRewardBench](https://arxiv.org/abs/2504.08942) | 自动评分器需要独立人工校验；分析成功、副作用与重复行为误判 |
| [JudgeLM，ICLR2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/7f8f73134e253845a8f82983219a8452-Abstract-Conference.html) | 导出业务评分训练集，比较SFT前后可靠性 |
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

个人改进聚焦：**将分层失败归因组织为GEPA可利用的结构化反馈。**

反馈包含失败层级、具体业务规则、可定位的轨迹证据、可修改的Agent提示位置及建议。区分数据缺失、Rubric错误与Agent错误；仅确认属于Agent提示或执行要求的问题进入Agent优化。

验证条件是相同预算下，相比正常GEPA产生稳定独立测试收益。GEPA本身已有文字反思能力，基线应获得正常轨迹与反馈；区别限定为分层组织，而非是否提供有用反馈。

CONTRIBUTIONS.md分别记录淘宝流程复现、开源适配、个人反馈实现，以及结果能否支持改进与创新主张。不声称首次提出分层评测或失败归因。

## 6. 完整实验设计

### 6.1 数据与划分

- 固定τ-bench v1.0.1零售域114任务。
- 保留官方test40；官方train74划为train54/dev20。
- 使用固定盐值的任务ID哈希排序，保存清单；[官方划分](https://github.com/sierra-research/tau2-bench/blob/v1.0.1/data/tau2/domains/retail/split_tasks.json)。
- 合成扩充只基于train；同源样本跟随parent_task_id划分。
- test任务、轨迹、反馈不得进入提示词优化、Judge训练或候选选择。
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

- 去层级：保留规则/证据，移除失败层级组织。
- 去证据定位：保留层级/规则，移除具体证据引用。
- 两组使用A3相同种子和预算。
- 第二模型比较A0/A2/A3，检查是否依赖单一底座。
- train改写扩充表现与独立test表现分开；改写不当作新独立任务。

### 6.4 Judge实验

固定同一批Agent轨迹：

| 组别 | 小模型权重 | 提示词 |
|---|---|---|
| J0 | 原始 | 通用 |
| J1 | 原始 | 分层Rubric |
| J2 | SFT后 | 通用 |
| J3 | SFT后 | 分层Rubric |
| J4 | 固定强模型 | 分层Rubric，参照 |

J0–J3使用同一小模型底座。导出远端SFT格式，标记人工、环境检查、教师标签来源；教师不当人工真值。用独立人工金标检验；SFT模型通过API接回本地。Agent主实验使用同一评分协议，Judge实验单独汇报。本地不负责Jupyter训练。

### 6.5 指标、统计与结果

Agent：官方成功率及评分组成、三次均成功任务比例、政策违规、重复执行及副作用、调用次数/Token/耗时/优化总开销。

Judge：准确率、Precision/Recall/F1、真实失败误放行比例、弃判率、自动覆盖率、解析失败率；在同覆盖率下比较，防止弃判取巧。

统计：任务为配对单位，报告A3−A2差值和95%CI；按任务分组Bootstrap，保留三次重复关系，单独呈现优化种子差异。有限任务不确定性必须披露，辅助指标用于诊断。API/评分异常单独记账，未完成运行不得静默进入完整表。

交付图表：①Agent版本/方法表；②dev优化曲线与固定test最终结果；③分层失败及修复案例；④Judge混淆矩阵与可靠性—开销；⑤消融与第二模型结果。

### 6.6 实施顺序与验收

1. 工程约定、引用清单、预注册、固定样例。
2. 固定样例闭环，再跑至少5个真实零售任务。
3. 批量运行、人工校准、基线报告。
4. GEPA、分层反馈、消融和Judge实验。
5. 复现命令、配置快照、公开数据清单、最终结论。

验收包括：环境隔离、无同源泄漏、有效证据引用、异常可对账、评分版本固定、真实结果可追溯、另一位使用者可按文档复现。**只有上述实验、标注和最终结果也有可核查产物后，才可将整体计划标为完成。**
