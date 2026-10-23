# 项目状态与开发记忆

更新时间：2026-10-23（Asia/Shanghai）。工程基座已落地；当前实验改为尺子与官方终态两条主终点，并已从代码移除 Judge 微调。真实模型研究结果仍待执行。

## 本轮计划核对

- 批准计划完整归档：docs/PLAN.md；逐项状态、文件证据与阶段验收：docs/PLAN_CHECKLIST.md。
- README顶部新增当前阶段入口，docs/NEXT_STEPS.md给出使用现有环境、配置接口、五任务运行与结果核对、后续实验顺序和Git准备。
- docs/PREREGISTRATION.md与docs/manual_revision.md为待填写模板；不是已经完成的正式登记或人工实验。
- 本轮重新运行 pytest：**36 passed**，1 个上游 audioop 弃用 warning；pip check 无依赖冲突。
- 划分仍是 train54/dev20/test40。参考锁已去掉 JudgeLM 和 LlamaFactory。人工标注、v1 轨迹和研究结论不得标为完成。
- 当前验收范围是工程/文档/离线闭环。整体研究计划明确标为未完成；下一阶段是配置接口并取得5任务真实API验收记录。

## 已确定的决策

- 独立目录与 Git：retail-agent-eval，Python 3.12。
- DeepAgents 负责生成业务操作，τ-bench 唯一执行工具并重置环境。
- GEPA 使用独立包的公开 Adapter API；DSPy 作为参考实现与方法对照，不另写重复优化器。
- Agent 只看到业务政策、零售工具与会话；开发记忆、答案、评分和测试反馈不传入。
- 分层 Rubric 是诊断协议；官方任务奖励单独保存。
- 固定 train54/dev20/test40，盐 retail-eval-v1；同源扩充跟随父任务。
- 当前只改清洗、Judge 提示词、Rubric 或 Agent 提示词。不做跨任务长期记忆，不训练 Judge。GEPA 代码保留，当前进步不看 A3−A2。
- 先保证本地闭环，真实任务与人工校验需要配置模型接口后执行。

## 已实现与已验证

- 目录、独立Git、Python3.12.10 .venv、135个冻结运行依赖、提示词/Rubric/配置分离。
- 五个参考源码树按 references.lock.yaml 固定 commit 获取：τ-bench、DeepAgents、DSPy、GEPA、AWM。JudgeLM 与 LlamaFactory 已从当前锁里去掉。DeepAgents/GEPA/DSPy 运行包另以 requirements.lock.txt 固定。
- data/manifests/splits.json已生成：train54/dev20/test40，哈希盐retail-eval-v1，官方114任务无重叠遗漏。
- Trace/Event/Grade契约、原始轨迹持久化、清洗追溯、六层顺序/并行逻辑、真实event证据引用验证。
- DeepAgents业务工具过滤、τ工具节点中断与单次执行、每任务环境和会话重置。发现并修正了τ默认开场白的初始历史兼容问题。
- GEPA公开Adapter、正常自然语言反馈/分层反馈/两个消融、150次硬预算、调用台账、候选提示和反思记录、完整开发集选择及冻结。
- 批量收集、单一划分轨迹池、盲标导入/导出、固定 Judge 评分。微调导出和 J0–J4 已从当前项目移除。
- 版本表、成本及已知/缺失usage、官方评分成分、pass³、失败分布、混淆矩阵/同覆盖率分析、任务/种子配对Bootstrap、消融/第二模型的独立运行协议。
- Grade新增error_type、earliest_error_event、attribution_uncertainty和逐层support；最早事件必须可见且被证据引用，unclassified/unknown不被强迫编造根因。
- 人工标注导入保留六层标签、错误类型、位置、证据支持与 review 记录。只有 `label_source=human` 进入一致率。teacher 行不能算进这份一致率。
- 模拟题规则写在 EXPERIMENTS 第 12 章：LLM 只从训练 54 起草，人筛选后才进入 v2、v3 的训练侧。本轮没有生成真实模拟题。
- 新增`docs/JD_ANALYSIS.md`、`data/manifests/jd_sources.json`（30家公司）与`jd_review.json`（70条逐项分类/能力标签）；6家缺失公司已重新检索并记录URL与结论。
- `docs/JD_FIT.md` 已按去掉微调后的能力说明重算：70 条 JD 平均覆盖 60.1%（核心 63.1%；剔除明确非目标 73.6%）。训练等级为 0，因为当前实验不包含模型微调。
- 远程端点批跑门禁：`configs/experiment.yaml`登记`budget.max_task_runs`与输入/输出价格（0允许），未登记时`assert_api_budget`在创建run前停止。
- README复现命令；REFERENCES完整项目/论文映射；EXPERIMENTS完整预注册与480盲标计划；CONTRIBUTIONS复现/个人实现/创新证据边界。
- 用户新增的Agentic CLEAR、AgentEval、AgentDebug、Who&When已访问官方论文页核验并加入REFERENCES与引用锁，同时更新实验和创新边界。未宣称已实现DAG根因分析或证明六层划分最优。

## 验证记录

| 检查 | 结果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | **36 passed**，1 个上游 audioop 弃用 warning；去掉微调导出测试后仍通过 |
| `python -m pip check` | No broken requirements found |
| `python -m compileall -q src scripts` | 通过 |
| `import dspy; dspy.GEPA` | DSPy3.4.1及GEPA集成可导入 |
| `retail-eval prepare-data` | 54/20/40清单已生成并被测试验证 |
| `retail-eval doctor` | Python与数据可用；所有模型角色均未配置 |
| `retail-eval demo` | 9条自制fixture完整闭环；报告含3pass/3fail/1abstain/1parse_error/1error，官方成功率为N/A |
| DeepAgents SDK → τ工具 → SDK | 实际零售get_user_details往返、工具allowlist、环境隔离通过 |
| 5个官方任务的完整适配检查 | 使用脚本模型与脚本用户执行真实零售环境/官方评分接口，通过；**只是集成测试，不是模型benchmark** |
| 官方NL接口中断模拟 | 执行轨迹保留、error单独记录、未知reward未进入正常结果 |
| 公开文件检查 | 无凭证样式字符串；.env/external/runs/私有数据/权重被Git忽略 |

已生成可查看的离线示例：`runs/20261021T054635Z-demo-c6b7ad87/report/report.md`、`diagnostics.png`、`summary.json`。图表已视觉核对，清楚标注fixture/no performance claims。目录由运行命令动态生成，不需要固定复用该run ID。

测试覆盖还包括：虚构证据拒绝、前层阻断后 RED 仍判定、同源泄漏拒绝、teacher 不能进入人机一致、固定覆盖率防弃判取巧、三 trial 配对与缺失拒绝、GEPA 公开 API 实际离线调用、预算不超额、冻结协议绑定、轨迹池去重及异常对账。没有真实 API 调用或人工金标性能数字。

## 当前限制

- 尚无已配置的模型 API；没有真实模型提升结果。
- 人工 480 条标注、v1 轨迹、模拟题和测试 40 上的最终比较均待实验执行。当前项目不包含 Judge 微调。
- 已配置仓库本地Git身份并推送到公开仓库`Josepheeeee/retail-agent-eval`（`main`）；早期“未提交/未推送”的记录已过时。
- 公开内容不含密钥、私有轨迹、权重或运行结果；真实实验产物仍需脱敏后单独发布。
- 没有自动断点续跑；失败/中断run保留，修复后创建新run并记录重跑成本。
- 证据ID存在的校验不等同于语义正确；cause是候选归因，仍需人工复核/修复重跑，严格因果主张需另做受控干预。
- 没有执行AWM合成环境/长期记忆扩展。AWM锁定源码根目录未声明LICENSE，不将其源码并入本项目。
- JD量化匹配只表示能力覆盖，不代表录用概率或真实运行效果；外部依赖份额是作者估值（±3–5pp），代码比例是测量值。

## 下一步

1. 在本机.env配置Agent、用户、固定Judge接口；doctor后执行train的5任务真实API smoke，检查错误、Token与成本。
2. 人工校准Judge/Rubric，登记实际模型版本及预算，提交预注册；真实版本变动不得沿用不匹配的候选freeze。
3. 未修改的助手跑出 v1 轨迹。盲标测试并封存，同时盲标训练和开发。记下测试上的两列指标。
4. 按 EXPERIMENTS 第 12 章构建并筛选模拟题，只用于 v2、v3… 的训练侧。
5. 开发 20 上人和 Judge 已对齐且官方终态通过率不再上升，就停止。再到测试 40 跑最终版并另做盲标。
6. 记录真实结果与负结果。真实实验产物需脱敏后选择性发布。
