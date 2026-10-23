# 面向零售服务 Agent 的分层评测与失败归因驱动优化

以淘宝评测实践为流程参考，以 DeepAgents 为被测对象，以 τ-bench 零售任务为可执行环境。先看尺子是否和人一致，再看官方终态通过率是不是助手改出来的。

**当前：工程实现与离线闭环；真实 API 实验和人工金标尚未完成。不提供未经测量的提升数字。当前项目不包含 Judge 微调。**

## 项目目的

业务用途是零售服务 Agent 的发布前回归：在订单修改、取消、退换货中识别执行失败、未经确认写入、重复交易、回复失实和隐私违规，并判断修复能否泛化。

| 研究问题 | 主终点/证据 | 不声称 |
|---|---|---|
| 尺子是否可信？ | 测试 40 上 v1 与最终版的总体一致、逐层一致、误放行、最早错误 | 不把 Judge 自己的通过率当进步 |
| 助手是否改好了订单？ | 同一测试 40 的官方终态通过率 | 只改尺子时这个数应几乎不动；不预填收益 |

真实公司数据、流量分布和上线收益不在验证范围。

## 架构与职责

```mermaid
flowchart TB
  runV1["未修改的助手跑出轨迹"]

  subgraph sealed [测试：标完封存]
    direction TB
    labelTest["盲标测试轨迹"]
    recordV1["记下两列指标"]
    labelTest --> recordV1
  end

  subgraph loop [训练：迭代到水位不再升]
    direction TB
    labelTrain["盲标训练与开发轨迹"]
    draftSim["LLM 从训练父题起草模拟题"]
    screenSim["按顺序筛选并由人抽查"]
    fixRuler["先改清洗或尺子并重打"]
    fixAgent["终态仍为 0 才改助手"]
    nextVersion["得到 v2 或下一版"]
    stopDev{"开发集水位是否不再升"}
    labelTrain --> draftSim --> screenSim --> fixRuler --> fixAgent --> nextVersion --> stopDev
    stopDev -->|仍在升| draftSim
  end

  runV1 --> labelTest
  runV1 --> labelTrain
  stopDev -->|不再升| runFinal["测试上再跑最终版并另做盲标"]
```

这是轻量评测 Harness：管理版本、数据、执行、评分和产物。DeepAgents 是被测对象；τ 是业务环境。GEPA 代码还在，当前进步不看 A3−A2。第一版不建设 Web 平台，不做跨任务长期记忆，也不训练 Judge。STATE.md 服务于开发助手，不是被测模型的记忆。模拟题规则在 [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md) 第 12 章。

每条 `Grade` 除六层状态外，还保留 `error_type`、`earliest_error_event`、`attribution_uncertainty` 和每层 `support`（direct/inferred/none）。无法定位时允许 `unclassified`/`null`/high，不强迫模型编造根因；若给出最早错误事件，必须能在该层证据中找到。报告把官方环境结果、LLM 判断、人工金标和教师标签分开，避免把“人工标签”压缩成只有一个总体结论。

```text
configs/       固定模型行为、预算、实验组与随机种子
prompts/       Agent、Judge、反思指令，互相独立
rubrics/       六层业务规则的唯一来源
src/retail_eval/
  schema.py    Trace / Event / Grade与证据契约
  data.py      清洗、任务划分与盲标
  agent.py     DeepAgents ↔ τ业务工具与会话适配
  judge.py     兼容模型API、严格JSON与证据校验
  optimize.py  正常GEPA及分层反馈/消融适配
  report.py    指标、成本、配对Bootstrap与图表
  run.py       统一CLI及快照、冻结、异常记账
scripts/       固定commit参考源码获取
data/fixtures/ 9条自制固定样例，仅用于工程验证
data/manifests/任务来源哈希及54/20/40划分
external/      五个上游源码树，忽略Git
runs/          自动实验产物，忽略Git
docs/          实验、引用、贡献及项目状态
tests/         契约、隔离、统计、GEPA和τ适配检查
```

## 快速开始：离线入口

本机环境与参考源码已经建立，下一步先读[真实五任务操作指南](docs/NEXT_STEPS.md)，配置.env并验收接口；无需重新搭建文件夹。原批准计划已归档到[PLAN.md](docs/PLAN.md)，每一项的实现位置、验证证据和待执行内容见[PLAN_CHECKLIST.md](docs/PLAN_CHECKLIST.md)。**“工程入口齐备”不等于“真实研究实验完成”。**

```powershell
Set-Location C:\Users\33969\Documents\retail-agent-eval
$py = Join-Path $PWD '.venv\Scripts\python.exe'
& $py -m retail_eval.run doctor
& $py -m retail_eval.run demo
```

然后按操作指南填写模型角色，运行`collect --split train --group A0 --limit 5 --trials 1`，核对5条记录与benchmark_complete；允许业务失败，不允许用缺失评分或接口异常冒充完成。

| 交付内容 | 阅读位置 |
|---|---|
| 工程、快速开始与命令 | 本文件、[AGENTS.md](AGENTS.md) |
| 批准计划归档、逐项验收 | [PLAN.md](docs/PLAN.md)、[PLAN_CHECKLIST.md](docs/PLAN_CHECKLIST.md) |
| 下一步具体操作与实验登记 | [NEXT_STEPS.md](docs/NEXT_STEPS.md)、[PREREGISTRATION.md](docs/PREREGISTRATION.md) |
| 完整参考项目与论文对应关系 | [REFERENCES.md](docs/REFERENCES.md)、[引用锁](references.lock.yaml) |
| 目的、假设、主实验/消融/Judge/统计与验收 | [EXPERIMENTS.md](docs/EXPERIMENTS.md) |
| 个人改进与创新证据边界 | [CONTRIBUTIONS.md](docs/CONTRIBUTIONS.md) |
| 项目记忆、已验证事实与下一步 | [STATE.md](docs/STATE.md) |
| 70 条 JD 原文、30 家公司来源清单与能力映射 | [JD_RAW.md](docs/JD_RAW.md)、[jd_sources.json](data/manifests/jd_sources.json)、[JD_ANALYSIS.md](docs/JD_ANALYSIS.md) |
| 70 条 JD 的能力匹配、差距与外部依赖盘点 | [JD_FIT.md](docs/JD_FIT.md)、[jd_fit.json](data/manifests/jd_fit.json)、[分析脚本](scripts/analyze_jd_fit.py) |

## 快速开始：完整安装与离线闭环

Windows PowerShell、Python **3.12**。下面命令在项目根目录逐行执行。已有.venv时从设置`$py`开始，无需激活脚本或修改执行策略。

```powershell
Set-Location C:\Users\33969\Documents\retail-agent-eval
py -3.12 -m venv .venv
$py = Join-Path $PWD '.venv\Scripts\python.exe'
& $py -m pip install -r requirements.lock.txt
& $py scripts/fetch_references.py
& $py -m pip install --no-deps --no-build-isolation -e external/tau-bench -e .
& $py -m pip check
& $py -m retail_eval.run prepare-data
& $py -m retail_eval.run doctor
& $py -m pytest -q
& $py -m retail_eval.run demo
```

锁文件来自Python3.12/Windows amd64的实际兼容环境，冻结运行依赖；tau2通过锁定源码以editable方式单独安装，因此lock没有本机绝对路径。构建工具由PEP517隔离环境安装。迁移到Linux/GPU训练环境需另行验证并保留单独lock，不能假定本地锁等同于远端训练依赖。

demo输出一个带时间与随机后缀的runs目录，包括原始/清洗后轨迹、分层Grade、JSON/CSV/Markdown报告、diagnostics.png。每处明确标记fixture、no-model、不代表性能结果。再次运行创建新目录，不覆盖前次产物。

## 配置真实模型并跑五任务

```powershell
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
```

在本机编辑.env，填写API_KEY（或各角色API_KEY）、包含`/v1`的端点、AGENT_MODEL、USER_MODEL、JUDGE_MODEL；优化时再填REFLECTION_MODEL。支持OpenAI兼容Chat Completions；Agent必须支持tool calls，Judge需支持JSON object。不要把密钥发到聊天里或写进YAML。ChatGPT/Codex订阅与本地模型API配置分开管理，doctor只检查此工程的角色配置。

商业/远程端点还需在`configs/experiment.yaml`的`budget.max_task_runs`登记本次批量最多任务运行数（0表示仅本地），并填写输入/输出价格（可填0）；未登记或未填价格时批跑直接停止。价格字段只用于成本报告，实际调用/Token/耗时写入run manifest；服务端不返回usage时记为未知。

```powershell
& $py -m retail_eval.run doctor
& $py -m retail_eval.run collect --split train --group A0 --limit 5 --trials 1
```

五任务用于验证端点、业务工具、状态重置、官方评分和Judge输出。记录中的执行error、parse_error或缺失reward必须先查清，再开始批跑。脚本模型的离线集成检查不能替代这个真实API验收。

运行快照不包含API密钥。Agent只获得政策、业务工具和当前任务会话，不能读取本地开发文件或评分答案。τ的默认开场白属于当前任务初始历史，保留它不等于跨任务记忆。

## 保留的 GEPA 命令

当前实验顺序在 [docs/NEXT_STEPS.md](docs/NEXT_STEPS.md) 第 5 节：先测 v1，再按 EXPERIMENTS 第 12 章做模拟题，水位看开发 20，进步只在测试 40 上比。下面的命令仍可用，不作为当前进步。

先在[实验预注册](docs/EXPERIMENTS.md)中登记实际模型版本、预算与选择规则。

实际登记填写[PREREGISTRATION.md](docs/PREREGISTRATION.md)，A1过程填写[manual_revision.md](docs/manual_revision.md)。两者当前均为空模板，不代表实验已经开始或完成。

```powershell
# A0开发集（20任务）
& $py -m retail_eval.run collect --split dev --group A0 --trials 1

# A1：复制并人工编辑，记下最多20任务/2小时的修改过程
Copy-Item prompts/agent.md prompts/agent_manual.md
& $py -m retail_eval.run collect --split dev --group A1 --trials 1 --prompt prompts/agent_manual.md

# 自动优化；42/43/44分别运行，A2与A3使用相同设置
& $py -m retail_eval.run optimize --group A2 --seed 42
& $py -m retail_eval.run optimize --group A3 --seed 42
& $py -m retail_eval.run optimize --group A3_no_layer --seed 42
& $py -m retail_eval.run optimize --group A3_no_evidence --seed 42
```

A2获得轨迹与正常自然语言规则/原因/证据反馈；A3将相同信息按层级组织。每次最多150次任务评分，包括dev与候选比较，实际调用写metric_ledger。只修改Agent提示词，评分协议固定；不读取test。普通GEPA已经有文字反思，这个项目检验分层组织能否带来额外收益。

用输出的真实目录替换下列占位路径；冻结只能基于完整且无基础设施异常的20任务dev评分，优化时自动选择完整dev均值最好的候选，同分取最早。

```powershell
$candidateRun = 'runs/替换为A3种子42的优化目录'
& $py -m retail_eval.run freeze --run $candidateRun
& $py -m retail_eval.run collect --split test --group A3 --optimization-seed 42 --frozen "$candidateRun/frozen_candidate.json"
```

A0/A1也先freeze其完整dev运行；测试时`--group A0`或A1，不传optimization-seed。测试固定全部40任务×3trial，不支持截取后当正式结果。更换模型/代码/评分协议后需重新进行相应dev验证与冻结。第二模型使用单独.env/角色配置重跑A0/A2/A3，独立呈现。

```powershell
# 合并同一模型、协议下的完整测试版本表
& $py -m retail_eval.run aggregate --runs runs/A0测试目录 runs/A1测试目录 runs/A2种子42测试目录 runs/A3种子42测试目录

# 正式主要比较：把每组42/43/44三种子的测试目录都传入
& $py -m retail_eval.run compare --a runs/A2种子42测试目录 runs/A2种子43测试目录 runs/A2种子44测试目录 --b runs/A3种子42测试目录 runs/A3种子43测试目录 runs/A3种子44测试目录
```

aggregate生成版本表、官方评分成分、失败分布与成本；compare生成任务/种子配对Bootstrap差值与95%CI，保留同任务三trial关联。不同模型或协议不能混算。单种子比较会标注无法估计优化随机性，不能代替预注册三种子主实验。

## 人工金标

目标 train 240、dev 80、test 160。先建立对应划分的轨迹池；不足配额时不能用 fixture 或 teacher 标签冒充人工样本。annotation-export 按任务和结果分层抽样，标注者只收到盲包，不收到旁置 mapping 文件和自动评分。模拟题怎么构建、怎么筛选，见 [EXPERIMENTS.md 第 12 章](docs/EXPERIMENTS.md)。模拟题不进入开发水位，也不进入测试 40。

```powershell
& $py -m retail_eval.run pool --runs runs/替换为A0训练采集目录 runs/替换为A1训练采集目录 --output data/raw/train_pool.jsonl
& $py -m retail_eval.run annotation-export --traces data/raw/train_pool.jsonl --count 240 --output data/annotations/train_packets.jsonl
```

pool只合并单一live划分的完整采集run，拒绝重复trace_id并保存输入manifest哈希；执行异常从标注池排除但记载数量。A0训练集三trial只有162条，需采集其他已登记版本才能满足240条人工目标；不足时不要重复复制轨迹凑数。dev/test同理各自建池，test只用冻结后的正式轨迹。

逐条将annotation的null替换为人工Grade内容（不含trace_id/judge_version），填写overall、六层状态/规则/理由/证据/支持类型、cause、error_type、earliest_error_event、attribution_uncertainty、confidence及必要建议。参照data/fixtures/labels.json的结构；人工真值只允许pass/fail/abstain，不能以parse_error代替标注。每条事件证据必须存在；无法确定时允许 `unclassified` + `null` + high，不强迫写根因。

每个packet的 `review` 必须填写 `reviewer_id`、`round` 和 `status`（first/recheck/adjudicated）；导入时写入 `annotation_sha256`。至少20%轨迹做间隔复核/重标，分歧保留裁决记录。人工金标原始版本、复核与裁决记录单独保存；报告同时给出总体、六层维度、最早错误事件/轮次、证据支持率，而不是只保留总体结论。

```powershell
& $py -m retail_eval.run annotation-import --packets data/annotations/train_packets.jsonl --mapping data/annotations/train_packets.mapping.json --output data/annotations/train_gold.jsonl
```

只有 `label_source=human` 进入一致率。teacher 行不能算进这份一致率。dev 和 test 的人标同样导入，测试标签标完封存。

## 固定 Judge

当前只用一个 Judge 角色。不对同一批轨迹做 J0–J4。

```powershell
& $py -m retail_eval.run judge --traces data/raw/train_pool.jsonl --role judge --version layered-v1

# 对既有 run 添加独立金标分析
& $py -m retail_eval.run report --run runs/替换为Judge目录/layered-v1 --gold data/annotations/train_gold.jsonl

# 语义保持的冗长干扰一致性检查（同一 Judge、同一轨迹事实，仅重述最终回复）
& $py -m retail_eval.run judge-robustness --traces data/raw/train_pool.jsonl --role judge --version verbosity-v1
```

有金标时生成总体一致、逐层一致、误放行、最早错误事件和覆盖率。没有金标时不输出伪造准确率。解析失败和接口异常分别统计。测试 40 的人标不拿回来改提示词或 Rubric。

## 产物位置与异常

每次run保存manifest、代码/依赖版本、输入与配置快照，raw执行、官方评分和原始Judge回复，清洗记录、分层Grade和报告。error保留类型及可用执行轨迹，避免将基础设施故障算为正常业务失败。官方NL遗漏断言/返回非布尔值时标记异常；这是格式完整性校验，不修改业务奖励定义。

优化另有候选、反思、metric_ledger、GEPA状态、selected_prompt.md和optimization.png。开发曲线不是测试曲线。正式比较拒绝未完成运行；中断后保留原run，修复后创建新run，当前版本不自动断点续跑。runs默认不提交Git，公开结果时另行脱敏并选择性导出。

## 当前状态

当前已验证：固定样例闭环、无泄漏任务划分、真实 DeepAgents SDK 与零售工具往返、五个官方任务的脚本模型端到端适配、评分中断保留轨迹、错误类型与最早事件契约、人工完整标签保留、维度与定位指标、冗长干扰检查、JD 来源与量化匹配。**真实 API 五任务、v1 轨迹、人工 480 标注和模拟题都还没做。**具体测试结果和运行记录见 [STATE.md](docs/STATE.md)。

## GitHub

公开仓库：[Josepheeeee/retail-agent-eval](https://github.com/Josepheeeee/retail-agent-eval)（`main`）。external、.venv、runs、.env、私有原始数据和权重均忽略跟踪；公开的是代码、可分发自制fixture、来源清单和研究协议。推送身份为 `Josepheeeee`，提交前已做凭证样式字符串扫描。上线真实运行后，结果报告需另行脱敏和选择性导出，不能直接把含用户信息的私有轨迹提交。
