# Hardware Profiles & Memory Budgeting in KVScope

本文档说明 KVScope Phase 6 中 Hardware Profile 的数据结构、内存预留分类、计算公式与配置规范。

## 1. 概念与定位

Hardware Profile 描述硬件设备的物理内存总量、非模型内存预留（OS、显示、后台进程、设备特有开销）以及推荐安全 Headroom 比例。

> [!NOTE]
> Hardware Profile 描述的是**预算与分配上限估算**，而非实时系统可用内存。Unified Memory 与操作系统及其他进程共享，实际运行时可分配内存存在不确定性。

## 2. Profile Schema 结构 (v0.1)

Profiles 以 JSON 或 YAML 格式存储于 `profiles/hardware/` 目录。

```json
{
  "schema_version": "0.1",
  "profile_id": "generic-discrete-16gib",
  "name": "Generic Discrete GPU (16 GiB)",
  "vendor": "generic",
  "family": "discrete-gpu",
  "aliases": ["discrete-16gb", "discrete-16gib"],
  "memory_topology": "discrete",
  "total_memory": {
    "value": "16",
    "unit": "GiB"
  },
  "reserves": {
    "os_reserve": { "lower_bytes": 0, "expected_bytes": 0, "upper_bytes": 0 },
    "display_reserve": { "lower_bytes": 268435456, "expected_bytes": 536870912, "upper_bytes": 1073741824 },
    "background_process_reserve": { "lower_bytes": 0, "expected_bytes": 0, "upper_bytes": 0 },
    "device_specific_reserve": { "lower_bytes": 134217728, "expected_bytes": 268435456, "upper_bytes": 536870912 }
  },
  "recommended_headroom_ratio": {
    "lower": "0.05",
    "expected": "0.10",
    "upper": "0.15"
  },
  "supported_backend_ids": ["vllm", "llama_cpp"],
  "notes": ["Generic 16 GiB discrete GPU profile."],
  "evidence": [
    {
      "evidence_id": "generic-discrete-16gib-spec",
      "source_type": "theoretical_spec",
      "source": "Standard 16 GiB VRAM specification",
      "notes": "Generic profile derived from standard 16384 MiB VRAM layout."
    }
  ],
  "confidence": "unknown",
  "status": "unverified"
}
```

## 3. 内存预留分类

KVScope 将非模型预留严格拆分为：
- **os_reserve**: 操作系统核心开销（System / Unified Memory 下显著）。
- **display_reserve**: 显卡桌面渲染 / 窗口合成器占用。
- **background_process_reserve**: 后台应用或竞争进程预留。
- **device_specific_reserve**: 驱动与硬件架构固有的 context/allocator 预留。
- **user_reserve**: 用户在 CLI/API 显式传入的自定义预留。

## 4. 预算计算公式

```text
total_non_model_reserve =
  os_reserve + display_reserve + background_process_reserve + device_specific_reserve + user_reserve

allocatable_before_headroom.lower    = max(0, total_memory - total_non_model_reserve.upper)
allocatable_before_headroom.expected = max(0, total_memory - total_non_model_reserve.expected)
allocatable_before_headroom.upper    = max(0, total_memory - total_non_model_reserve.lower)

recommended_headroom = allocatable_before_headroom × recommended_headroom_ratio

recommended_allocatable.lower    = max(0, allocatable_before_headroom.lower - recommended_headroom.upper)
recommended_allocatable.expected = max(0, allocatable_before_headroom.expected - recommended_headroom.expected)
recommended_allocatable.upper    = max(0, allocatable_before_headroom.upper - recommended_headroom.lower)
```

## 5. Built-in Production Hardware Profiles

内置 Production Profiles 仅包含定义明确的通用容量配置：
- `generic-discrete-8gib`
- `generic-discrete-16gib`
- `generic-discrete-24gib`
- `generic-unified-16gib`
- `generic-unified-32gib`
- `generic-system-32gib`

Synthetic 测试 Profile 严禁放入 Production Registry。
