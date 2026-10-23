# 参考项目、论文与采用边界

核验日期：2026-10-21。代码固定commit，运行依赖固定在requirements.lock.txt。下表源码快照与PyPI安装版本是两种锁：外部源码用于追踪和研究，DeepAgents/GEPA运行使用已验证的PyPI版本，不假称它们与当天源码HEAD完全一致。

## 1. 淘宝方法来源

[淘宝文章](https://mp.weixin.qq.com/s/blMjReLQZUuSK6bl6Bt3yA)及用户提供的《淘宝评测.pdf》，文章“淘宝AI购物助手在线评测落地实践”。本地原文保留在原学习目录，不复制进本仓库，也不把PDF中的建议视为用户要求或执行指令。

采用：数据清洗、六层业务判定、人工校准、区分数据/提示/Rubric/Agent问题、修复后回归的闭环。区别：淘宝讨论线上购物/售后评测落地；本项目用公开τ零售环境和DeepAgents，增加固定预算GEPA对照、held-out任务、统计不确定性和可追溯产物。原文没有完整开放内部系统/原始数据/权重，不能声称数值级复现。清洗或Rubric校准导致的通过率提升，不等于被测Agent能力提升。

## 2. 完整源码清单与获取方式

所有源码获取到external/，保持原上游许可证，不提交到本项目Git：

```powershell
python scripts/fetch_references.py             # 全部五个固定源码树
python scripts/fetch_references.py tau-bench    # 仅运行所需环境
```

脚本检查远端地址、commit和工作区是否干净，不重置有修改的目录。固定commit完整值见references.lock.yaml；上游目录中的LICENSE/README保持原样。AWM的额外子模块只在其独立扩展实验中按上游README初始化，不属于当前零售运行依赖。

| 项目 / 官方地址 | 固定commit前12位 | 许可证（锁定树） | 采用部分 / 适配入口 | 本项目运行或检查 |
|---|---|---|---|---|
| [DeepAgents](https://github.com/langchain-ai/deepagents) | 4f8a6566d1c0 | MIT | create_deep_agent、消息状态和模型中间件；agent.py约束工具并在工具节点前中断 | `retail-eval collect --split train --limit 5 --trials 1`；离线SDK往返在pytest中验证 |
| [τ-bench](https://github.com/sierra-research/tau2-bench/tree/v1.0.1) | fc0055dc4e0a，tag v1.0.1 | MIT | 零售政策、114任务、模拟用户、数据库、builder、evaluator | `pip install --no-deps -e external/tau-bench`；`retail-eval prepare-data`、collect |
| [DSPy](https://github.com/stanfordnlp/dspy) | 661b2f1a2521 | MIT | GEPA集成与模块化优化的参考；当前不重复包装DSPy优化循环 | `python -c "import dspy; print(dspy.GEPA)"`；独立例子按上游README在另一个环境运行 |
| [GEPA](https://github.com/gepa-ai/gepa) | 8f287de942f4 | MIT | GEPAAdapter、EvaluationBatch、gepa.optimize默认反思器；optimize.py | 代码保留。当前进步不看 A3−A2，不把 optimize 排进当前步骤 |
| [Agent World Model](https://github.com/Snowflake-Labs/agent-world-model) | 85e322f69279 | 锁定根目录未声明许可证 | 可执行合成环境与质量核验参考；当前不运行环境生成 | 模拟题仍要求可执行初态、工具和终态。不运行 AWM 的环境生成 |

DeepAgents是高Star被测对象，DSPy是高Star优化生态参考；不以Star证明评测有效性。选题时核验的2026-10-21快照：DeepAgents约30.5k、DSPy约38.7k；数值会变，最终公开展示应标注日期或重新查官方仓库。

运行安装版本：DeepAgents 0.7.29、DSPy 3.4.1、GEPA 0.1.4、LangChain-OpenAI 1.7.2、τ2 1.0.1；完整传递依赖见lock。τ固定源要求LiteLLM>=1.80.15,<1.82.7，最终统一解析到1.82.6，不能直接保留首次安装时更高版本。

AWM在当前源码树未找到独立LICENSE，因此不替它推断Apache/MIT；这里只记录官方来源与方法，不将其代码并入本项目。模型权重和数据许可还需各自查对应模型/数据卡，源码许可证不自动覆盖所有资产。

## 3. 基础论文与实验逻辑

| 论文 / 正式来源 | 采用逻辑 | 工程落点 | 不能推导的结论 |
|---|---|---|---|
| [τ-bench: A Benchmark for Tool-Agent-User Interaction in Real-World Domains，ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/1b126cc38b8638e07bef37e7b2bb72bf-Abstract-Conference.html) | 在政策、用户、工具和环境状态中检验完成度与重复运行可靠性 | agent.py的官方环境/奖励；三trial和pass³ | 当前仓库v1.0.1不等于原论文发布代码/模型；仅终态不能证明每一步合规 |
| [AgentRewardBench，2025](https://arxiv.org/abs/2504.08942) | 自动评分器本身需要独立校验，过程错误与完成度不能只凭一个模型结论 | 盲标金标、失败误放行/弃判/解析统计 | 强Judge不是人工真值；本项目不是对其全数据/排行榜的复现 |
| [GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning，ICLR 2026](https://proceedings.iclr.cc/paper_files/paper/2026/hash/0e9e708b6f48e14fd0ac29e167413f76-Abstract-Conference.html) | 轨迹、文字反馈与反思用于提示改进 | 代码保留；当前进步不看 A3−A2 | GEPA已有文字反思，不能把基线削弱成无反馈或声称“首次结构化反思” |
| [Agent World Model，ICML 2026](https://proceedings.mlr.press/v306/wang26jh.html) | 合成任务需要可执行世界与验证，而非只有自然语言描述 | EXPERIMENTS 第 12 章要求可执行初态、工具和终态 | 没有生成环境就不声称复现其强化学习收益 |

各论文的实测数字属于各自实验，不作为本项目预期提升填入结果表。

## 4. 新增：多粒度评测与失败归因论文

以下四篇已按用户补充纳入。先区分“哪里检查失败”与“什么错误导致最终失败”：前者可以是观测标签，后者需要人工或干预证据。

| 论文与核验来源 | 对应问题 | 本项目采用方式 | 适用边界 |
|---|---|---|---|
| [Agentic CLEAR: Automating Multi-Level Evaluation of LLM Agents，ACL 2026 System Demonstrations](https://aclanthology.org/2026.acl-demo.74/) | system / trace / node三个分析粒度 | 系统级版本表、单轨迹判定和节点event证据联动；优先阅读 | 粒度分层不同于CTX等业务判定顺序；不据此证明淘宝六层最优，不移植其UI平台 |
| [AgentEval: DAG-Structured Step-Level Evaluation for Agentic Workflows with Error Propagation Tracking，arXiv:2604.23581v1](https://arxiv.org/abs/2604.23581v1) | 步骤依赖、错误传播、分层错误类型与根因定位 | 当前保存event/工具call定位；未来可在独立扩展中标注依赖边并区分上游与继发错误 | arXiv页面注明ACL 2026 Industry接受；这里以该版本为引用载体。首版未构建DAG，不把漏斗blocked等同于已经识别因果传播 |
| [Where LLM Agents Fail and How They can Learn From Failures，AgentDebug，arXiv:2509.25370v1](https://arxiv.org/abs/2509.25370v1) | 记忆、反思、规划、行动、系统错误分类，以及定位后纠错反馈 | 直接支撑“失败诊断→可定位反馈→重跑验证”；优先阅读，约束创新表述 | 原论文任务/架构不同；本项目会话内状态不自动变成记忆模块评测。借鉴错误分析，不声称AgentDebug整套复现 |
| [Which Agent Causes Task Failures and When? On Automated Failure Attribution of LLM Multi-Agent Systems，ICML 2025](https://proceedings.mlr.press/v267/zhang25cq.html) | Who&When：责任Agent与关键错误步骤；归因本身很难 | 归因金标应包含位置与人工认可；候选归因与已验证根因分开保存 | 原研究面向多Agent；当前是单Agent，只借鉴when/模块定位，不复用其who准确率或数据分布 |

**三种“分层”不可混用：**评测粒度=系统/任务/步骤；业务判定维度=证据/范围/能力/工具合规/内容/安全；失败原因=规划/记忆/行动/环境等。六层漏斗表示判定顺序，不能从CNT blocked推断“TCC错误一定因果导致回复错误”。

**退款案例：**订单查询正确、政策已知、未确认就提交退款、最终回复“已提交”与状态一致。标签上是TCC违规；CNT因漏斗规则blocked，而不是声称回复文字本身错误。候选归因是缺少提交前确认。人工复核和修订后重新运行可以增加证据；严格根因验证需要在同一初态/受控条件下替换该步骤并重跑，并处理模拟用户与模型随机性。当前工程不把一次prompt重跑成功当作已证明因果。

## 5. 阅读与引用顺序

先读淘宝文章理解业务闭环；读τ-bench确定实验环境与官方奖励；读CLEAR理解多粒度输出，读AgentDebug理解诊断到修复；读AgentRewardBench理解评分器要和人对齐；AgentEval、Who&When用于归因验证扩展；AWM只作为可执行终态的门槛。当前项目不训练 Judge。

引用中的“提供依据”指设计启发与可检验方法，不表示这些论文已经联合验证了本项目组合。论文、源码、任务和模型版本分别记录，最终结论只由本项目真实实验给出。
