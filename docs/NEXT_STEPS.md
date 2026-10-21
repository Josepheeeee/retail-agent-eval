# 下一步操作：从本机工程到真实五任务验收

你现在位于**离线工程已验证、真实模型实验未开始**的阶段。先完成本页，再按根README进行主实验。完整目标见[PLAN.md](PLAN.md)，哪些完成见[PLAN_CHECKLIST.md](PLAN_CHECKLIST.md)。

## 1. 使用已经创建的环境

在PowerShell逐行执行；当前机器已有.venv和参考源码，无需重新安装、重新克隆或重建划分。

```powershell
Set-Location C:\Users\33969\Documents\retail-agent-eval
$py = Join-Path $PWD '.venv\Scripts\python.exe'
& $py --version
& $py -m pip check
& $py -m retail_eval.run doctor
& $py -m retail_eval.run demo
```

预期：Python3.12；pip无冲突；doctor显示数据可用；demo最后一行给出新的runs目录。打开该目录中的`report/report.md`、`report/diagnostics.png`；它们明确是fixture工程示例，不是模型能力结果。首次换一台机器安装时，使用[根README的安装步骤](../README.md)。

## 2. 在本机填写模型接口

仅当.env不存在时复制示例，避免覆盖已有密钥：

```powershell
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
```

本机编辑.env，第一阶段只需配置前三个模型角色：

| 字段 | 填写内容 | 何时需要 |
|---|---|---|
| API_BASE_URL | 实际OpenAI兼容Chat Completions服务地址，通常含/v1 | 五任务前 |
| API_KEY | 该模型服务自己的密钥；本地服务按自身要求配置 | 五任务前 |
| AGENT_MODEL | 服务端存在的模型ID，支持工具调用 | 五任务前 |
| USER_MODEL | 用户模拟模型ID，支持官方角色指令 | 五任务前 |
| JUDGE_MODEL | 固定评分模型ID，支持JSON object输出 | 五任务前 |
| REFLECTION_MODEL | GEPA反思模型ID | 运行A2/A3前 |
| SMALL_BASE_MODEL / SMALL_SFT_MODEL / STRONG_MODEL | 原始小Judge、SFT权重及固定强参照 | Judge实验前 |

前三个角色可共享同一服务，也可用`AGENT_BASE_URL/AGENT_API_KEY`等角色字段分别配置。`SMALL_BASE_BASE_URL`等名称按.env.example原样填写。不要把占位符当作有效模型ID，不向聊天发送密钥，也不把.env加入Git。

配置后再运行doctor。第一阶段只要求agent/user/judge不再显示not configured；reflection和三个Judge实验角色暂时未配置不影响五任务。

## 3. 跑五个真实零售任务

```powershell
$smokeOutput = & $py -m retail_eval.run collect --split train --group A0 --limit 5 --trials 1
if ($LASTEXITCODE -ne 0) {
    throw '五任务命令未正常结束，请先检查终端错误。'
}
$smokeOutput
$smokeRun = ($smokeOutput | Select-Object -Last 1).Trim()
$manifest = Get-Content -LiteralPath "$smokeRun/manifest.json" -Raw | ConvertFrom-Json
$summary = Get-Content -LiteralPath "$smokeRun/report/summary.json" -Raw | ConvertFrom-Json
$manifest | Select-Object status, benchmark_complete, expected_records
$summary.versions | Format-Table version, n, official_outcomes_known, judge_pass, judge_fail, abstain, parse_error, error
```

五任务接口/工程验收要求：

- manifest的status为complete、benchmark_complete为true、expected_records为5。
- versions中n=5，official_outcomes_known=5，parse_error=0、error=0；raw和五条trace可回查。
- 复核一次模型工具调用→τ执行→工具回包→最终回复，确认没有双重写入和跨任务状态。
- 记录真实Token是否可用、总耗时及接口错误；若服务不提供usage，保留未知并另查服务账单。

**official_reward=0可以是正常的业务失败，不意味着工程没跑通；benchmark_complete=true也不表示五个任务全部成功。**同样，Judge的fail或abstain是有意义的判定，不需要为了“跑绿”修改答案。

若存在parse_error、error或reward缺失，先看`grades.jsonl`、`raw/*.judge.json`、`raw/*.execution.json`和`raw/*.error.json`。当前只保存异常类型及可用轨迹，部分错误仍需结合本机终端日志和服务日志定位。修复后生成新run，不覆盖旧记录；不要进入正式实验后才更换评分协议。

## 4. 登记协议与五任务验收结果

填写[PREREGISTRATION.md](PREREGISTRATION.md)：真实模型/权重ID、端点版本说明（无密钥）、配置路径、Rubric与提示词版本、预算和选择规则，以及五任务run路径/结果。未填写前保持“草稿”，不能声称已完成预注册。

人工检查Judge与业务规则；确认需要调整时只使用train/dev。调整完成后固定评分协议，并更新STATE.md。A1人工修订使用[manual_revision.md](manual_revision.md)记录，最多20个dev任务、2小时；空模板不算实际完成修订。

## 5. 按顺序开展实验

| 顺序 | 操作 | 应留下的产物 | 详细入口 |
|---|---|---|---|
| 1 | A0/A1完整dev，记录人工修订 | dev运行、人工记录 | 根README“基线、GEPA与最终测试” |
| 2 | A2/A3及两消融，各42/43/44 | 最多150调用/优化run、候选、反思、dev曲线 | optimize命令、EXPERIMENTS第5–6部分 |
| 3 | 按完整dev选择候选并freeze | frozen_candidate.json | freeze命令 |
| 4 | 各候选全部40×3测试 | 120条/候选、官方组成与Judge结果 | collect --split test |
| 5 | 第二模型独立运行A0/A2/A3 | 第二模型自己的dev/freeze/test | 只更换Agent角色，固定其他角色 |
| 6 | 建各划分池，盲标240/80/160 | pool/抽样清单、人类标签和复核记录 | pool、annotation-export/import |
| 7 | train-only导出、远端SFT并接回 | JSONL及来源、训练记录、模型接口 | export-sft；本地不训练 |
| 8 | 固定轨迹运行J0–J4 | 独立金标混淆、覆盖率/成本 | judge-matrix --gold |
| 9 | 合并方法表与配对比较 | aggregate报告、A3−A2差值/95%CI、真实结论 | aggregate、compare |

train/dev人工金标可在基线采集后先做；test金标必须在候选冻结后，且不回流优化。Judge实验始终固定轨迹，不能中途替换Agent主实验的评分器。

## 6. Git与发布

当前文件已暂存，但本机没有提交者姓名/邮箱，也没有目标remote。若准备提交，在本仓库用你真实的Git身份设置；以下占位值必须替换，邮箱可使用你已有的GitHub noreply邮箱。

```powershell
git config --local user.name '替换为你的Git提交姓名'
git config --local user.email '替换为你的Git提交邮箱'
git diff --cached --stat
git status --short
git commit -m 'Build retail agent evaluation foundation and experiment protocol'
```

之后在GitHub确定目标仓库及可见性，核对授权再添加remote与push；本工程未自动创建远端或公开原始轨迹。原计划中“源码/配置可分发”与“原始模型轨迹可公开”是两项不同的验收，发布前仍需按来源和隐私检查。

第一项实际待办是**配置本机模型API并完成第3节**，不是重新建设文件夹。完成后把真实run与状态更新到STATE.md和PLAN_CHECKLIST.md。
