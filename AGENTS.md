# KVScope Agent Instructions

## 项目范围

KVScope 是一个面向 LLM 推理前内存估算、KV Cache 分析和部署可行性解释
的 Python 库与 CLI。当前仓库只完成 Phase 0：Repository Bootstrap。

Phase 0 不实现：

- 正式的权重、KV Cache、运行时开销或可行性计算；
- InferPilot 的任何功能或集成；
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
