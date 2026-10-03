# KVScope

KVScope 是一个轻量、可解释的 LLM 推理内存估算与分析工具库，用于分析模型权重、KV Cache、硬件内存预算和推理后端运行时开销，并评估部署可行性。

## 当前状态

v0.1 的静态分析核心、Phase 10a/10b 校准、Phase 11 多目标对比和 Phase 12 workload sweep 已交付。仓库目前支持：

- 模型、硬件和后端 profile 解析；
- 权重、KV Cache、硬件预算和运行时开销估算，内部使用整数 bytes 并显式表达不确定性区间；
- 内存可行性评估、约束分析、安全 context/并发上限和推荐；
- `kvscope analyze` 端到端分析、`kvscope compare` 多目标对比和 `kvscope sweep` 单维 workload 扫描，支持 Terminal、JSON、Markdown 输出；
- 离线校准记录导入与估算误差比较；
- 显式 opt-in 的本地校准 runner、限定范围拟合和人工审核工件。

内置 vLLM 和 llama.cpp profile 是未校准的通用规划模板，结果应在目标模型、后端版本和硬件环境中验证。校准 runner 只执行用户在 manifest 中指定的本地 argv 命令；KVScope 不下载模型、不执行远程模型代码，也不自动修改或发布 backend profile。runner 无法替操作者建立网络隔离，运行外部命令前应自行确认其安全性。

Web UI、模型下载、推理服务集成、自动 profile promotion 和自动调优不在当前范围内。完整阶段状态和边界见 [实施计划](docs/IMPLEMENTATION_PLAN.md)；校准使用方法见[校准文档](docs/calibration.md)。

## 快速开始

```bash
uv sync --extra dev
uv run kvscope --version
uv run kvscope backend list
uv run kvscope analyze qwen-example \
  --hardware generic-discrete-16gib \
  --backend vllm \
  --parameter-count 4000000000 \
  --context 4096 \
  --recommend
```

当解析到的模型配置不含参数量时，`--parameter-count` 为必需参数。使用 `--format json` 或 `--format markdown` 可输出机器可读或便于分享的报告。

若要对比同一 workload 在多个硬件/backend profile 组合上的可行性，请使用 `kvscope compare`，详见[多目标对比文档](docs/deployment-comparison.md)。若要观察 context 或并发数变化对内存可行性的影响，请使用 `kvscope sweep`，详见[workload 扫描文档](docs/workload-sweep.md)。若要把完整 feasibility 报告与本地采集的峰值内存记录比较，请使用 `kvscope calibrate compare`。Phase 10b 的 `run`、`fit` 和 `review` 命令及其安全边界详见[校准文档](docs/calibration.md)。

## 开发质量检查

```bash
uv run ruff check .
uv run mypy src/kvscope
uv run pytest --cov=kvscope --cov-report=term-missing
uv run pre-commit run --all-files
```

贡献流程见 [CONTRIBUTING.md](CONTRIBUTING.md)。
