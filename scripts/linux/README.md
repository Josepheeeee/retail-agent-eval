# Linux 脚本

在 H20 上按顺序使用。当前实验不包含 Judge 微调。

| 脚本 | 用途 |
|---|---|
| `install.sh` | 基础环境、τ editable、离线检查 |
| `install_infer.sh` | `.venv-infer`，vLLM 服务依赖 |
| `serve_vllm.sh` | 起 OpenAI 兼容服务；`MODEL`、`TP` 可配 |
| `run_smoke.sh` | 真实 API 五任务 smoke |
| `validate_results.sh` | pytest、pip check、compile、run 审计 |

示例：

```bash
bash scripts/linux/install.sh
bash scripts/linux/install_infer.sh
bash scripts/linux/run_smoke.sh
```

脚本不内置密钥、价格或“已完成”声明；缺少 `.env` 时明确停止。
