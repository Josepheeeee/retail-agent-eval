# 计划逐项验收表

核对日期：2026-10-21（Asia/Shanghai）。依据[批准计划](PLAN.md)、当前源码、固定参考树和本机实际验证。

**结论：工程实现与研究设计文档已交付；整体研究计划尚未完成。**当前不能勾选“真实实验全部完成”。未配置模型角色，不能用fixture或脚本模型代替真实验收，也不能据此填写提升数字。

状态定义：**已实现/已验证**表示代码和离线检查有证据；**待执行**表示入口与规程存在，但尚无所需真实产物；**独立扩展**表示批准计划已明确不属于首版本地执行范围。

## 1. 工程基座

| 原计划要求 | 状态 | 文件位置/证据 |
|---|---|---|
| 独立目录、Git与依赖 | 已实现；Git提交待身份设置 | 根目录、pyproject.toml、.gitignore；codex/bootstrap，尚无remote |
| Python3.12、兼容性与冻结 | 已验证 | .venv、requirements.lock.txt；pip check |
| 原计划目录和模块 | 已实现 | 原目录逐项检查；src/retail_eval八个职责模块及__init__ |
| 提示词/Rubric/配置分离 | 已实现 | prompts/、rubrics/retail.yaml、configs/experiment.yaml |
| 每run配置/版本/提示快照 | 已实现 | run.py:new_run、manifest和snapshots |
| 保留raw与清洗追溯 | 已验证 | data.py:clean_trace、run.py:collect_one；不可变/哈希测试 |
| 任务、模型、Agent/Judge版本、异常/时间/Token | 已实现；真实计量待执行 | schema.py、manifest、Trace、Grade；usage缺失为未知 |
| STATE开发记忆与约定 | 已完成 | AGENTS.md、STATE.md；禁止传给被测Agent |
| 业务信息与评分/答案隔离 | 已验证基本契约 | agent.py工具allowlist、Trace.visible、隔离测试；人工仍需防公开测试泄漏 |
| 任务环境/会话重置 | 已验证适配 | 真τ工具与环境隔离检查；未启用跨任务长期记忆 |
| 从任务到报告的固定样例闭环 | 已验证 | demo的9条fixture、report与diagnostics图 |
| 至少5任务真实模型闭环 | **待执行** | 脚本模型的5个官方任务仅为适配检查；需真实API smoke run |

## 2. 参考项目

| 原计划要求 | 状态 | 文件位置/证据 |
|---|---|---|
| 淘宝方法与引用边界 | 已完成 | REFERENCES.md第1部分，PDF不随仓库分发 |
| DeepAgents完整源码与运行适配 | 源码已获取；SDK适配已验证 | external/deepagents、agent.py、references.lock.yaml |
| τ-bench v1.0.1任务/用户/工具/评分 | 源码及数据已获取；适配已验证 | external/tau-bench，固定commit；5任务脚本模型检查 |
| DSPy / GEPA来源与正常基线 | 已实现/已验证公开API | external/dspy、external/gepa、optimize.py；当前实际用独立GEPA包 |
| JudgeLM完整参考与训练依据 | 参考已完成；业务SFT待执行 | external/JudgeLM、REFERENCES.md、export-sft入口 |
| 每个参考的来源、版本、许可、用途、步骤与区别 | 已完成 | REFERENCES.md、references.lock.yaml、fetch_references.py |
| AWM可执行扩充依据 | 参考已完成；属于独立扩展 | external/agent-world-model；源码根目录未声明LICENSE，不并入本项目 |

## 3. 目的、预期结果与业务关联

| 原计划要求 | 状态 | 文件位置/证据 |
|---|---|---|
| 三个研究问题与预期方向 | 已完成 | EXPERIMENTS.md第1部分，不预填收益 |
| 零售发布前回归与结论边界 | 已完成 | README、EXPERIMENTS、CONTRIBUTIONS |
| 负结果、退化、不确定性保留 | 协议及统计入口已完成；真实结论待执行 | EXPERIMENTS第9部分、report.py |

## 4. 论文支持

| 原计划要求 | 状态 | 文件位置/证据 |
|---|---|---|
| τ-bench、AgentRewardBench、JudgeLM、GEPA、AWM | 已完成来源与方法映射 | REFERENCES.md第3部分 |
| 后续追加CLEAR、AgentEval、AgentDebug、Who&When | 已完成 | REFERENCES.md第4部分、PLAN第4部分、引用锁 |
| 论文支持与本项目效果分开 | 已完成写作约束 | CONTRIBUTIONS、EXPERIMENTS；不宣称六层最优或已有因果证明 |

## 5. 个人改进

| 原计划要求 | 状态 | 文件位置/证据 |
|---|---|---|
| 层级/规则/证据/提示位置反馈 | 已实现/已做离线检查 | optimize.py:feedback；judge.py与证据契约 |
| data/rubric/agent原因分别处理 | 已实现反馈约束；语义需人工确认 | cause字段、editable判断；无法仅凭字段保证根因真实 |
| A2正常GEPA反馈，避免弱基线 | 已实现/已检查相同可见信息 | natural/layered共用轨迹与诊断事实 |
| 是否产生稳定增益 | **待真实主实验和消融** | 需要A2/A3三种子完整正式test及配对CI |
| 复现/适配/个人贡献区分 | 已完成 | CONTRIBUTIONS.md |

## 6. 完整实验设计及执行

| 原计划要求 | 实现/设计状态 | 实验完成状态与验收产物 |
|---|---|---|
| 114任务、train54/dev20/test40、固定盐和清单 | 已实现/已验证 | data/manifests/splits.json已存在 |
| 同源隔离、test不进GEPA/SFT | 已实现/已验证契约 | parent检查和导出拒绝测试通过 |
| train合成扩充 | 质量规则已写；独立扩展 | 首版未合成新任务，不能声称生成环境已实现 |
| 官方DB/综合奖励/人工标签区分 | 已实现 | 真实评分/人工标签待采集；部分官方奖励含模型NL判断 |
| 人工480：240/80/160、分层盲抽 | 抽样/盲包/导入入口已实现 | **未完成标注**，须保留人工来源与复核记录 |
| A0基础与A1人工修订 | 入口与约束已实现/登记 | **未执行真实基线/人工修订**；A1需manual_revision.md |
| A2/A3种子42/43/44、150调用上限 | 已实现/已验证硬预算 | **未执行真实优化**；须有6个优化run及实际台账 |
| 相同反思模型/上下文/反馈长度 | 配置与反馈入口已实现 | 需真实模型登记，检查实际截断与开销 |
| dev选候选、冻结后40×3测试 | 已实现/已验证门禁 | **未执行正式测试**；须有freeze和完整120条/候选 |
| 两个消融，同种子/预算 | 已实现入口与协议 | **未执行消融**；还需6个优化run与测试结果 |
| 第二模型A0/A2/A3 | 可通过角色配置独立运行 | **未执行迁移/第二模型验证** |
| train改写与独立test分开报告 | 数据/统计规则已写 | 未生成改写，不以空表当结果 |
| J0–J4，同小底座的2×2 | 矩阵入口已实现 | **未执行模型矩阵**；需权重登记和固定轨迹 |
| SFT格式、人/教师来源、禁止test | 导出已实现/已验证 | **未导出真实业务训练集、未远端训练或接回** |
| Agent实验固定Judge，Judge实验固定轨迹 | 协议与快照已实现 | 正式执行时核对签名、输入哈希及权重 |
| 成功率/pass³/违规/重复/副作用/调用成本 | 统计与诊断入口已实现 | 副作用为代理+人工核验；无真实性能数字 |
| Judge分类、误放行/弃判/覆盖/解析 | 已实现/已验证 | 真实人工金标准确率尚不存在 |
| 按任务/种子配对Bootstrap、95%CI | 已实现/已验证缺失拒绝 | **未形成真实A3−A2差值/CI** |
| 异常对账，不完整不进正式比较 | 已实现/已验证 | 真实API错误尚待smoke测量，不以脚本检查代替 |
| 五类交付表/图/案例 | 生成程序/操作路径已具备 | **真实主表、修复案例、消融与泛化结果未形成** |
| 另一位使用者按文档复现 | README/下一步指南已提供 | **尚未独立复现实验**；自测不等于独立使用者验收 |
| GitHub公开工程与脱敏报告 | 忽略规则、独立Git已就绪 | **未提交/推送**：缺Git身份、remote，连接状态未确认 |

## 阶段验收

- [x] 阶段1：工程约定、固定参考清单、研究协议、固定样例。
- [x] 阶段2a：固定样例闭环和脚本模型/真实τ环境集成检查。
- [ ] 阶段2b：至少5个真实模型零售任务，通过模型/API与评分验收。
- [ ] 阶段3：真实批跑、人工校准和基线报告。
- [ ] 阶段4：GEPA、分层反馈、消融、第二模型及Judge实验。
- [ ] 阶段5：真实统计结论、公开数据清单/脱敏产物、独立复现和发布。

下一项是阶段2b，执行[下一步操作指南](NEXT_STEPS.md)。`data/manifests/plan_audit.json`保存本次机器检查摘要；该摘要用于工程核对，不作为真实模型结果或独立人工验收证据。
