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

## Phase 7：Memory Engine + Aggregation + Feasibility + Constraint Analysis — 已完成

交付内容：
- Memory Aggregation Engine (`aggregate_memory_requirements`)：聚合 Weight Memory, KV Cache, Runtime Overhead 成为统一模型需求。
- Feasibility Engine (`evaluate_memory_feasibility`)：基于推荐/分配预算推导 `GUARANTEED_FEASIBLE`, `EXPECTED_FEASIBLE`, `CONDITIONAL_FEASIBLE`, `HEADROOM_EXCEEDED`, `ALLOCATABLE_EXCEEDED`, `PHYSICAL_MEMORY_EXCEEDED` 内部状态与 `FEASIBLE`, `TIGHT`, `INFEASIBLE` 产品状态。
- Constraint Analysis Engine (`analyze_memory_constraints`)：根据 12 种结构化 Constraint Code 分析内存瓶颈与风险。
- `assess_memory_feasibility` 高层入口，JSON / Terminal / Markdown 序列化，`kvscope assess-memory` CLI。

## Phase 8：Recommendation Engine 与安全参数反推 — 已完成

交付内容：
- Recommendation Eligibility Engine (`determine_recommendation_eligibility`)：结构化判定 ELIGIBLE, ADVISORY_ONLY, INELIGIBLE。
- Safe Parameter Back-solving Engines (`find_safe_context_limits`, `find_safe_active_sequence_limits`)：反推 recommended allocatable, allocatable ceiling 目标下的最大 context 与 active sequences，并经过 forward engine 二次验证。
- Counterfactual Candidate Generators & Evaluation (`generate_candidate_proposals`, `evaluate_candidate_proposal`)：重算 KV/Weight/Runtime 单组件，计算 SignedByteRange 内存节省量，确定 Strength & Verification Status。
- Deterministic Ranking Engine (`rank_recommendation_candidates`)：无浮点/随机数的 10 元组多键确定性排序。
- Top-level `generate_recommendations` API，`kvscope recommend` CLI，`recommendation-report-v0.1.json` JSON schema，8 个 Golden Cases A-H，Unit 与 Hypothesis Property-based 测试。

## 阶段依赖

```text
Phase 0
  ↓
Phase 1 ──→ Phase 2 ──→ Phase 4 (Weight Engine) ──→ Phase 5 (Model Resolver)
                                                         ↓
Phase 8 (Recommendation Engine) ←── Phase 7 (Memory Engine) ←── Phase 6 (Hardware & Overhead)
```

