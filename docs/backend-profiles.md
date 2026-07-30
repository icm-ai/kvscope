# Backend Profiles & Memory Models in KVScope

本文档说明 KVScope Phase 6 中 Backend Profile 的结构、隔离机制、匹配打分与三项核心原则。

## 1. 核心语义与四大原则

> [!IMPORTANT]
> 1. **Unknown ≠ Zero**：未知 Runtime Overhead 不等于 0 开销。数据不完整时主动报错（`IncompleteBackendProfileError`），绝不生成过于乐观的零开销结果。
> 2. **Completeness与Trustworthiness正交**：`is_partial` 严格仅由 Profile 是否缺失字段或为 Template 决定；Profile 是否已验证（`UNVERIFIED` / `EXPERIMENTAL`）仅降级 `confidence` 并产生警告，不影响 `is_partial=False`。
> 3. **Template ≠ Unverified Profile**：通用模板（Template Profile）放置于 `examples/templates/` 目录中，不作为生产 Profile 存在于正式 Registry (`profiles/backends/`)。
> 4. **Template 不参与正常 Profile 选择**：CLI 命令 `kvscope backend list` 与默认 `resolve_backend_profile()` 会隔离并排除模板。只有用户显式加载模板文件并提供完整 `user_overrides` 或设置 `allow_incomplete_profile=True` 时才允许参与估算。

### 正交维度矩阵

| Profile 情况 | `is_partial` | Confidence | 语义与可用于 Feasibility 判断 |
| :--- | :---: | :---: | :--- |
| 已验证且字段完整 | `False` | High / Exact | 完整数学估算，可直接用于 Phase 7 |
| 未验证但字段完整 (如社区贡献) | `False` | Low / Unknown | 完整数学估算，低置信度，允许进入 Phase 7 |
| Template、字段缺失 | `True` | Unknown | 局部/不完整估算，**禁止**进入 Phase 7 可行性决策 |
| Template 被完整 Overrides 补齐 | `False` | 视 Evidence 决定 | 显式完整估算，可进入 Phase 7 |

## 2. Generic Template 位置与示例 (v0.1)

模板文件独立存放于 [`examples/templates/vllm-generic-template.yaml`](file:///Users/mingchen/workspace/personal/kvscope/examples/templates/vllm-generic-template.yaml) 和 [`examples/templates/llama-cpp-generic-template.yaml`](file:///Users/mingchen/workspace/personal/kvscope/examples/templates/llama-cpp-generic-template.yaml)。

```yaml
schema_version: "0.1"
profile_id: vllm-generic-template
backend_id: vllm
display_name: vLLM Generic Template
aliases:
  - vllm
  - vllm-template
version_specifier: ">=0.4.0,<1.0.0"

supported_memory_topologies:
  - discrete
  - unified

supported_vendors:
  - nvidia
  - amd
  - generic

memory_model:
  base_runtime:
    lower_bytes: 268435456
    expected_bytes: 536870912
    upper_bytes: 1073741824
  per_billion_parameters:
    lower_bytes: 33554432
    expected_bytes: 67108864
    upper_bytes: 134217728
  workspace_ratio_of_resident_weights:
    lower: "0.02"
    expected: "0.05"
    upper: "0.10"
  graph_capture_reserve:
    lower_bytes: 536870912
    expected_bytes: 1073741824
    upper_bytes: 2147483648
  backend_buffers:
    lower_bytes: 67108864
    expected_bytes: 134217728
    upper_bytes: 268435456
  allocator_margin_ratio_of_subtotal:
    lower: "0.03"
    expected: "0.05"
    upper: "0.08"
  graph_capture_supported: true
  kv_block_size: 16

confidence: unknown
status: unverified
```

## 3. Resolver 匹配机制与打分

Resolver 根据传入的 `backend_id`、`version` 以及可选的 `hardware`，对候选 Profiles (`profiles/backends/`) 进行评估与打分：

1. **Backend Match**: 检查 `backend_id` 或 `aliases` 是否匹配。
2. **Version Specifier Match**: 使用 `packaging.specifiers` 验证 `version` 是否满足 `version_specifier`。
3. **Hardware Constraints Match**: 验证 `memory_topology` 和 `vendor` 是否在 Profile 支持范围内。
4. **Specificity Scoring**:
   - 精确 Profile ID 匹配得 +100 分。
   - Explicit 版本依赖得 +50 分，符合版本范围得 +20 分。
   - 硬件拓扑与 Vendor 匹配得 +20 分。
   - `verified` 状态得 +10 分。

当存在最高分并列且候选集不唯一时，抛出 `BackendProfileAmbiguousError`。
