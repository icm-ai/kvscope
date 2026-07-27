# Contributing to KVScope

感谢参与 KVScope。当前项目处于 Phase 0，贡献应保持在仓库初始化和后续
实现计划允许的范围内。

## 范围约束

- 不引入 `torch`、`transformers`、vLLM、CUDA 或其他重量级运行时依赖。
- 不实现 InferPilot 功能、Web UI、模型下载、推理服务、benchmark 或自动调优。
- 优先使用标准库和已有依赖；新增依赖必须说明必要性。
- 公式、经验参数和外部数据必须可追溯，并与展示层分离。
- 所有公开 Python 函数和类必须有完整类型注解。

## 开发流程

1. 从 `main` 创建主题分支。
2. 保持修改聚焦，并为行为变化添加测试。
3. 在提交前运行：

   ```bash
   ruff check .
   mypy src/kvscope
   pytest --cov=kvscope --cov-report=term-missing
   pre-commit run --all-files
   ```

4. 提交说明应清楚描述变更目的和验证结果。
5. Pull request 应说明范围、设计决策、测试命令和已知限制。

## 代码风格

项目使用 Ruff 进行 lint 和格式检查，使用 mypy 进行严格类型检查，使用
pytest 编写测试。内部内存单位统一使用 bytes 的设计将在 Domain + Formula
阶段落地。
