# KVScope 系统架构设计 v0.1

> **项目名称**：KVScope  
> **文档类型**：Architecture / Design Document  
> **文档状态**：Draft  
> **版本**：0.1  
> **目标实现语言**：Python 3.11+  
> **目标读者**：维护者、核心贡献者、集成方

---

## 1. 文档目的

本文档定义 KVScope v0.1 的系统架构、模块边界、核心数据模型、计算流程、扩展接口、错误处理、测试策略和演进路径。

架构目标是支持：

- CLI；
- Python SDK；
- Web 前端；
- InferPilot 集成；
- 社区贡献模型、硬件和后端 profile；
- 静态估算与实测校准分离。

---

## 2. 架构目标

### 2.1 功能目标

系统必须能够：

1. 解析模型结构；
2. 估算权重内存；
3. 估算 KV Cache；
4. 加入后端运行时开销；
5. 加入系统安全预留；
6. 判断部署可行性；
7. 解释主要限制；
8. 生成可执行建议；
9. 导出稳定、可版本化的报告。

### 2.2 质量目标

- 公式可审查；
- 计算可复现；
- 数据与代码分离；
- 核心库不依赖 Web；
- 允许离线运行；
- 未知模型可通过通用字段分析；
- 失败时不静默猜测；
- 扩展新模型和硬件不需要修改核心逻辑。

### 2.3 非目标

- 启动推理服务；
- 自动搜索最优参数；
- 精确预测吞吐；
- 训练内存分析；
- GPU kernel profiling。

---

## 3. 总体架构

```text
                           ┌─────────────────────┐
                           │      CLI / SDK      │
                           └──────────┬──────────┘
                                      │
                           ┌──────────▼──────────┐
                           │  Application Layer  │
                           │ Analyze / Fit / Diff│
                           └──────────┬──────────┘
                                      │
       ┌──────────────────────────────┼──────────────────────────────┐
       │                              │                              │
┌──────▼──────┐               ┌──────▼──────┐               ┌──────▼──────┐
│ Model       │               │ Hardware    │               │ Backend     │
│ Resolver    │               │ Resolver    │               │ Resolver    │
└──────┬──────┘               └──────┬──────┘               └──────┬──────┘
       │                              │                              │
       └──────────────────────────────┼──────────────────────────────┘
                                      │
                           ┌──────────▼──────────┐
                           │ Normalized Domain   │
                           │ Model / HW / Config │
                           └──────────┬──────────┘
                                      │
               ┌──────────────────────┼──────────────────────┐
               │                      │                      │
       ┌───────▼────────┐    ┌────────▼────────┐    ┌───────▼────────┐
       │ Weight Engine  │    │ KV Cache Engine │    │ Overhead Engine│
       └───────┬────────┘    └────────┬────────┘    └───────┬────────┘
               └──────────────────────┼──────────────────────┘
                                      │
                           ┌──────────▼──────────┐
                           │ Feasibility Engine │
                           └──────────┬──────────┘
                                      │
                           ┌──────────▼──────────┐
                           │ Recommendation     │
                           │ & Explanation      │
                           └──────────┬──────────┘
                                      │
                           ┌──────────▼──────────┐
                           │ Report Serializer  │
                           │ Text/JSON/Markdown │
                           └─────────────────────┘
```

---

## 4. 分层设计

### 4.1 Domain Layer

Domain Layer 定义稳定的数据语义，不感知 CLI、HTTP 和具体文件格式。

核心对象：

- `ModelSpec`；
- `HardwareSpec`；
- `BackendSpec`；
- `InferenceConfig`；
- `MemoryEstimate`；
- `FeasibilityResult`；
- `Recommendation`；
- `AnalysisReport`；
- `Evidence`；
- `Confidence`。

### 4.2 Resolver Layer

Resolver 负责将多种输入解析为标准对象：

- Hugging Face config；
- 本地 config；
- GGUF metadata；
- safetensors index；
- 内置 registry；
- 用户显式参数；
- 当前机器探测结果。

### 4.3 Calculation Layer

包括：

- Weight Engine；
- KV Cache Engine；
- Runtime Overhead Engine；
- System Reserve Engine；
- Multimodal Token Estimator（v0.2+）；
- Alignment Engine。

### 4.4 Decision Layer

包括：

- Feasibility Engine；
- Constraint Analyzer；
- Recommendation Engine；
- Confidence Evaluator。

### 4.5 Presentation Layer

包括：

- CLI；
- Python API；
- JSON serializer；
- Markdown renderer；
- 未来的 REST / WebAssembly adapter。

---

## 5. 建议仓库结构

```text
kvscope/
├── pyproject.toml
├── README.md
├── README.zh-CN.md
├── LICENSE
├── CONTRIBUTING.md
├── SECURITY.md
├── ROADMAP.md
├── docs/
│   ├── KVScope_Product_Spec_v0.1.md
│   ├── KVScope_Architecture_v0.1.md
│   ├── formulas.md
│   ├── calibration.md
│   └── json-schema.md
├── src/
│   └── kvscope/
│       ├── __init__.py
│       ├── api.py
│       ├── cli/
│       │   ├── app.py
│       │   ├── inspect.py
│       │   ├── estimate.py
│       │   ├── fit.py
│       │   └── compare.py
│       ├── domain/
│       │   ├── model.py
│       │   ├── hardware.py
│       │   ├── backend.py
│       │   ├── config.py
│       │   ├── estimate.py
│       │   ├── report.py
│       │   └── evidence.py
│       ├── resolvers/
│       │   ├── base.py
│       │   ├── huggingface.py
│       │   ├── local_config.py
│       │   ├── safetensors.py
│       │   ├── gguf.py
│       │   ├── registry.py
│       │   └── runtime_hardware.py
│       ├── calculators/
│       │   ├── weights.py
│       │   ├── kv_cache.py
│       │   ├── overhead.py
│       │   ├── reserve.py
│       │   └── alignment.py
│       ├── engines/
│       │   ├── analysis.py
│       │   ├── feasibility.py
│       │   ├── constraints.py
│       │   ├── recommendations.py
│       │   └── confidence.py
│       ├── registries/
│       │   ├── loader.py
│       │   ├── models/
│       │   ├── hardware/
│       │   └── backends/
│       ├── calibration/
│       │   ├── schema.py
│       │   ├── loader.py
│       │   └── fitter.py
│       ├── serialization/
│       │   ├── json.py
│       │   ├── markdown.py
│       │   └── terminal.py
│       ├── schemas/
│       │   ├── analysis-report-v0.1.json
│       │   └── profile-v0.1.json
│       └── errors.py
├── profiles/
│   ├── models/
│   ├── hardware/
│   ├── backends/
│   └── calibration/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── golden/
│   └── fixtures/
└── examples/
    ├── jetson_orin_nx.py
    ├── compare_hardware.py
    └── reports/
```

---

## 6. 核心数据模型

建议使用 `pydantic` v2 定义边界对象，内部纯计算函数尽量使用不可变数据结构。

### 6.1 ModelSpec

```python
from pydantic import BaseModel, Field


class ModelSpec(BaseModel):
    model_id: str
    architecture: str

    num_hidden_layers: int = Field(gt=0)
    hidden_size: int = Field(gt=0)
    num_attention_heads: int = Field(gt=0)
    num_key_value_heads: int = Field(gt=0)
    head_dim: int = Field(gt=0)

    vocab_size: int | None = None
    intermediate_size: int | None = None
    max_position_embeddings: int | None = None

    parameter_count: int | None = None
    active_parameter_count: int | None = None

    num_experts: int | None = None
    num_experts_per_tok: int | None = None

    tie_word_embeddings: bool | None = None
    source: str
```

约束：

```text
num_attention_heads % num_key_value_heads == 0
hidden_size == num_attention_heads × head_dim
```

若模型配置不满足，应产生明确 warning，而不是自动修正。

### 6.2 HardwareSpec

```python
class MemoryTopology(str, Enum):
    DISCRETE = "discrete"
    UNIFIED = "unified"
    SYSTEM = "system"


class HardwareSpec(BaseModel):
    hardware_id: str
    vendor: str
    device_family: str
    name: str

    memory_topology: MemoryTopology
    total_memory_bytes: int
    default_system_reserve_bytes: int

    memory_bandwidth_gbps: float | None = None
    compute_capability: str | None = None
    supported_backends: list[str] = []
    notes: list[str] = []
```

### 6.3 BackendSpec

```python
class BackendSpec(BaseModel):
    backend_id: str
    version_constraint: str | None = None

    base_overhead_bytes: int
    overhead_per_billion_parameters_bytes: int
    graph_capture_reserve_bytes: int
    workspace_ratio: float
    allocator_margin_ratio: float

    kv_block_size: int | None = None
    supports_kv_dtypes: list[str]
    supports_cpu_offload: bool
    confidence: str
```

BackendSpec 的所有经验字段必须附带 evidence。

### 6.4 InferenceConfig

```python
class InferenceConfig(BaseModel):
    weight_dtype: str
    kv_dtype: str

    context_length: int
    batch_size: int = 1
    max_num_seqs: int = 1

    prefix_tokens: int = 0
    multimodal_tokens: int = 0

    cpu_offload_bytes: int = 0
    graph_capture_enabled: bool = True
    safety_margin_ratio: float = 0.05
```

第一版需要明确 `batch_size` 与 `max_num_seqs` 的语义：

- offline batch；
- serving active sequences；
- beam width；
- speculative decode slot。

v0.1 默认将 KV 活跃序列数定义为：

```text
active_sequences = max(batch_size, max_num_seqs)
```

但报告中必须说明该假设。

### 6.5 MemoryEstimate

```python
class EstimateComponent(BaseModel):
    name: str
    bytes: int
    lower_bound_bytes: int | None = None
    upper_bound_bytes: int | None = None
    confidence: str
    formula: str | None = None
    evidence_ids: list[str] = []


class MemoryEstimate(BaseModel):
    weights: EstimateComponent
    kv_cache: EstimateComponent
    runtime_overhead: EstimateComponent
    graph_capture: EstimateComponent
    workspace: EstimateComponent
    system_reserve: EstimateComponent
    safety_margin: EstimateComponent
    total: EstimateComponent
```

### 6.6 AnalysisReport

```python
class AnalysisReport(BaseModel):
    schema_version: str
    generated_at: datetime

    model: ModelSpec
    hardware: HardwareSpec
    backend: BackendSpec
    config: InferenceConfig

    estimate: MemoryEstimate
    feasibility: FeasibilityResult
    constraints: list[Constraint]
    recommendations: list[Recommendation]
    warnings: list[str]
    evidence: list[Evidence]
```

---

## 7. 输入解析设计

### 7.1 Resolver 协议

```python
from typing import Protocol


class ModelResolver(Protocol):
    def can_resolve(self, source: str) -> bool:
        ...

    def resolve(self, source: str) -> ModelSpec:
        ...
```

Resolver 链：

```text
Explicit ModelSpec
    ↓
Local Config Resolver
    ↓
Local Weight Metadata Resolver
    ↓
Hugging Face Resolver
    ↓
Built-in Registry Resolver
    ↓
Generic Manual Resolver
```

### 7.2 Hugging Face 解析

优先直接获取 `config.json`，避免导入和实例化模型。

网络策略：

- 默认允许缓存；
- 提供 `--offline`；
- 缓存原始 config 与解析结果；
- 记录 revision / commit hash；
- 不下载权重。

### 7.3 字段归一化

不同模型可能使用：

```text
n_layer / num_hidden_layers
n_head / num_attention_heads
n_head_kv / num_key_value_heads
d_model / hidden_size
```

归一化通过架构 adapter 完成：

```python
class ArchitectureAdapter(Protocol):
    architecture_names: set[str]

    def normalize(self, raw_config: dict) -> ModelSpec:
        ...
```

首批 adapter：

- `LlamaAdapter`；
- `QwenAdapter`；
- `DeepSeekAdapter`；
- `GenericDecoderAdapter`。

---

## 8. 计算引擎设计

### 8.1 Weight Engine

接口：

```python
def estimate_weight_memory(
    model: ModelSpec,
    dtype: WeightDType,
    artifact: WeightArtifact | None,
) -> EstimateComponent:
    ...
```

优先级：

1. 权重文件真实大小；
2. safetensors index；
3. config 中 parameter_count；
4. 按结构推导；
5. 用户显式参数。

#### 8.1.1 量化元数据

INT4 并不总是严格 4 bit/parameter，需要处理：

- scale；
- zero-point；
- group size；
- padding；
- embedding / lm_head 未量化；
- mixed precision。

建议返回区间：

```text
raw payload + metadata overhead + alignment overhead
```

### 8.2 KV Cache Engine

接口：

```python
def estimate_kv_cache(
    model: ModelSpec,
    config: InferenceConfig,
    backend: BackendSpec,
) -> EstimateComponent:
    ...
```

基础计算：

```text
tokens =
context_length
+ prefix_tokens
+ multimodal_tokens

raw_kv =
2
× layers
× tokens
× active_sequences
× kv_heads
× head_dim
× bytes_per_element
```

后端对齐：

```text
allocated_tokens =
ceil(tokens / block_size) × block_size
```

需要展示：

- raw KV；
- block 对齐后 KV；
- 对齐浪费；
- 每 token；
- 每 active sequence；
- 每层。

### 8.3 Runtime Overhead Engine

接口：

```python
def estimate_runtime_overhead(
    model: ModelSpec,
    hardware: HardwareSpec,
    backend: BackendSpec,
    config: InferenceConfig,
) -> list[EstimateComponent]:
    ...
```

拆分：

- base engine；
- graph capture；
- temporary workspace；
- allocator margin；
- backend-specific buffers。

不得只输出一个不透明的“其他”。

### 8.4 System Reserve Engine

离散显存：

```text
available_device_memory =
total_device_memory
- display_reserve
- user_reserved_memory
```

统一内存：

```text
available_unified_memory =
total_memory
- os_reserve
- active_process_reserve
- filesystem_cache_reserve
```

统一内存只给出可用范围，避免声称所有内存都可以被推理使用。

### 8.5 Feasibility Engine

```python
def evaluate_feasibility(
    estimate: MemoryEstimate,
    hardware: HardwareSpec,
) -> FeasibilityResult:
    ...
```

建议阈值：

```text
headroom = available - required

headroom_ratio >= 0.15  -> feasible / low risk
0 <= headroom_ratio < 0.15 -> tight / medium-high risk
headroom < 0 -> infeasible
```

阈值必须允许 profile 覆盖。

---

## 9. 约束分析

Constraint Analyzer 输出影响最大的瓶颈。

```python
class Constraint(BaseModel):
    code: str
    title: str
    severity: str
    component: str
    current_value: float | int | str
    threshold: float | int | str | None
    explanation: str
```

首批约束代码：

```text
WEIGHTS_EXCEED_AVAILABLE_MEMORY
KV_CACHE_EXCEEDS_BUDGET
RUNTIME_OVERHEAD_TOO_HIGH
CONTEXT_EXCEEDS_MODEL_LIMIT
UNSUPPORTED_WEIGHT_DTYPE
UNSUPPORTED_KV_DTYPE
UNSUPPORTED_BACKEND
UNIFIED_MEMORY_HEADROOM_LOW
MODEL_CONFIG_INCONSISTENT
INSUFFICIENT_INPUT_DATA
```

---

## 10. 推荐引擎

### 10.1 原则

推荐必须是确定性的、可解释的，并估算影响。

错误示例：

```text
Try reducing some parameters.
```

正确示例：

```text
将 context_length 从 32768 降为 8192，
预计减少 3.38 GiB KV Cache；
代价是最大上下文缩短 75%。
```

### 10.2 推荐规则

建议将规则数据化：

```yaml
id: reduce-context-for-kv
when:
  constraint: KV_CACHE_EXCEEDS_BUDGET
action:
  parameter: context_length
  strategy: binary_search_feasible_limit
priority: 100
```

### 10.3 目标反推

提供函数：

```python
find_max_context(...)
find_max_active_sequences(...)
find_min_weight_bits(...)
find_required_memory(...)
```

这些函数将直接成为 InferPilot Planner 的基础。

---

## 11. Evidence 与置信度

### 11.1 Evidence

```python
class Evidence(BaseModel):
    evidence_id: str
    source_type: str
    source: str
    version: str | None
    observed_at: datetime | None
    notes: str | None
```

### 11.2 置信等级

- `exact`：由文件大小或确定公式获得；
- `high`：由官方 config 和已校准 profile 获得；
- `medium`：同类设备或后端经验；
- `low`：通用缺省值；
- `unknown`：无法可靠估计。

最终报告的总置信度不能高于最关键组件中的最低等级。

---

## 12. Registry 设计

### 12.1 文件格式

使用 YAML，便于社区贡献。

```yaml
schema_version: "0.1"
id: jetson-orin-nx-16gb
kind: hardware
name: NVIDIA Jetson Orin NX 16GB
vendor: nvidia
memory:
  topology: unified
  total_gib: 15.3
  default_system_reserve_gib: 2.0
evidence:
  - source_type: official_spec
    source: NVIDIA Jetson Orin NX documentation
confidence: high
```

### 12.2 覆盖顺序

```text
用户输入
> 用户本地 profile
> 项目内置校准 profile
> 通用内置 profile
```

### 12.3 Schema 验证

所有 profile 在 CI 中：

- JSON Schema 验证；
- 单位检查；
- ID 唯一性；
- 引用完整性；
- 逻辑约束检查。

---

## 13. Python API

建议公开 API：

```python
from kvscope import analyze, estimate, fit, compare


report = analyze(
    model="Qwen/Qwen3.5-4B",
    hardware="jetson-orin-nx-16gb",
    backend="vllm",
    weight_dtype="int4",
    kv_dtype="fp16",
    context_length=8192,
    max_num_seqs=1,
)
```

低层 API：

```python
from kvscope.api import (
    resolve_model,
    resolve_hardware,
    resolve_backend,
    estimate_weight_memory,
    estimate_kv_cache,
    evaluate_feasibility,
    generate_recommendations,
)
```

稳定性策略：

- `kvscope.api` 是稳定公共 API；
- 内部模块不承诺兼容；
- JSON schema 单独版本化；
- profile schema 单独版本化。

---

## 14. CLI 设计

建议使用 Typer。

```text
kvscope inspect MODEL
kvscope estimate MODEL
kvscope fit MODEL
kvscope compare MODEL
kvscope profile validate PATH
kvscope report render REPORT_JSON
```

示例：

```bash
kvscope fit Qwen/Qwen3.5-4B \
  --hardware jetson-orin-nx-16gb \
  --backend vllm \
  --weight-dtype int4 \
  --kv-dtype fp16 \
  --context 8192 \
  --max-num-seqs 1 \
  --format markdown
```

退出码：

```text
0  分析完成，feasible
2  分析完成，tight
3  分析完成，infeasible
4  输入错误
5  解析失败
6  profile 不受支持
10 内部错误
```

---

## 15. 序列化设计

### 15.1 JSON

JSON 是事实源，Terminal 和 Markdown 由 JSON report 渲染。

### 15.2 浮点处理

内部以整数 bytes 存储，避免浮点累计误差。

展示时再转换为 GiB：

```python
gib = bytes_value / (1024 ** 3)
```

### 15.3 Schema Version

```json
{
  "schema_version": "0.1"
}
```

破坏性变化升级 major schema。

---

## 16. 错误处理

错误类型：

```python
class KVScopeError(Exception):
    code: str


class ModelResolutionError(KVScopeError):
    ...


class InvalidModelConfigError(KVScopeError):
    ...


class UnsupportedArchitectureError(KVScopeError):
    ...


class ProfileValidationError(KVScopeError):
    ...
```

错误输出必须包含：

- 错误码；
- 原因；
- 受影响字段；
- 修复方式；
- 是否可以退化到 generic 模式。

---

## 17. 缓存与离线模式

缓存内容：

- Hugging Face config；
- 模型解析结果；
- revision；
- profile；
- 可选权重 metadata。

默认目录：

```text
~/.cache/kvscope/
```

离线模式：

```bash
kvscope estimate MODEL --offline
```

离线找不到数据时，不自动访问网络。

---

## 18. 安全与隐私

- 不执行模型仓库中的远程代码；
- 不使用 `trust_remote_code=True` 作为默认路径；
- 不加载模型权重到内存；
- 不上传用户机器信息；
- Web 版本默认在浏览器本地计算；
- 提交校准数据必须显式 opt-in；
- 报告中 API key、路径和用户名需脱敏。

---

## 19. 测试策略

### 19.1 单元测试

覆盖：

- dtype 转换；
- KV Cache 公式；
- block 对齐；
- GQA/MQA；
- 权重估算；
- feasibility 阈值；
- 推荐节省量；
- 单位转换。

### 19.2 Golden Tests

为典型模型保存黄金报告：

- Qwen 0.6B；
- Qwen 4B；
- Llama 8B；
- DeepSeek Distill；
- GQA / MQA / MHA 人工配置。

### 19.3 Property-Based Tests

使用 Hypothesis 验证：

- context 增加时 KV Cache 单调不减；
- batch 增加时 KV Cache 单调不减；
- KV dtype bytes 减小时内存不增加；
- `kv_heads <= attention_heads`；
- 建议后的配置应降低目标组件内存。

### 19.4 集成测试

- Hugging Face config；
- 本地 config；
- registry；
- CLI；
- JSON schema；
- Markdown rendering。

### 19.5 校准测试

记录：

```text
estimated_peak
measured_peak
absolute_error
relative_error
backend_version
driver_version
hardware_id
```

---

## 20. 性能目标

KVScope 本身不加载模型，目标：

- 本地 config 解析小于 100 ms；
- 单次分析小于 50 ms；
- Web 端交互更新小于 100 ms；
- 内置 registry 加载小于 200 ms；
- 无网络情况下冷启动小于 1 s。

---

## 21. 依赖策略

核心依赖尽量小：

```text
pydantic
typer
pyyaml
httpx
platformdirs
rich
```

可选依赖：

```text
huggingface_hub
safetensors
gguf parser
```

禁止核心库强依赖：

- torch；
- transformers；
- CUDA；
- vLLM。

---

## 22. Web 架构演进

v0.2 可采用：

```text
KVScope Core
    ↓
JSON/WASM-compatible Calculation Model
    ↓
React/Vue/Svelte UI
    ↓
GitHub Pages
```

两条可选路线：

1. 将公式逻辑重写为 TypeScript；
2. 使用 Pyodide 在浏览器运行 Python Core。

推荐早期使用 TypeScript 复刻稳定公式，Python 继续作为事实参考实现，并用跨语言 golden tests 保持一致。

---

## 23. InferPilot 集成点

InferPilot 依赖以下稳定接口：

```python
report = analyze(...)
max_context = find_max_context(...)
max_sequences = find_max_active_sequences(...)
candidates = generate_memory_safe_candidates(...)
```

InferPilot 可扩展但不应修改 KVScope 的职责：

- 启动后端；
- 运行 benchmark；
- 收集实测；
- 搜索参数；
- 选择最终 profile。

---

## 24. 实施阶段

### Phase 1：Domain + Formula

- 数据模型；
- dtype；
- Weight Engine；
- KV Cache Engine；
- 单元测试。

### Phase 2：Resolvers + Registry

- Hugging Face config；
- local config；
- model registry；
- hardware registry；
- backend registry。

### Phase 3：Decision + Reports

- feasibility；
- constraints；
- recommendations；
- JSON；
- Markdown；
- CLI。

### Phase 4：Calibration

- 导入实测；
- 误差分析；
- backend profile 校准；
- benchmark 文档。

### Phase 5：Web

- 浏览器 UI；
- 图表；
- GitHub Pages；
- 分享链接。

---

## 25. 架构决策记录

建议建立 `docs/adr/`。

首批 ADR：

```text
ADR-001: Python as the reference implementation
ADR-002: Integer bytes as the internal memory unit
ADR-003: Data-driven hardware and backend profiles
ADR-004: No remote model code execution
ADR-005: JSON report as the rendering source of truth
ADR-006: KVScope does not start inference backends
```

---

## 26. 关键风险

### 26.1 总内存估算被误解为精确值

缓解：

- 输出区间；
- 显示置信度；
- 显示估算来源；
- 区分 theoretical/calibrated/measured。

### 26.2 后端变化频繁

缓解：

- profile 带版本范围；
- profile 与代码分离；
- 社区提交校准数据；
- 未匹配版本时降低置信度。

### 26.3 模型 config 不规范

缓解：

- adapter；
- schema validation；
- generic fallback；
- 明确 warning。

### 26.4 统一内存难以精确预测

缓解：

- 采用可用区间；
- 支持运行时机器检测；
- 显式系统预留；
- 不承诺峰值精度。

---

## 27. 结论

KVScope v0.1 应采用“稳定核心 + 数据驱动 profile + 可解释决策”的架构。

最重要的技术约束是：

1. 公式与经验值分离；
2. 内部统一使用 bytes；
3. 所有估算可追溯；
4. 核心库不依赖具体 UI；
5. 模型、硬件和后端通过 registry 扩展；
6. 为 InferPilot 提供稳定分析 API，但不承担自动部署职责。

该架构允许项目从一个轻量 CLI，自然演进为：

- 在线可视化工具；
- 推理内存知识库；
- 自动部署规划器的核心依赖；
- 社区驱动的边缘 LLM 硬件数据基础设施。
