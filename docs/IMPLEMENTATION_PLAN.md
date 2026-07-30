# KVScope v0.1 Implementation Plan

本文档把产品和架构文档中的 v0.1 拆分为可独立验收的阶段。当前阶段：
Phase 4（Weight Engine）已完成；后续阶段保持未开始。

## Phase 0：Repository Bootstrap — 已完成

验收标准：

- Python 3.11+ src-layout 和 `pyproject.toml` 可安装；
- `src/kvscope` 建立稳定的模块边界；
- `kvscope --version` 和 `kvscope --help` 可运行；
- pytest、pytest-cov、mypy、ruff、pre-commit 和 GitHub Actions 已配置；
- 单元、集成、golden、fixtures 测试目录存在；
- README、贡献指南、安全政策和 Apache-2.0 许可证齐全。

## Phase 1：Domain + KV Cache Formula — 已完成（基础能力）

交付内容：

- `ModelSpec`、`HardwareSpec`、`BackendSpec`、`InferenceConfig` 等不可变边界模型；
- dtype 与单位转换；
- KV Cache 与 block 对齐的纯计算；
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

## Phase 4：Weight Engine — 已完成

本阶段只实现无网络、无文件 IO 的模型权重内存估算：

- parameter count 与平均 bits-per-weight 模式；
- group-wise quantization 的 scale、zero-point、group size 和混合精度；
- 上游 `WeightArtifactSummary` 字节摘要模式；
- integer bytes、向上取整、alignment 和可追溯结果拆分；
- unit、property-based 和 golden tests。

本阶段明确未实现 Hugging Face 网络访问、config resolver、safetensors/GGUF
解析、hardware registry、runtime overhead、feasibility、recommendation、
Web UI、InferPilot 和推理后端启动。

独立验收：`estimate_weight_memory(...)` 对三种模式输出非负整数 bytes，结果
区分 artifact storage bytes 与 estimated resident weight bytes，且通过 Ruff、
mypy、pytest 和覆盖率门禁。

## Phase 5：Model Resolver + Model Registry — 已完成

交付内容：显式、本地 JSON、可选 Hugging Face、内置 registry resolver；LLaMA、Qwen、DeepSeek 和受控 generic decoder adapter；字段别名冲突检测；来源、revision、digest、warnings、confidence 和 attempts provenance；原子缓存与严格 offline 模式；`resolve_model` API 与 `inspect-model` CLI。

本阶段不下载或加载权重，不执行远程代码，不实现 Hardware/Backend Resolver、Runtime Overhead、Feasibility、Recommendation、Benchmark、Web UI 或 InferPilot。

## Phase 6：Hardware Registry, Backend Profile & Runtime Overhead Engine — 已完成

交付内容：
- Hardware Profile Schema (v0.1) 与 Hardware Registry，支持 6 个通用硬件容量 Profile（discrete 8/16/24G, unified 16/32G, system 32G）。
- Hardware Memory Budget 计算引擎（非模型预留 OS/Display/Background/Device/User 拆分，区间的 allocatable 与 recommended headroom 规约）。
- Backend Profile Schema (v0.1) 与 Backend Registry，支持 `packaging.specifiers` 版本匹配规则及候选优先级 Scoring 机制。
- Runtime Overhead Engine 纯计算引擎（包含 Base Runtime, Parameter Scaled, Workspace, Graph Capture, Backend Buffers, Allocator Margin）。
- `ByteRange` 与 `RatioRange` 不确定性区间传播及 ceiling integer bytes 运算。
- JSON, Terminal, Markdown 格式化序列化输出与 `kvscope hardware`, `kvscope backend`, `kvscope estimate-overhead` CLI 子命令。
- Unit tests, Hypothesis Property-based tests 与 Golden Cases A/B/C 测试套件。

本阶段明确未实现 Feasibility 最终判断、Status 判断、Recommendation 引擎、自动硬件探测、自动调优或远程后端连接。

## 后续：Runtime Calibration（未开始）

交付内容：

- 导入 measured peak、backend/hardware/version 元数据；
- estimated 与 measured 的误差分析；
- 后端 profile 校准系数和置信度更新；
- 校准报告和脱敏校验。

独立验收：至少一组实测数据可重放，报告明确区分 theoretical、calibrated
和 measured，不把经验值伪装成精确公式。

## 后续：Multimodal and MoE（未开始）

交付内容：

- 视觉 token 和 vision encoder 预算；
- MoE 总参数、激活参数和 KV Cache 分析；
- DeepSeek 专项配置与 golden tests。

独立验收：多模态 token 和 MoE 配置的增量内存影响可追溯，缺失数据时输出
区间或 unknown。

## 后续：Interactive Web（未开始）

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
Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4 (Weight Engine)
                                  └──→ 后续 Runtime Calibration
                                      └──→ 后续 Multimodal/MoE
                                          └──→ 后续 Interactive Web
```

下一阶段建议在 Phase 4 完成后再单独规划 Model Resolver；本次交付不进入该阶段。
