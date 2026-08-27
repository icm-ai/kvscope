# KVScope v0.1 Implementation Plan

本文档把产品和架构文档中的 v0.1 拆分为可独立验收的阶段。当前状态：
Phase 0、1、4、5、6、7、8 已完成。原始的 Phase 2 与 Phase 3 被后续的
Phase 5--8 重新拆分并交付；其条目保留用于追溯。Phase 9 与 Phase 10a 已完成，
v0.1 的静态分析核心及离线校准导入/误差分析已交付；Web UI、推理后端启动、
benchmark 和自动调优仍待后续版本单独规划。

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

## Phase 2：Resolvers + Registry — 由 Phase 5 和 Phase 6 交付

交付内容：

- 本地 `config.json` 解析；
- Hugging Face config 解析（默认不下载权重、不执行远程代码）；
- LLaMA、Qwen、DeepSeek Dense 与 generic adapter；
- 模型、硬件、后端 YAML profile registry；
- schema、单位、ID 唯一性和引用完整性校验；
- 离线模式与缓存边界。

独立验收：提供本地输入或 registry ID 时，resolver 返回标准 domain 对象；
无数据或字段不一致时返回可操作错误，不静默猜测。

## Phase 3：Decision + Reports + CLI — 核心能力由 Phase 7 和 Phase 8 交付

交付内容：

- feasibility、constraints、confidence 和 recommendations 引擎；
- feasible/tight/infeasible/unknown 结论与可解释建议；
- JSON 事实源、Terminal 和 Markdown 渲染；
- `inspect`、`estimate`、`fit`、`compare`、报告渲染等 CLI 子命令；
- 稳定的 `kvscope.api` 公共入口。

独立验收：对一个可运行和一个超预算配置，CLI 与 JSON 报告给出一致的内存
分解、结论、主要约束和建议。

Phase 9 以单一的 `analyze` 工作流交付面向新用户的端到端入口；原计划中的
`inspect`、`estimate`、`fit`、`compare`、`explain` 独立命令不属于 v0.1。

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

## Phase 9：v0.1 端到端 CLI 与发布就绪 — 已完成

目标是在不改变公式或决策引擎语义的前提下，将已完成的核心能力组合为用户可
发现、可复现的工作流，并使文档与实际 API/CLI 保持一致。

交付内容：

- `kvscope analyze` 将模型解析、参数量权重估算、KV Cache、硬件预算、运行时
  开销、可行性评估串联为单次命令；可选生成 Recommendation Report；
- 内置 vLLM 与 llama.cpp 的通用 `unverified` Backend Profile，用于低置信度的
  初步规划，始终提示用户须在目标环境上验证；
- README、profile 文档与 quick start 同步实际 CLI 和当前阶段状态；
- 端到端 CLI 测试覆盖正常分析、推荐 JSON 输出和缺失参数量的拒绝路径。

校准、Web UI、启动推理后端、benchmark 和自动调优仍不属于本阶段。

## Phase 10a：Runtime Calibration — 离线测量记录导入与误差分析 — 已完成

本阶段将用户或外部工具已采集的峰值内存数据作为本地 JSON 导入，并与完整的
`MemoryFeasibilityReport` 比较；它不执行或编排任何 runtime。

交付内容：

- 冻结的 `CalibrationMeasurement` Pydantic 边界模型和
  `calibration-record-v0.1.json` 版本化 schema；记录保留采集时间、模型、
  backend/hardware、可复现 inference 配置、正整数 bytes、来源和 evidence；
- 仅本地文件的严格 JSON/Pydantic loader，提供文件不存在、非法 JSON、schema
  不匹配及非正峰值的可操作错误；
- `kvscope analyze` 生成的 feasibility JSON 记录 model/backend/hardware 和完整
  inference 配置 provenance；`compare_calibration_measurement(report, measurement)`
  逐字段验证已知身份，拒绝 mismatch 或无 provenance 的报告，对完整总需求区间输出
  落点、lower/expected/upper 的有符号字节差、精确分数误差、置信度、假设、warnings
  与 evidence；partial report 明确返回不可比较结果；
- `kvscope calibrate compare --report-json REPORT --measurement-json MEASUREMENT`
  的 Terminal、JSON 和 Markdown 输出；JSON 是版本化事实源；
- 校准记录说明文档、无敏感信息的示例 measurement JSON，以及覆盖 loader、
  区间内/外、partial report 和 CLI 格式的测试。

明确非目标：不执行 benchmark、不启动 backend、不抓取日志、不访问网络、不做
`fit` 或自动调整 backend profile、allocator margin、headroom 或其他预留。此类
人工审核后的拟合能力留给 Phase 10b。

## 阶段依赖

```text
Phase 0
  ↓
Phase 1 ──→ Phase 2 ──→ Phase 4 (Weight Engine) ──→ Phase 5 (Model Resolver)
                                                         ↓
Phase 8 (Recommendation Engine) ←── Phase 7 (Memory Engine) ←── Phase 6 (Hardware & Overhead)
  ↓
Phase 9 (End-to-end CLI & release readiness)
  ↓
Phase 10a (Offline calibration import & error analysis)
```
