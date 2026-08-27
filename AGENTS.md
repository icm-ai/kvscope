# KVScope Agent Instructions

## 项目范围

KVScope 是一个面向 LLM 推理前内存估算、KV Cache 分析和部署可行性解释
的 Python 库与 CLI。当前仓库已完成 Phase 0、Phase 1（Domain 与 KV Cache 估算引擎）及 Phase 4（Weight Engine）。


当前不实现：

- InferPilot 的完整集成；
- Web UI、模型下载、推理服务、benchmark 和自动调优。


## 编码规则

- 支持 Python 3.11+，使用 `src/kvscope` 的 src-layout。
- 运行时依赖保持轻量；不得添加 `torch`、`transformers`、vLLM、CUDA 或其他
  重量级依赖。
- 所有公开函数和类都必须有完整类型注解。
- 遵循现有模块边界：domain、resolvers、calculators、engines、registries、
  calibration 和 serialization。
- 内部内存表示使用整数 bytes；展示层再转换为 GiB/其他单位。
- 公式与经验数据分离；估算结果必须可以追溯到输入、公式、profile 和证据。
- 不执行远程模型代码，不把 UI 或推理后端耦合进核心库。
- 保持修改聚焦，不顺手重构无关代码。

## 完成标准

任何变更完成前必须：

1. 更新必要的单元或集成测试；
2. 运行 `ruff check .`；
3. 运行 `mypy src/kvscope`；
4. 运行 `pytest --cov=kvscope --cov-report=term-missing`；
5. 对配置、文档和公共 API 变更进行人工检查。

Phase 0 的完成标准是：包可安装和导入，`kvscope --version` 与
`kvscope --help` 可用，CI 配置执行上述质量门禁，且不包含正式业务逻辑。

<!-- BEGIN brain.md -->
## Project Brain

This project keeps a **Project Brain**: a persistent memory layer of its durable decisions, requirements, and constraints. Read `./BRAIN.md` for the full read/write contract.

Maintain the brain as part of normal coding work — not as a separate task. While discussing or implementing features:
- **Start of a task:** load relevant context with the `brain` CLI (`list-pages`, `read-page`, `read-root`). Prefer a narrow read over scanning everything.
- **When a decision, requirement, constraint, or durable insight settles** (in chat or while coding): capture it immediately via the `brain` CLI. Do not wait to be asked and do not batch it for later.
- **Pure implementation with no new decision:** do not write to the brain.
- **When overturning a prior conclusion:** update the page (`update-truth` and/or `append-timeline` with `kind: reversal`, or `archive-page`).
- Only store what will still matter in six months and is hard to reconstruct from the code alone.
- All reads and writes go through the `brain` CLI — never hand-edit brain files.

The brain skills (`brain-setup`, `brain-page`, `brain-ingest`, `brain-bootstrap`) are installed in your global skills directory. Prefer `brain init` to scaffold a new project.
<!-- END brain.md -->
