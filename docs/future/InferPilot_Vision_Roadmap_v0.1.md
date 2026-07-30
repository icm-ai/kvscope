# InferPilot 产品愿景与技术路线 v0.1

> **项目名称**：InferPilot  
> **副标题**：Planning, Diagnosing and Tuning LLM Inference Across Heterogeneous Hardware  
> **文档状态**：Vision / RFC Draft  
> **版本**：0.1  
> **目标读者**：项目发起人、核心维护者、早期贡献者、合作方

---

## 1. 文档目的

本文档定义 InferPilot 的长期产品愿景、问题边界、核心能力、总体架构、阶段路线和与 KVScope、EdgeBench 的关系。

它不是 v0.1 的详细实现设计，也不要求项目立即覆盖所有硬件和后端。

InferPilot 的第一原则是：

> **先把一个模型在一台机器上可靠地配置并验证，再扩展到更多后端和硬件。**

---

## 2. 一句话定位

> **InferPilot 根据模型、硬件和目标，生成可运行的推理配置，并通过实测诊断和调优形成可复用的部署 Profile。**

英文定位：

> **From model and hardware to a runnable, benchmarked inference configuration.**

---

## 3. 问题定义

LLM 推理部署当前存在三个断层。

### 3.1 从模型到配置的断层

用户知道：

- 模型名称；
- 机器型号；
- 目标上下文；
- 并发需求。

但不知道：

- 该选择 vLLM、SGLang、llama.cpp 还是其他后端；
- 应该使用何种量化；
- 哪些启动参数可以保证启动；
- 哪些参数影响 TTFT、TPS 和稳定性。

### 3.2 从错误到根因的断层

失败日志往往包含：

- OOM；
- KV Cache 不足；
- CUDA Graph 失败；
- 不支持的 dtype；
- 架构不兼容；
- tokenizer / config 问题；
- ABI / driver 问题；
- CPU offload 过量；
- 多模态限制错误。

用户仍然需要大量人工搜索才能确定修复方案。

### 3.3 从“能跑”到“合适”的断层

默认配置可能启动成功，但：

- TTFT 不达标；
- 并发过低；
- 内存余量不足；
- 长时间运行后热降频；
- 前缀缓存没有收益；
- CPU offload 造成严重性能下降；
- 上下文或 batch 配置浪费资源。

---

## 4. 产品愿景

InferPilot 希望成为本地和边缘 LLM 推理的“部署规划与调优控制面”。

长期工作流：

```text
Model + Hardware + Workload + Objective
                    ↓
             Static Planning
                    ↓
          Runnable Configuration
                    ↓
          Launch and Health Check
                    ↓
              Benchmark
                    ↓
          Parameter Search / Tune
                    ↓
      Validated Deployment Profile
                    ↓
        Reuse / Share / Compare
```

用户最终应获得：

- 一条可执行启动命令；
- 一份配置文件；
- 一份为什么这样配置的解释；
- 一份实测报告；
- 一份失败时的修复建议；
- 一份可以在同类设备上复用的 Profile。

---

## 5. 目标用户

### 5.1 本地 AI 开发者

希望快速在消费级 GPU、Mac 或 Windows AI PC 上部署模型。

### 5.2 边缘 AI 工程师

目标设备：

- Jetson；
- 工控机；
- 统一内存 APU；
- 智能眼镜；
- Android；
- NPU 设备。

### 5.3 推理平台工程师

需要：

- 建立标准化部署 profile；
- 比较后端；
- 批量验证模型；
- 将调优结果纳入 CI；
- 形成硬件能力矩阵。

### 5.4 开源模型维护者

需要提供：

- 已验证的设备配置；
- 推荐后端；
- 显存和上下文范围；
- 可复现 benchmark。

---

## 6. 核心产品能力

### 6.1 Inspect

检查模型、硬件、环境和后端能力。

```bash
inferpilot inspect \
  --model Qwen/Qwen3.5-4B \
  --backend vllm
```

输出：

- 模型结构；
- 权重格式；
- 推荐 dtype；
- 硬件容量；
- 驱动和运行时；
- 后端兼容性；
- 已知风险；
- 可用 profile。

### 6.2 Plan

生成候选部署方案。

```bash
inferpilot plan \
  Qwen/Qwen3.5-4B \
  --hardware auto \
  --objective balanced
```

输出：

```text
SAFE
BALANCED
THROUGHPUT
LOW_MEMORY
LOW_TTFT
```

每个方案包含：

- backend；
- model artifact；
- quantization；
- context length；
- concurrency；
- backend args；
- 预计内存；
- 预计风险；
- 假设和证据。

### 6.3 Doctor

解析错误日志并定位根因。

```bash
inferpilot doctor logs/vllm.log
```

输出：

- root cause；
- confidence；
- matched signatures；
- suggested changes；
- validation command；
- related known issue。

### 6.4 Launch

以受控方式启动后端。

```bash
inferpilot launch profile.yaml
```

职责：

- 前置检查；
- 环境变量；
- 命令生成；
- 进程启动；
- 健康检查；
- 日志收集；
- 停止与清理。

### 6.5 Benchmark

执行标准化 workload。

```bash
inferpilot benchmark \
  --profile profile.yaml \
  --suite edge-chat
```

指标：

- cold start；
- model load time；
- TTFT p50/p95/p99；
- inter-token latency；
- prefill TPS；
- decode TPS；
- request throughput；
- success rate；
- peak memory；
- CPU/GPU utilization；
- power / temperature（设备支持时）。

### 6.6 Tune

根据目标搜索参数。

```bash
inferpilot tune \
  --profile profile.yaml \
  --objective p95_ttft \
  --constraint p95_ttft_ms<=800 \
  --constraint peak_memory_gib<=14.5
```

搜索变量：

- context length；
- max active sequences；
- max batched tokens；
- memory utilization；
- chunked prefill；
- prefix cache；
- KV dtype；
- graph capture；
- CPU offload；
- batch size；
- thread count；
- GPU layers；
-后端特定参数。

### 6.7 Profile

保存经过验证的结果。

```yaml
schema_version: "0.1"
profile_id: qwen35-4b-jetson-orin-nx-vllm-balanced
model:
  id: Qwen/Qwen3.5-4B
hardware:
  id: jetson-orin-nx-16gb
backend:
  id: vllm
  version: 0.x
configuration:
  max_model_len: 4096
  max_num_seqs: 1
  gpu_memory_utilization: 0.92
validation:
  status: passed
  benchmark_id: edge-chat-v0.1
  measured:
    p95_ttft_ms: 920
    decode_tps: 18.7
    peak_memory_gib: 14.6
```

---

## 7. 非目标

InferPilot 不是：

- 新的推理引擎；
- Kubernetes 替代品；
- 通用分布式训练系统；
- 模型下载站；
- 聊天 UI；
- Agent 框架；
- 云端商业模型 API 聚合器。

早期也不负责：

- 多节点大规模集群；
- 跨地域调度；
- 自动修改模型代码；
- 自动量化训练；
- 端到端应用编排。

---

## 8. 核心设计原则

### 8.1 Runnable First

第一目标是生成能启动并通过健康检查的配置。

### 8.2 Evidence-Based

推荐依据必须来自：

- KVScope 静态分析；
- 后端官方能力；
- 当前机器检测；
- 已验证 profile；
- 实测 benchmark；
- 明确标注的经验规则。

### 8.3 Backend-Neutral Core

核心 Planner 和 Profile schema 不绑定单一后端。

### 8.4 Backend-Specific Adapters

参数生成、日志诊断和健康检查由 adapter 负责。

### 8.5 Safe Search

自动调优不得无约束地消耗资源或导致设备不稳定。

### 8.6 Reproducible

每个结果应记录：

- 模型 revision；
- 后端版本；
-驱动；
- OS；
- 启动参数；
- workload；
- 环境变量；
- benchmark 原始结果。

### 8.7 Local-First

默认不上传模型、日志和机器信息。

---

## 9. 总体架构

```text
                           ┌────────────────────┐
                           │ CLI / Python / API │
                           └─────────┬──────────┘
                                     │
                           ┌─────────▼──────────┐
                           │   Orchestrator     │
                           └─────────┬──────────┘
                                     │
       ┌─────────────────────────────┼─────────────────────────────┐
       │                             │                             │
┌──────▼──────┐              ┌──────▼──────┐              ┌──────▼──────┐
│ Environment │              │   Planner   │              │   Doctor    │
│ Inspector   │              │             │              │             │
└──────┬──────┘              └──────┬──────┘              └──────┬──────┘
       │                             │                             │
       │                    ┌────────▼────────┐                    │
       │                    │ KVScope Core    │                    │
       │                    └────────┬────────┘                    │
       │                             │                             │
       └─────────────────────────────┼─────────────────────────────┘
                                     │
                           ┌─────────▼──────────┐
                           │ Runtime Adapters   │
                           │ vLLM / SGLang /    │
                           │ llama.cpp / ...    │
                           └─────────┬──────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │                    │                    │
       ┌────────▼────────┐  ┌────────▼────────┐  ┌────────▼────────┐
       │ Process Manager │  │ Benchmark Agent │  │ Telemetry       │
       └────────┬────────┘  └────────┬────────┘  └────────┬────────┘
                └────────────────────┼────────────────────┘
                                     │
                           ┌─────────▼──────────┐
                           │   Tuning Engine    │
                           └─────────┬──────────┘
                                     │
                           ┌─────────▼──────────┐
                           │ Profile Registry   │
                           └────────────────────┘
```

---

## 10. 核心模块

### 10.1 Environment Inspector

负责：

- OS；
- CPU；
- GPU / NPU；
-内存；
-驱动；
- CUDA / ROCm / Metal；
- Python；
-容器；
-后端安装状态；
-端口和磁盘；
-温度和功耗能力。

输出标准化 `EnvironmentSnapshot`。

### 10.2 Planner

输入：

- ModelSpec；
- HardwareSpec；
- WorkloadSpec；
- Objective；
- Constraints；
- Backend availability。

输出多个 `PlanCandidate`。

Planner 分阶段过滤：

```text
Compatibility Filter
    ↓
Memory Feasibility Filter
    ↓
Safety Rules
    ↓
Heuristic Ranking
    ↓
Known Profile Boost
    ↓
Candidate Plans
```

### 10.3 Runtime Adapter

统一接口：

```python
class RuntimeAdapter(Protocol):
    backend_id: str

    def inspect_support(self, context) -> SupportReport: ...

    def render_command(self, plan) -> LaunchCommand: ...

    def launch(self, command) -> RuntimeHandle: ...

    def health_check(self, handle) -> HealthReport: ...

    def parse_logs(self, logs) -> list[Diagnosis]: ...

    def collect_metrics(self, handle) -> RuntimeMetrics: ...

    def stop(self, handle) -> None: ...
```

首批 adapter：

- vLLM；
- llama.cpp。

第二批：

- SGLang；
- LMDeploy；
- MLX；
- ONNX Runtime GenAI。

### 10.4 Doctor

Doctor 使用：

- 结构化错误码；
- 正则 signature；
- 版本化知识库；
- 运行环境；
- 当前配置；
- KVScope 估算；
- 后端 adapter。

诊断输出：

```text
diagnosis
confidence
evidence
recommended_patch
validation_steps
```

### 10.5 Benchmark Agent

需要支持：

- OpenAI-compatible API；
- 原生 llama.cpp endpoint；
- 冷启动；
- streaming；
- 多轮；
- 长前缀；
- 多模态；
- 并发；
-取消；
-异常率。

### 10.6 Tuning Engine

早期策略：

1. 规则式缩小空间；
2. 网格搜索；
3. successive halving；
4. 基于历史 profile 的 warm start。

后期可考虑：

- Bayesian optimization；
- contextual bandit；
- learned cost model。

不建议第一版使用复杂 AutoML。

### 10.7 Profile Registry

Profile 类型：

- community；
- official；
- local；
- generated；
- deprecated。

Profile 必须有可信度：

- unverified；
- self-reported；
- reproducible；
- maintainer-verified；
- CI-verified。

---

## 11. 与 KVScope 的关系

KVScope 是 InferPilot 的静态分析内核。

### KVScope 提供

- 权重内存；
- KV Cache；
- runtime overhead 范围；
- feasibility；
-最大上下文；
-最大并发；
-内存约束解释。

### InferPilot 增加

- 环境检测；
-后端选择；
-命令生成；
-进程管理；
-日志诊断；
- benchmark；
-自动调优；
-profile 持久化。

依赖方向：

```text
InferPilot → KVScope
KVScope ↛ InferPilot
```

---

## 12. 与 EdgeBench 的关系

EdgeBench 可作为独立 benchmark 协议和公开数据项目。

InferPilot 负责运行和调优。

EdgeBench 负责：

- workload schema；
- metric schema；
-结果验证；
-公开 leaderboard；
-社区提交；
-硬件数据集。

```text
InferPilot generates results
          ↓
EdgeBench validates and stores results
          ↓
Profiles improve planning
```

---

## 13. Workload 模型

```yaml
schema_version: "0.1"
workload_id: edge-chat
input:
  prompt_tokens:
    p50: 512
    p95: 2048
  output_tokens:
    p50: 128
    p95: 512
traffic:
  concurrency: [1, 2, 4]
  duration_seconds: 120
objectives:
  - p95_ttft_ms
  - decode_tps
  - success_rate
```

首批 suite：

- `interactive-chat`；
- `long-prefix-intent`；
- `rag-answering`；
- `agent-planning`；
- `vision-single-image`；
- `throughput-batch`。

---

## 14. Objective 与 Constraint

Objective：

```text
minimize_p95_ttft
maximize_decode_tps
maximize_request_throughput
maximize_context
minimize_memory
minimize_power
balanced
```

Constraint：

```text
peak_memory_gib <= 14.5
p95_ttft_ms <= 1000
success_rate >= 0.99
context_length >= 8192
temperature_c <= 80
```

Planner 和 Tuner 必须区分：

- 硬约束；
- 软目标；
- guardrail。

---

## 15. v0.1 产品范围

v0.1 只做：

### 平台

- Linux；
- Jetson Linux；
- macOS 可作为 llama.cpp / MLX 的实验支持。

### 后端

- vLLM；
- llama.cpp。

### 命令

- `inspect`；
- `plan`；
- `doctor`；
- `launch`；
- `benchmark`。

`tune` 进入 v0.2。

### 模型

- Qwen Dense；
- LLaMA；
- DeepSeek Distill；
- 常见 GGUF 模型。

### 硬件

- NVIDIA CUDA GPU；
- Jetson Orin；
- Apple Silicon 实验支持。

### 目标

第一版只需要证明：

> 对一个给定模型和一台受支持机器，InferPilot 能生成一个可运行配置，并通过 benchmark 验证。

---

## 16. v0.1 验收标准

- [ ] 自动检测当前设备；
- [ ] 解析模型；
- [ ] 调用 KVScope 判断内存；
- [ ] 生成至少 SAFE/BALANCED 两套方案；
- [ ] 为 vLLM 生成命令；
- [ ] 为 llama.cpp 生成命令；
- [ ] 启动和停止进程；
- [ ] 执行健康检查；
- [ ] 解析至少 20 种常见错误；
- [ ] 执行 OpenAI-compatible benchmark；
- [ ] 保存可复现 profile；
- [ ] 输出 Markdown 报告；
- [ ] 在 Jetson Orin NX 和一台常规 GPU 或 Mac 上完成端到端验证。

---

## 17. 技术路线

### 阶段 0：基础资产

前置条件：

- KVScope Core；
- Model registry；
- Hardware registry；
- Backend profile；
- 现有 LLM API benchmark 工具整理；
- 错误日志样本库。

### 阶段 1：Planner MVP

目标：

```text
inspect → plan → render command
```

交付：

- EnvironmentSnapshot；
- RuntimeAdapter；
- PlanCandidate；
- SAFE/BALANCED；
- vLLM / llama.cpp。

### 阶段 2：Controlled Launch

目标：

```text
plan → launch → health check → stop
```

交付：

- Process Manager；
- 日志归档；
- 超时；
- 端口冲突处理；
- 资源清理；
- crash summary。

### 阶段 3：Benchmark

目标：

```text
launch → benchmark → report → profile
```

交付：

- TTFT；
- TPS；
-并发；
-峰值内存；
-标准 workload；
-结果 schema。

### 阶段 4：Doctor

目标：

```text
failure → diagnosis → patched plan
```

交付：

- signature database；
- root cause ranking；
-推荐参数 patch；
-验证命令。

### 阶段 5：Tune

目标：

```text
constraints + objective → validated best profile
```

交付：

-参数空间；
-安全边界；
-搜索策略；
-early stop；
-warm start；
-comparison report。

### 阶段 6：Community Profiles

目标：

- 可提交；
- 可验证；
- 可复用；
- 可查询；
- 可标记过期。

### 阶段 7：Heterogeneous and Distributed

后续方向：

- AMD；
- Intel；
- Android；
- NPU；
- 多设备；
-局域网节点；
-能力感知路由；
-失败漂移。

---

## 18. 里程碑建议

### M0：KVScope Release

完成静态估算核心。

### M1：InferPilot 0.1

- vLLM；
- llama.cpp；
- inspect；
- plan；
- launch；
- benchmark。

### M2：InferPilot 0.2

- doctor；
-基础 tune；
- SGLang；
- profile registry。

### M3：InferPilot 0.3

- Web dashboard；
- EdgeBench submission；
- 社区 profile；
- Mac / AMD profile。

### M4：InferPilot 1.0

- 稳定 adapter API；
- 稳定 profile schema；
- 可复现 benchmark；
- 100+ 经过验证的模型 × 硬件组合；
- 可供第三方工具调用的 SDK。

---

## 19. 推荐仓库划分

建议独立仓库：

```text
edge-infer-lab/
├── kvscope
├── inferpilot
├── edgebench
└── inference-profiles
```

早期若维护资源有限：

```text
kvscope/
inferpilot/
```

Profile 数据可暂时保存在 InferPilot 仓库中，规模扩大后再拆分。

---

## 20. Profile Schema 草案

```yaml
schema_version: "0.1"
profile:
  id: qwen35-4b-orin-vllm-safe
  status: validated
  created_at: 2026-07-26

model:
  id: Qwen/Qwen3.5-4B
  revision: main
  artifact:
    format: safetensors
    quantization: awq

hardware:
  id: jetson-orin-nx-16gb
  snapshot_hash: sha256:...

software:
  os: Ubuntu 22.04
  backend:
    id: vllm
    version: 0.x
  python: 3.11
  cuda: "12.6"

configuration:
  command:
    - vllm
    - serve
    - Qwen/Qwen3.5-4B
  args:
    dtype: float16
    max_model_len: 4096
    max_num_seqs: 1
    gpu_memory_utilization: 0.92
    enforce_eager: true

validation:
  suite: interactive-chat-v0.1
  status: passed
  metrics:
    p50_ttft_ms: 721
    p95_ttft_ms: 938
    decode_tps: 18.7
    peak_memory_gib: 14.6
  raw_result_digest: sha256:...
```

---

## 21. Doctor 知识库草案

```yaml
id: vllm-kv-cache-insufficient
backend: vllm
versions:
  - ">=0.x,<1.0"
match:
  any:
    - "No available memory for the cache blocks"
    - "The model's max seq len is larger than the maximum number of tokens"
diagnosis:
  code: KV_CACHE_INSUFFICIENT
  title: KV Cache capacity is insufficient
recommendations:
  - action: reduce
    parameter: max_model_len
  - action: reduce
    parameter: max_num_seqs
  - action: lower_dtype
    parameter: kv_cache_dtype
confidence: high
```

知识库规则必须：

- 带后端版本；
- 带来源；
- 带测试；
- 可废弃；
- 不将单一字符串匹配视为绝对结论。

---

## 22. 自动调优安全策略

自动调优必须设置：

- 最大试验次数；
- 最大运行时间；
- 内存安全余量；
- 温度上限；
- 单次失败恢复；
- 子进程清理；
- 磁盘日志上限；
- 禁止危险参数；
- 不自动执行 root 操作；
- 不自动修改系统驱动。

调优流程：

```text
Static safe bounds
    ↓
Baseline profile
    ↓
One-dimensional probes
    ↓
Candidate pruning
    ↓
Multi-parameter search
    ↓
Repeatability validation
    ↓
Final profile
```

---

## 23. 可观测性

每次执行分配：

- `run_id`；
- `plan_id`；
- `profile_id`；
- `request_id`。

事件：

```text
environment.detected
plan.generated
runtime.launching
runtime.ready
benchmark.started
benchmark.completed
runtime.failed
doctor.diagnosed
profile.saved
```

本地日志使用 JSONL，方便后续 Web UI 和问题复现。

---

## 24. 开源策略

### 24.1 许可证

建议 Apache-2.0：

- 允许企业采用；
- 包含专利授权条款；
- 与 AI Infra 生态兼容性较好。

### 24.2 公司知识产权边界

必须：

- clean-room 实现；
- 不复制公司内部 Agent One/Ailyn 代码；
- 不公开未授权内部接口；
- 不提交内部模型、日志和数据；
- 对可能涉及专利的实现先做边界审查；
- 开源仓库使用个人环境重新实现和验证。

### 24.3 社区贡献入口

优先开放：

- hardware profile；
- backend adapter；
- error signature；
- benchmark result；
- model adapter；
-文档和案例。

---

## 25. 项目传播策略

InferPilot 的传播不能只展示架构图，应展示“前后对比”。

案例标题：

1. **I gave InferPilot a model and a Jetson; it produced a working vLLM command.**
2. **Why this 4B model OOMs at 32K context on a 16GB device.**
3. **vLLM vs llama.cpp on the same edge device: configuration, memory and TTFT.**
4. **Turn an OOM log into a validated deployment profile.**

README 首屏：

```text
Model + Hardware
      ↓
inferpilot plan
      ↓
Runnable command
      ↓
Benchmark report
```

---

## 26. 主要风险

### 26.1 范围过大

缓解：

- 第一版只支持两个后端；
- 每个 adapter 独立；
- 不做 Web UI；
- 不做分布式调度；
- 不承诺所有模型。

### 26.2 调优结果不可迁移

缓解：

- profile 绑定版本；
- 保留 EnvironmentSnapshot；
- 明确适用范围；
- 同类硬件只作为 warm start；
- 实机重新验证。

### 26.3 后端参数频繁变化

缓解：

- adapter 版本化；
- capability detection；
- CLI help parsing 可作为辅助；
- profile 带 backend version；
- CI 运行 smoke tests。

### 26.4 设备差异导致误判

缓解：

- 静态规划只生成候选；
- 最终结论依赖健康检查和 benchmark；
- 使用 KVScope 置信区间；
- 明确不可验证项。

---

## 27. 关键决策

### 决策 1：先做 KVScope

原因：

- 是 InferPilot Planner 的必需依赖；
- 独立可发布；
- 开发和验证周期更短；
- 可先建立社区认知。

### 决策 2：InferPilot 不做新推理引擎

原因：

- 维护成本过高；
- 与成熟后端正面竞争；
- 用户真正缺少的是选择、配置、诊断和验证层。

### 决策 3：v0.1 只支持 vLLM 和 llama.cpp

原因：

- 分别代表服务型 GPU 后端和广泛本地后端；
- 便于验证 adapter 抽象；
- 覆盖 NVIDIA、Jetson、Mac 和 CPU 的主要路径。

### 决策 4：实测 Profile 是长期护城河

代码可以被复制，但持续积累的：

- 设备；
-模型；
-后端；
-版本；
-参数；
-性能；
-错误；

组合数据更难复制。

---

## 28. 建议的起步顺序

### 第一步：KVScope Core

交付：

- 公式；
-模型解析；
-硬件 profile；
- CLI；
-报告。

### 第二步：整理现有 benchmark 工具

将已有 OpenAI-compatible API 压测能力提炼为独立库：

- streaming parser；
- TTFT；
- input/output TPS；
-并发；
-报告 schema。

### 第三步：InferPilot Adapter 骨架

实现：

- vLLM；
- llama.cpp；
- command renderer；
- health checker；
- log parser。

### 第四步：端到端 Demo

优先验证：

- Jetson Orin NX 16GB；
- Qwen 3B/4B；
- SAFE 配置；
- OOM 配置；
- Doctor 修复；
- benchmark 报告。

---

## 29. 结论

InferPilot 的价值不在于增加一个新的推理框架，而在于将碎片化的推理知识转化为可复现的工程流程：

```text
选择
→ 配置
→ 启动
→ 诊断
→ 测量
→ 调优
→ 保存
→ 复用
```

KVScope 负责静态可行性和内存解释，InferPilot 负责执行闭环，EdgeBench 负责标准化和社区数据。

最小成功标准不是 GitHub star 数，而是：

> **用户在一台受支持设备上，仅提供模型和目标，就能获得一套可运行、可解释、经过 benchmark 验证的推理配置。**
