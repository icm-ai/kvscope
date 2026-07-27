# KVScope v0.1 Implementation Plan

本文档把产品和架构文档中的 v0.1 拆分为可独立验收的阶段。当前只完成
Phase 0；后续阶段不应在本次仓库初始化中提前实现。

## Phase 0：Repository Bootstrap — 已完成

验收标准：

- Python 3.11+ src-layout 和 `pyproject.toml` 可安装；
- `src/kvscope` 建立稳定的模块边界；
- `kvscope --version` 和 `kvscope --help` 可运行；
- pytest、pytest-cov、mypy、ruff、pre-commit 和 GitHub Actions 已配置；
- 单元、集成、golden、fixtures 测试目录存在；
- README、贡献指南、安全政策和 Apache-2.0 许可证齐全；
- 不包含正式内存估算逻辑，不包含 InferPilot 功能。

## Phase 1：Domain + Formula

交付内容：

- `ModelSpec`、`HardwareSpec`、`BackendSpec`、`InferenceConfig` 等不可变边界模型；
- dtype 与单位转换；
- 权重内存、KV Cache、block 对齐、运行时开销和系统预留计算；
- 明确 batch、active sequences、GQA/MQA/MHA 语义；
- 公式单元测试、属性测试和典型 golden 输入。

独立验收：给定手工模型配置和硬件配置时，所有组件输出整数 bytes、公式可
审查，且覆盖率和单调性测试通过。

## Phase 2：Resolvers + Registry

交付内容：

- 本地 `config.json` 解析；
- Hugging Face config 解析（默认不下载权重、不执行远程代码）；
- LLaMA、Qwen、DeepSeek Dense 与 generic adapter；
- 模型、硬件、后端 YAML profile registry；
- schema、单位、ID 唯一性和引用完整性校验；
- 离线模式与缓存边界。

独立验收：提供本地输入或 registry ID 时，resolver 返回标准 domain 对象；
无数据或字段不一致时返回可操作错误，不静默猜测。

## Phase 3：Decision + Reports + CLI

交付内容：

- feasibility、constraints、confidence 和 recommendations 引擎；
- feasible/tight/infeasible/unknown 结论与可解释建议；
- JSON 事实源、Terminal 和 Markdown 渲染；
- `inspect`、`estimate`、`fit`、`compare`、报告渲染等 CLI 子命令；
- 稳定的 `kvscope.api` 公共入口。

独立验收：对一个可运行和一个超预算配置，CLI 与 JSON 报告给出一致的内存
分解、结论、主要约束和建议。

## Phase 4：Runtime Calibration

交付内容：

- 导入 measured peak、backend/hardware/version 元数据；
- estimated 与 measured 的误差分析；
- 后端 profile 校准系数和置信度更新；
- 校准报告和脱敏校验。

独立验收：至少一组实测数据可重放，报告明确区分 theoretical、calibrated
和 measured，不把经验值伪装成精确公式。

## Phase 5：Multimodal and MoE

交付内容：

- 视觉 token 和 vision encoder 预算；
- MoE 总参数、激活参数和 KV Cache 分析；
- DeepSeek 专项配置与 golden tests。

独立验收：多模态 token 和 MoE 配置的增量内存影响可追溯，缺失数据时输出
区间或 unknown。

## Phase 6：Interactive Web

交付内容：

- 静态 Web UI 和内存可视化；
- 浏览器端离线计算；
- 分享配置与 JSON schema 版本管理；
- 跨语言 golden tests。

独立验收：核心库不依赖 Web，浏览器交互结果与 Python reference 实现一致。

## 阶段依赖

```text
Phase 0
  ↓
Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4
                                  └──→ Phase 5 ──→ Phase 6
```

下一阶段建议从 Phase 1 开始：先冻结 domain 数据语义和可审查公式，再接入
任何外部模型或硬件数据。
