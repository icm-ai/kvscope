# KVScope (中文)

KVScope 是一个轻量、可解释的 LLM 推理内存估算与分析工具库，用于分析 KV Cache、模型权重、硬件内存预算以及推理框架运行时开销。

> Phase 6 提供了 Hardware Registry、Backend Profile 版本解析、硬件内存预算计算以及基于不确定性区间（`ByteRange` / `RatioRange`）的纯公式 Runtime Overhead Engine。不下载模型权重、不执行远程代码、不依赖 PyTorch / CUDA 运行时或推理后端。

## 当前支持功能

仓库目前支持：

- `resolve_model()`、`resolve_hardware_profile()`、`resolve_backend_profile()` 解析 API；
- `estimate_weight_memory()`、`estimate_kv_cache()`、`estimate_hardware_memory_budget()`、`estimate_runtime_overhead()` 计算 API；
- Hardware Registry 与 Backend Registry（包含 6 个通用硬件容量 Profile 及 vLLM / llama.cpp 通用模板）；
- 硬件非模型预留拆分（OS / Display / Background / Device / User）与可分配内存 Headroom 计算；
- 纯公式 Runtime Overhead 计算（Base Runtime, Parameter Scaled, Workspace, Graph Capture, Backend Buffers, Allocator Margin）；
- Terminal、JSON、Markdown 序列化渲染与 `kvscope hardware`、`kvscope backend`、`kvscope estimate-overhead` CLI 命令；
- 完整的 100% 类型注解、Ruff、mypy、Hypothesis 属性测试与 Golden Case 测试套件。

InferPilot、Feasibility 最终判断、Recommendation 引擎、推理服务集成、Web UI、Benchmark 和自动调优明确不在本阶段范围内。

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
kvscope --version
kvscope hardware list
kvscope backend list
kvscope estimate-overhead --backend vllm --hardware generic-discrete-16gib --weight-bytes 14000000000 --params 7000000000
```

## 开发质量检查

```bash
ruff check .
mypy src/kvscope
pytest --cov=kvscope --cov-report=term-missing
pre-commit run --all-files
```

详见 [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) 获取阶段规划，及 [CONTRIBUTING.md](CONTRIBUTING.md) 获取贡献指南。
