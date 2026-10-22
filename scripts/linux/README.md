# Linux 脚本

在 H20 上按顺序使用；训练与推理使用不同 venv。

| 脚本 | 用途 |
|---|---|
| `install.sh` | 基础环境、τ editable、离线检查 |
| `install_train.sh` | `.venv-train`，Judge SFT 依赖 + 固定 commit 的 LlamaFactory |
| `install_infer.sh` | `.venv-infer`，vLLM 服务依赖 |
| `serve_vllm.sh` | 起 OpenAI 兼容服务；`MODEL`、`TP`、`ADAPTER` 可配 |
| `train_judge.sh` | 四卡 LoRA；参数来自 `retail-eval judge-sft-config` |
| `run_judge_matrix.sh` | 固定轨迹 J0–J4 与人工金标 |
| `run_smoke.sh` | 真实 API 五任务 smoke |
| `validate_results.sh` | pytest、pip check、compile、run 审计 |

示例：

```bash
bash scripts/linux/install.sh
bash scripts/linux/install_train.sh
bash scripts/linux/install_infer.sh
MODEL=Qwen/Qwen3-4B scripts/linux/serve_vllm.sh 8000
TRACES=data/raw/frozen_judge_test_pool.jsonl GOLD=data/annotations/test_gold.jsonl \
  bash scripts/linux/run_judge_matrix.sh
```

脚本不内置密钥、价格或“已完成”声明；缺少 `.env` 或人工金标时明确停止。
