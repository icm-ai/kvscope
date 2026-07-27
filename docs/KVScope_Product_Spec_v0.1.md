# KVScope 产品需求与技术规格 v0.1

> **项目名称**：KVScope  
> **副标题**：Interactive LLM Memory Analysis and KV Cache Visualization Toolkit  
> **文档状态**：Draft  
> **版本**：0.1  
> **建议许可证**：Apache-2.0  
> **目标读者**：LLM 应用开发者、推理工程师、边缘 AI 开发者、项目维护者和贡献者

---

## 1. 文档目的

本文档定义 KVScope v0.1 的产品定位、目标用户、核心问题、功能范围、非目标、接口形态、验收标准与版本路线。

它用于回答以下问题：

1. KVScope 为什么存在？
2. 第一版必须解决什么问题？
3. 哪些功能应当明确推迟？
4. 什么状态可以称为 v0.1 可发布？
5. 项目如何为后续 InferPilot 提供基础能力？

本文档不描述详细代码结构、类设计和算法实现；这些内容见《KVScope 系统架构设计 v0.1》。

---

## 2. 项目定位

### 2.1 一句话定位

> **KVScope 是一个面向 LLM 推理的内存估算、KV Cache 分析与部署可行性判断工具。**

用户输入模型、精度、上下文长度、并发和硬件信息，KVScope 输出：

- 模型权重占用；
- KV Cache 占用；
- 运行时预留；
- 总内存需求；
- 最大可行上下文或并发；
- OOM 风险解释；
- 可操作的部署调整建议。

### 2.2 核心价值主张

KVScope 解决的不是“如何启动一个模型”，而是：

> **在真正启动之前，解释模型为什么能跑、为什么不能跑，以及应该改哪个参数。**

### 2.3 项目边界

KVScope 是：

- 推理前的静态估算器；
- 推理后的结果校准工具；
- KV Cache 与内存结构的可视化工具；
- 可被 CLI、Web 和 InferPilot 复用的分析库。

KVScope 不是：

- 推理引擎；
- 模型服务框架；
- GPU kernel profiler；
- 训练显存计算器；
- 自动部署和自动调优系统。

---

## 3. 背景与问题定义

### 3.1 典型问题

LLM 本地部署中，用户经常遇到以下情况：

- 权重看起来能放入显存，但启动时仍然 OOM；
- 同一个模型在不同后端中的显存占用差异明显；
- 上下文从 4K 增加到 32K 后，显存突然不可接受；
- GQA、MQA、MHA 对 KV Cache 的影响难以直观理解；
- 多模态输入引入额外视觉 token，但用户没有明确预算；
- CUDA Graph、workspace、allocator fragmentation 等运行时开销未被纳入；
- 统一内存设备上的“可加载”不等于“可用”；
- 估算公式存在，但缺少可直接用于部署决策的工具。

### 3.2 当前解决方式的缺陷

| 现有方式 | 主要缺陷 |
|---|---|
| 阅读模型卡与框架文档 | 信息分散，难以组合 |
| 手工套公式 | 容易遗漏 GQA、精度、batch 和后端开销 |
| 直接启动试错 | 成本高，失败后仍不清楚根因 |
| `nvidia-smi` 或系统监控 | 只能看到结果，不能解释结构 |
| 单框架 calculator | 缺少跨后端、跨硬件的一致模型 |
| 论文公式 | 不直接映射为工程参数建议 |

---

## 4. 目标用户

### 4.1 LLM 应用开发者

典型问题：

- RTX 4060 8GB 能否运行 Qwen 4B/8B？
- 量化到 INT4 后能支持多长上下文？
- 单用户聊天与四路并发分别需要多少显存？

### 4.2 推理工程师

典型问题：

- vLLM 的 KV Cache 预算为什么不足？
- `max_model_len`、`max_num_seqs` 和 KV dtype 如何影响容量？
- 估算与实际峰值为什么有偏差？

### 4.3 边缘 AI 开发者

目标硬件包括：

- Jetson Orin 系列；
- Apple Silicon；
- AMD Ryzen AI PC；
- Intel AI PC；
- Android / ARM SoC；
- CPU-only 设备。

典型问题：

- 统一内存设备应该预留多少系统空间？
- 端侧设备的可运行上限在哪里？
- 模型权重、KV Cache、视觉编码器如何共同占用内存？

### 4.4 教学与研究用户

典型需求：

- 直观看懂 GQA 如何降低 KV Cache；
- 比较不同上下文和 batch 的增长曲线；
- 复现实测并校准估算误差。

---

## 5. 核心使用场景

### 5.1 场景 A：判断模型能否运行

输入：

```yaml
model: Qwen/Qwen3.5-4B
weight_dtype: int4
kv_dtype: fp16
context_length: 8192
batch_size: 1
hardware: jetson-orin-nx-16gb
backend: vllm
```

输出示例：

```text
模型权重估算：2.65 GiB
KV Cache 估算：1.12 GiB
运行时预留：2.40 GiB
系统安全预留：2.00 GiB
总需求：8.17 GiB
可用预算：13.50 GiB

结论：可运行
风险等级：低
```

### 5.2 场景 B：解释 OOM

用户提供当前配置：

```yaml
model: Qwen/Qwen3.5-4B
context_length: 32768
max_num_seqs: 4
hardware_memory_gib: 16
```

输出：

```text
主要风险：KV Cache 预算过高
影响最大的参数：
1. max_num_seqs
2. context_length
3. kv_dtype

建议：
- 将 max_num_seqs 从 4 降为 1；
- 将 context_length 从 32768 降为 8192；
- 后端支持时使用 FP8 KV Cache；
- 将 gpu_memory_utilization 控制在安全区间内。
```

### 5.3 场景 C：比较硬件

比较同一个模型在以下设备上的可行性：

- RTX 4060 8GB；
- Jetson Orin NX 16GB；
- Mac mini M4 16GB；
- 32GB AMD APU 统一内存设备。

输出包括：

- 是否可运行；
- 推荐量化；
- 推荐最大上下文；
- 估算吞吐风险提示；
- 是否涉及统一内存争用。

### 5.4 场景 D：分析上下文增长

输出以下曲线：

- context length → KV Cache；
- batch / concurrency → KV Cache；
- KV dtype → KV Cache；
- MHA / GQA / MQA → KV Cache；
- 模型层数 → KV Cache。

### 5.5 场景 E：导出机器可读结果

输出 JSON，供 InferPilot 或 CI 使用：

```json
{
  "schema_version": "0.1",
  "model": {
    "id": "Qwen/Qwen3.5-4B",
    "architecture": "qwen"
  },
  "memory_gib": {
    "weights": 2.65,
    "kv_cache": 1.12,
    "runtime_overhead": 2.4,
    "system_reserve": 2.0,
    "total": 8.17
  },
  "feasibility": {
    "status": "feasible",
    "risk": "low"
  }
}
```

---

## 6. v0.1 功能范围

### 6.1 模型配置解析

v0.1 支持：

- 从本地 Hugging Face `config.json` 解析；
- 从 Hugging Face 模型仓库名称解析；
- 从用户显式参数解析；
- 将不同模型字段归一化为内部模型描述。

首批架构：

- LLaMA 系列；
- Qwen 系列；
- DeepSeek Dense；
- DeepSeek MoE 的权重估算可进入实验支持，但不承诺完整运行时估算。

需要解析的字段：

- `num_hidden_layers`；
- `hidden_size`；
- `num_attention_heads`；
- `num_key_value_heads`；
- `head_dim`；
- `vocab_size`；
- `intermediate_size`；
- `num_experts`；
- `num_experts_per_tok`；
- `tie_word_embeddings`；
- 最大上下文长度；
- 参数量或可推导参数量。

### 6.2 精度支持

权重精度：

- FP32；
- FP16；
- BF16；
- FP8；
- INT8；
- INT4；
- 用户自定义平均 bits-per-weight。

KV Cache 精度：

- FP32；
- FP16；
- BF16；
- FP8；
- INT8；
- 用户自定义 bytes-per-element。

### 6.3 KV Cache 估算

基础公式：

```text
KV bytes =
2
× number_of_layers
× effective_sequence_tokens
× batch_or_active_sequences
× number_of_kv_heads
× head_dim
× bytes_per_kv_element
```

其中：

- `2` 分别代表 Key 与 Value；
- MHA、GQA、MQA 通过 `number_of_kv_heads` 统一表达；
- `effective_sequence_tokens` 可包含文本、视觉和系统前缀 token；
- paged KV Cache 与 block 对齐开销作为后端修正项处理。

### 6.4 权重占用估算

v0.1 至少提供两种模式：

1. **参数量模式**

```text
weight bytes = parameter_count × effective_bits_per_weight / 8
```

2. **文件模式**

通过 safetensors / GGUF 文件大小估算实际权重占用。

需要考虑：

- embedding 是否共享；
- 量化 group scale / zero-point 元数据；
- 混合精度层；
- MoE 总参数与激活参数的区别；
- mmap 与常驻内存的差别。

### 6.5 运行时开销模型

v0.1 不追求对所有后端精确建模，但必须显式拆分：

- engine / framework base overhead；
- CUDA Graph 或 graph capture 预留；
- temporary workspace；
- allocator safety margin；
- 系统保留；
- 统一内存设备的 OS 和其他应用占用。

每个后端 profile 需要给出：

- 默认固定预留；
- 按模型规模变化的预留；
- 安全系数；
- 置信等级。

### 6.6 硬件 Profile

首批内置硬件：

- NVIDIA RTX 4060 8GB；
- NVIDIA RTX 4090 24GB；
- NVIDIA Jetson Orin NX 16GB；
- Apple Silicon 16GB / 32GB 通用 profile；
- AMD APU 16GB / 32GB 通用 profile；
- 用户自定义硬件。

硬件字段：

```yaml
id: jetson-orin-nx-16gb
vendor: nvidia
device_family: jetson
memory:
  total_gib: 15.3
  architecture: unified
  default_system_reserve_gib: 2.0
compute:
  backend_support:
    - vllm
    - llama_cpp
    - tensorrt_llm
notes:
  - shared_with_os
  - thermal_constraints
```

### 6.7 部署可行性结论

输出状态：

- `feasible`：预计可运行且有合理余量；
- `tight`：预计可运行，但对上下文、并发或后台进程敏感；
- `infeasible`：理论预算已超过可用内存；
- `unknown`：信息不足或架构未支持。

风险等级：

- `low`；
- `medium`；
- `high`；
- `unknown`。

### 6.8 建议生成

v0.1 支持确定性建议：

- 降低上下文；
- 降低并发；
- 降低权重精度；
- 降低 KV dtype；
- 增加 CPU offload；
- 换用更低开销后端；
- 禁用或减少 graph capture；
- 减少视觉输入；
- 增加系统预留；
- 选择更小模型。

建议必须包含：

- 触发原因；
- 影响参数；
- 预计节省内存；
- 潜在性能代价。

### 6.9 CLI

建议命令：

```bash
kvscope inspect Qwen/Qwen3.5-4B
kvscope estimate Qwen/Qwen3.5-4B --weight-dtype int4 --context 8192
kvscope fit Qwen/Qwen3.5-4B --hardware jetson-orin-nx-16gb
kvscope compare Qwen/Qwen3.5-4B --hardware rtx4060-8gb,apple-unified-16gb
kvscope explain report.json
```

### 6.10 输出格式

v0.1 支持：

- Terminal；
- JSON；
- Markdown。

Web UI 可作为 v0.2 发布，但核心库应在 v0.1 中为 Web 做好 API 边界。

---

## 7. 非目标

v0.1 明确不做：

### 7.1 训练显存估算

不覆盖：

- optimizer states；
- gradients；
- ZeRO；
- FSDP；
- activation checkpointing；
- LoRA 训练开销。

### 7.2 精确性能预测

v0.1 不承诺准确预测：

- TTFT；
- prefill TPS；
- decode TPS；
- 功耗；
- 温度；
- 热降频。

这些能力属于 InferPilot 和 EdgeBench。

### 7.3 Kernel 级分析

不替代：

- Nsight Systems；
- Nsight Compute；
- PyTorch Profiler；
- Triton profiler。

### 7.4 自动启动后端

KVScope 不负责安装或启动 vLLM、SGLang、llama.cpp。

### 7.5 所有模型架构

第一版只承诺 LLaMA、Qwen 和常见 DeepSeek 配置。其他模型通过插件或社区贡献逐步增加。

---

## 8. 产品原则

### 8.1 解释优先

每个数字必须可以追溯到：

- 输入字段；
- 公式；
- 后端修正项；
- 安全系数；
- 置信等级。

### 8.2 估算与实测分离

报告必须区分：

- theoretical；
- calibrated；
- measured。

不得将经验值包装为精确公式。

### 8.3 默认保守

当信息不足时，应输出安全范围，而不是给出过于乐观的单点值。

### 8.4 可组合

核心分析器必须可作为 Python 库使用，CLI 和 Web 都是适配层。

### 8.5 开放数据

模型、硬件、后端开销和实测校准数据应使用可审查的 YAML/JSON 文件管理。

### 8.6 不隐藏不确定性

每项估算应提供：

- 来源；
- 置信等级；
- 误差范围；
- 缺失信息。

---

## 9. 交互与报告要求

### 9.1 终端输出

终端报告至少包含：

```text
Model
Hardware
Configuration
Memory Breakdown
Feasibility
Primary Constraints
Recommendations
Confidence
```

### 9.2 内存单位

内部统一使用 bytes，展示层支持：

- MB / GB；
- MiB / GiB。

默认展示 GiB，并明确单位，避免 GB/GiB 混淆。

### 9.3 可视化

Web 版本建议包含：

- 内存堆叠条；
- 上下文增长曲线；
- 并发增长曲线；
- 不同精度比较；
- 硬件容量线；
- 风险区间。

---

## 10. 数据来源与可信度

### 10.1 模型数据优先级

1. 本地权重文件和 config；
2. 用户显式输入；
3. 官方模型仓库 config；
4. 内置 registry；
5. 推断值。

### 10.2 硬件数据优先级

1. 运行时实际检测；
2. 用户显式输入；
3. 官方规格；
4. 内置通用 profile。

### 10.3 后端开销数据优先级

1. 同硬件同版本实测；
2. 同类硬件实测；
3. 框架官方文档；
4. 经验默认值。

---

## 11. 成功指标

### 11.1 技术指标

v0.1 发布标准：

- 支持至少 20 个公开模型配置；
- 支持至少 5 类硬件 profile；
- 支持 LLaMA、Qwen、DeepSeek Dense；
- KV Cache 基础公式单元测试覆盖率达到 95%；
- 核心库测试覆盖率达到 80%；
- 对至少 10 组真实部署进行校准；
- KV Cache 单项估算误差目标小于 3%；
- 总内存估算误差目标：
  - 已校准后端：小于 10%；
  - 未校准后端：明确给出区间，不承诺单点误差。

### 11.2 产品指标

- 用户可在 60 秒内完成第一次估算；
- README 首屏示例不超过 5 条命令；
- 无 GPU 的用户也能使用离线模式；
- JSON schema 稳定且有版本号；
- 错误信息提供直接修复建议。

### 11.3 社区指标

社区指标只作为运营目标，不作为产品验收条件：

- 首个公开版本获得真实 Issue 和配置贡献；
- 形成至少 10 个社区硬件 profile；
- 至少 3 位外部贡献者；
- 出现第三方项目集成 KVScope Core。

---

## 12. v0.1 验收清单

### 核心能力

- [ ] 从 Hugging Face config 解析模型结构；
- [ ] 支持用户手工输入模型结构；
- [ ] 支持 MHA/GQA/MQA；
- [ ] 计算权重占用；
- [ ] 计算 KV Cache；
- [ ] 计算后端开销范围；
- [ ] 计算系统安全预留；
- [ ] 输出 feasible/tight/infeasible；
- [ ] 输出建议及预计节省；
- [ ] 支持 Terminal/JSON/Markdown。

### 数据与质量

- [ ] Model registry；
- [ ] Hardware registry；
- [ ] Backend profile registry；
- [ ] JSON Schema；
- [ ] 公式单元测试；
- [ ] 黄金样例测试；
- [ ] 误差校准报告；
- [ ] 中英文 README；
- [ ] Apache-2.0 License；
- [ ] CONTRIBUTING.md；
- [ ] SECURITY.md。

---

## 13. 版本路线

### v0.1：Core Calculator

- 模型解析；
- 权重估算；
- KV Cache 估算；
- 硬件适配；
- CLI；
- JSON/Markdown 报告。

### v0.2：Interactive Web

- 静态 Web UI；
- 图表；
- URL 分享配置；
- GitHub Pages 部署；
- 浏览器端离线计算。

### v0.3：Runtime Calibration

- 读取 vLLM / SGLang / llama.cpp 运行结果；
- 导入实测峰值；
- 自动生成校准系数；
- 比较估算与实测。

### v0.4：Multimodal and MoE

- 视觉 token 预算；
- vision encoder 权重；
- MoE 权重和激活专家；
- DeepSeek 系列专项支持。

### v1.0：Stable Analysis API

- 稳定 Python API；
- 稳定 JSON schema；
- 可被 InferPilot、IDE、Web 和 CI 集成；
- 形成社区校准数据库。

---

## 14. 与 InferPilot 的关系

KVScope 负责回答：

> 当前配置需要多少内存，限制在哪里？

InferPilot 负责回答：

> 应该选择什么后端和参数，并通过实测找到更优配置。

KVScope 将向 InferPilot 暴露：

```python
estimate_memory(...)
evaluate_feasibility(...)
find_context_limit(...)
find_concurrency_limit(...)
explain_constraints(...)
generate_memory_recommendations(...)
```

KVScope 不依赖 InferPilot；InferPilot 依赖 KVScope Core。

---

## 15. 发布建议

首个公开版本应重点展示三个案例：

1. **为什么权重能放下但仍然 OOM？**
2. **GQA 如何降低 KV Cache？**
3. **Jetson Orin NX 16GB 到底能运行什么配置？**

README 首屏应具备：

- 一句话价值；
- 30 秒 GIF；
- 一条安装命令；
- 一个真实模型示例；
- 一张清晰的内存分解图；
- 在线 Demo 地址；
- “估算不是承诺”的可信度说明。

---

## 16. 结论

KVScope v0.1 的目标不是构建完美的通用推理模拟器，而是交付一个：

- 公式透明；
- 工程可用；
- 风险可解释；
- 可被其他工具复用；
- 能持续通过实测校准；

的 LLM 推理内存分析核心。

项目最终应稳定回答：

> **这个模型以当前精度、上下文和并发运行在这台设备上，需要多少内存；如果不能运行，最有效的调整是什么？**
