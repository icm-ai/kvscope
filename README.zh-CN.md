# KVScope

KVScope 是一个轻量、可解释的 LLM 推理内存与 KV Cache 分析工具，面向
不同模型、硬件和推理配置提供可追溯的内存估算。

> 当前为 Phase 0 仓库初始化阶段。正式的计算和分析 API 尚未实现，不能
> 根据当前版本推断任何内存估算结果。

## 当前状态

仓库已经提供：

- Python 3.11+ `src/` 项目布局；
- 可安装的 Python 包和 CLI 入口；
- domain、resolver、calculator、engine、registry、calibration、
  serialization 模块边界骨架；
- pytest、coverage、mypy、ruff、pre-commit 和 GitHub Actions 配置。

InferPilot、模型下载、推理服务、Web UI、benchmark 和自动调优均不在
当前范围内。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
kvscope --version
kvscope --help
```

## 开发检查

```bash
ruff check .
mypy src/kvscope
pytest --cov=kvscope --cov-report=term-missing
pre-commit run --all-files
```

详见 [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) 和
[CONTRIBUTING.md](CONTRIBUTING.md)。
