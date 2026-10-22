# 项目状态与开发记忆

更新时间：2026-10-21（Asia/Shanghai）。工程基座与实验协议已落地；真实模型研究结果仍待执行。

## 本轮计划核对

- 批准计划完整归档：docs/PLAN.md；逐项状态、文件证据与阶段验收：docs/PLAN_CHECKLIST.md。
- README顶部新增当前阶段入口，docs/NEXT_STEPS.md给出使用现有环境、配置接口、五任务运行与结果核对、后续实验顺序和Git准备。
- docs/PREREGISTRATION.md与docs/manual_revision.md为待填写模板；不是已经完成的正式登记或人工实验。
- 本轮重新运行pytest：**37 passed，1个上游audioop弃用warning，约13秒**；pip check无依赖冲突。
- 本轮机器核对：34个必需文件存在、6个参考源码commit匹配且tracked文件干净、train54/dev20/test40共114个唯一任务；本轮新增文档链接检查结果记录在data/manifests/plan_audit.json。
- doctor仍显示全部模型角色未配置；未发现完整正式优化run或正式test run。人工标注、SFT和研究结论不得标为完成。
- 当前验收范围是工程/文档/离线闭环。整体研究计划明确标为未完成；下一阶段是配置接口并取得5任务真实API验收记录。

## 已确定的决策

- 独立目录与 Git：retail-agent-eval，Python 3.12。
- DeepAgents 负责生成业务操作，τ-bench 唯一执行工具并重置环境。
- GEPA 使用独立包的公开 Adapter API；DSPy 作为参考实现与方法对照，不另写重复优化器。
- Agent 只看到业务政策、零售工具与会话；开发记忆、答案、评分和测试反馈不传入。
- 分层 Rubric 是诊断协议；官方任务奖励单独保存。
- 固定 train54/dev20/test40，盐 retail-eval-v1；同源扩充跟随父任务。
- 仅优化提示词；不做跨任务长期记忆，不在本地训练模型。
- 先保证本地闭环，真实任务与人工校验需要配置模型接口后执行。

## 已实现与已验证

- 目录、独立Git、Python3.12.10 .venv、135个冻结运行依赖、提示词/Rubric/配置分离。
- 六个完整参考源码树均按references.lock.yaml固定commit获取；上游tracked文件无修改。DeepAgents/GEPA/DSPy运行包另以requirements.lock.txt固定，源码HEAD不冒充安装包版本。
- data/manifests/splits.json已生成：train54/dev20/test40，哈希盐retail-eval-v1，官方114任务无重叠遗漏。
- Trace/Event/Grade契约、原始轨迹持久化、清洗追溯、六层顺序/并行逻辑、真实event证据引用验证。
- DeepAgents业务工具过滤、τ工具节点中断与单次执行、每任务环境和会话重置。发现并修正了τ默认开场白的初始历史兼容问题。
- GEPA公开Adapter、正常自然语言反馈/分层反馈/两个消融、150次硬预算、调用台账、候选提示和反思记录、完整开发集选择及冻结。
- 批量收集、单一划分轨迹池、盲标导入/导出、train-only SFT及来源sidecar、J0–J4固定轨迹评分入口。
- 版本表、成本及已知/缺失usage、官方评分成分、pass³、失败分布、混淆矩阵/同覆盖率分析、任务/种子配对Bootstrap、消融/第二模型的独立运行协议。
- Grade新增error_type、earliest_error_event、attribution_uncertainty和逐层support；最早事件必须可见且被证据引用，unclassified/unknown不被强迫编造根因。
- 人工标注导入保留六层标签、错误类型/位置、证据支持与review记录；报告新增总体+维度一致率、最早事件/轮次/层定位、错误类型准确率、ECE/Brier和证据直接支持率；`judge-robustness`增加语义保持的冗长重述一致性检查；teacher只作训练摘要。
- Judge SFT默认Qwen3-4B非思考、LoRA rank32/alpha64/lr1e-4/global batch16/len4096/1 epoch、种子42/43/44；`judge-sft-config`导出LlamaFactory配置，导出上限2,000条不同轨迹并报告实际数量。
- 新增`docs/JD_ANALYSIS.md`、`data/manifests/jd_sources.json`（30家公司）与`jd_review.json`（70条逐项分类/能力标签）；6家缺失公司已重新检索并记录URL与结论。
- README复现命令；REFERENCES完整项目/论文映射；EXPERIMENTS完整预注册与480盲标计划；CONTRIBUTIONS复现/个人实现/创新证据边界。
- 用户新增的Agentic CLEAR、AgentEval、AgentDebug、Who&When已访问官方论文页核验并加入REFERENCES与引用锁，同时更新实验和创新边界。未宣称已实现DAG根因分析或证明六层划分最优。

## 验证记录

| 检查 | 结果 |
|---|---|
| `.venv/Scripts/python.exe -m pytest -q` | **37 passed**；唯一warning来自τ语音模块导入的Python audioop弃用提示，当前文本实验通过 |
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

测试覆盖还包括：虚构证据拒绝、前层阻断后RED仍判定、同源泄漏拒绝、test/dev/fixture不能导出SFT、teacher与human来源区别、固定覆盖率防弃判取巧、三trial配对/缺失拒绝、GEPA公开API实际离线调用、预算不超额、冻结协议绑定、轨迹池去重及异常对账。没有真实API调用或人工金标性能数字。

## 当前限制

- 尚无已配置的模型 API；没有真实模型提升结果。
- 人工 480 条标注、正式优化、消融、第二模型和 Judge SFT 均待实验执行。
- 已配置仓库本地Git身份并推送到公开仓库`Josepheeeee/retail-agent-eval`（`main`）；早期“未提交/未推送”的记录已过时。
- 公开内容不含密钥、私有轨迹、权重或运行结果；真实实验产物仍需脱敏后单独发布。
- 没有自动断点续跑；失败/中断run保留，修复后创建新run并记录重跑成本。
- 证据ID存在的校验不等同于语义正确；cause是候选归因，仍需人工复核/修复重跑，严格因果主张需另做受控干预。
- 没有执行AWM合成环境/长期记忆扩展。AWM锁定源码根目录未声明LICENSE，不将其源码并入本项目。

## 下一步

1. 在本机.env配置Agent、用户、固定Judge接口；doctor后执行train的5任务真实API smoke，检查错误、Token与成本。
2. 人工校准Judge/Rubric，登记实际模型版本及预算，提交预注册；真实版本变动不得沿用不匹配的候选freeze。
3. 运行A0/A1开发集与A2/A3及消融42/43/44，完整dev选择/冻结，再跑40×3测试和第二模型。
4. 建立各划分轨迹池，盲标train240/dev80/test160；test只在冻结后标注，不回流优化。
5. 导出训练集，远端SFT后接回SMALL_SFT模型，执行固定轨迹J0–J4及独立金标分析。
6. 记录真实结果与负结果；工程代码已推送，真实实验产物需脱敏后选择性发布，并与基座项目分别提交。
