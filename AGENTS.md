# 项目约定

本项目研究“面向零售服务 Agent 的分层评测与失败归因驱动优化”。开始工作时先读本文件、README.md、docs/STATE.md 和 docs/PLAN_CHECKLIST.md；结束工作时更新 STATE.md 中的已验证事实、限制及下一步。

docs/PLAN.md保存批准计划，docs/PLAN_CHECKLIST.md是逐项验收，docs/NEXT_STEPS.md指导当前阶段操作。模板、入口、fixture、脚本模型检查不能替代真实实验；只有可追溯结果齐备后才勾选相应实验完成。

## 实验纪律

- 被测 Agent 使用 DeepAgents；τ-bench 固定 v1.0.1。工程代码保持薄适配，按职责解耦。
- 原始轨迹不可改写。清洗、评分、优化必须生成新产物并记录输入哈希。
- train/dev/test 按任务及 parent_task_id 分组。优化、候选选择、SFT 导出禁止读取 test。
- 开发文档、评分标签、目标数据库和参考答案不得暴露给被测 Agent。
- 每个任务、trial 使用新的会话和环境，禁用跨任务记忆。仅开放业务工具。
- Agent 实验固定 Judge；Judge 实验固定轨迹。环境检查、官方评分、人工金标、教师标签分开记录。
- 证据不足是 abstain；解析失败是 parse_error；基础设施异常是 error。均不得默认通过。
- 不制造提升数字，不把 fixture/demo 当作真实模型实验。报告负结果及缺失运行。
- A2 正常获得自然语言反馈与轨迹；A3 只改变反馈组织。仅优化 Agent 提示词。
- 密钥只放 .env，禁止提交原始私密数据、模型权重及含秘密的配置快照。

## 工程要求

Python 3.12。运行 `python -m pytest`；离线闭环运行 `retail-eval demo`。
新增行为需检查数据隔离、标签语义及可复现性；不为文档和简单配置增加镜像式测试。
Rubric 唯一来源为 rubrics/retail.yaml。提示词位于 prompts/。入口为 retail-eval。
参考源码位于 external/，不提交；版本由 references.lock.yaml 固定。
STATE.md 是开发项目记忆，不是被测 Agent 的记忆，不传给模型。
