# Runtime Overhead Engine & Calculation Guide

本文档详细描述 KVScope Phase 6 Runtime Overhead Engine 的纯计算逻辑、公式定义与不确定性区间传播规则。

## 1. 引擎职责与边界

Runtime Overhead Engine 的目标是精确计算将模型部署到特定后端框架（Backend Profile）和硬件（Hardware Profile）上时，**模型权重之外、KV Cache 之外**所需的运行时固定及动态开销总和。

> [!CAUTION]
> 1. 本引擎为**纯计算引擎**，绝对不触发后端执行、不调用 PyTorch / CUDA 运行时、不发网络请求。
> 2. **Unknown ≠ Zero**：模板 Profile 或不完整 Profile 默认阻断计算并抛出 `IncompleteBackendProfileError`，不允许当作 0 开销生成过于乐观的结果。

## 2. 计算公式与分项分解

### (1) Base Runtime (`base_runtime`)
推理引擎进程初始化、基础 Runtime 库装载等固定开销。

### (2) Parameter Scaled Overhead (`parameter_scaled_overhead`)
与模型参数量成正比的开销（如 Parameter Meta / Tensor Descriptors）。使用无损整数向上取整除法 `ceil_div(n, 1_000_000_000)` 计算，不包含任何 `1e9` 浮点路径。
```text
lower_p = ceil_div(parameter_count × per_billion.lower_bytes, 1_000_000_000)
expected_p = ceil_div(parameter_count × per_billion.expected_bytes, 1_000_000_000)
upper_p = ceil_div(parameter_count × per_billion.upper_bytes, 1_000_000_000)
```

### (3) Workspace Overhead (`workspace`)
推理计算时的 Scratchpad 临时工作区空间。
```text
workspace = resident_weight_bytes × workspace_ratio_of_resident_weights
```

### (4) Graph Capture Reserve (`graph_capture`)
CUDA Graph / Executive Graph Capture 预分配保留空间。若 `graph_capture_enabled = False`，则为 0。若后端不支持 Graph Capture 却显式开启，将抛出 `RuntimeOverheadInputError`。

### (5) Backend Buffers (`backend_buffers`)
后端通量 Buffer、通信 Block 与框架私有缓冲区。

### (6) Subtotal Before Allocator Margin
```text
subtotal_before_allocator_margin =
  base_runtime + parameter_scaled_overhead + workspace + graph_capture + backend_buffers
```

### (7) Allocator Margin (`allocator_margin`)
PyTorch / CUDA Allocator 的碎片化（Fragmentation）与 Slot Margin 预留。仅按 `subtotal` 计算一次增量：
```text
allocator_margin = subtotal_before_allocator_margin × allocator_margin_ratio_of_subtotal
```

### (8) Total Runtime Overhead (`total_runtime_overhead`)
```text
total_runtime_overhead = subtotal_before_allocator_margin + allocator_margin
```

## 3. 区间与精度约束

- 所有中间计算与最终存储采用**整数 bytes**。
- Decimal 比例乘法及除法统一向上取整 (`math.ceil`)。
- 输入或参数为区间 (`ByteRange` / `RatioRange`) 时，遵循区间算术规约：
  ```text
  [l1, e1, u1] + [l2, e2, u2] = [l1 + l2, e1 + e2, u1 + u2]
  ```
