# KVScope

KVScope 是一个轻量、可解释的 LLM 推理内存与 KV Cache 分析工具，面向
不同模型、硬件和推理配置提供可追溯的内存估算。

> 当前已完成 Phase 5 模型配置解析。KVScope 不下载权重，也不执行远程模型代码。

## 当前状态

仓库已经提供：

- `resolve_model()`：解析显式配置、本地 JSON、Hugging Face 和内置 Registry；
- 支持 revision、缓存、offline 模式和架构适配器；

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
