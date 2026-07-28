# KVScope 公式：Weight Engine

Weight Engine 是纯计算层，不访问网络、不读取文件，也不解析
`config.json`、safetensors 或 GGUF。上游 resolver 如需提供文件信息，必须先
构造 `WeightArtifactSummary`。

## 公共 API

```python
from kvscope.api import estimate_weight_memory
from kvscope.domain import WeightArtifactSummary, WeightDType

estimate = estimate_weight_memory(1_000_000_000, dtype=WeightDType.INT4)
artifact_estimate = estimate_weight_memory(
    artifact=WeightArtifactSummary(
        payload_bytes=2_000_000_000,
        metadata_bytes=16_384,
        alignment_bytes=256,
    )
)
```

结果类型为 `WeightMemoryEstimate`，拆分返回 quantized/unquantized payload、
scale、zero-point、metadata、alignment、total、effective bits、估算方法、
置信度、假设和 warning。`to_estimate_component()` 可将总值适配到已有的
`EstimateComponent`。

## Parameter Count 模式

```text
payload_bytes = ceil(parameter_count × bits_per_weight / 8)
total_bytes = payload_bytes + metadata_bytes + alignment_overhead_bytes
```

FP32、FP16、BF16、FP8、INT8 和 INT4 分别使用 32、16、16、8、8 和 4
bits/weight；也可以通过 `bits_per_weight` 使用自定义精度。所有乘法使用整数
或精确的 `Fraction`，不使用 GiB 浮点数参与核心计算。

## Group-wise Quantization 模式

```text
quantized_payload = ceil(quantized_parameter_count × quantization_bits / 8)
number_of_groups = ceil(quantized_parameter_count / group_size)
scale_overhead = number_of_groups × scale_bytes_per_group
zero_point_overhead = number_of_groups × zero_point_bytes_per_group
unquantized_payload =
    ceil(unquantized_parameter_count × unquantized_bits_per_weight / 8)

total = quantized_payload
      + unquantized_payload
      + scale_overhead
      + zero_point_overhead
      + metadata_bytes
      + alignment_overhead
```

`alignment` 是可选的正整数对齐边界；`alignment_bytes` 是已经由上游提供的
对齐开销。两者都只计入一次。未量化参数可以直接给出数量，或给出
`unquantized_fraction`；Fraction 产生的参数数量向上取整。若量化和未量化数量
同时显式提供，它们必须覆盖总参数量且不能超过总参数量。

特别注意：**INT4 的 4 bits/parameter 是理论 payload，实际权重内存可能包含
scale、zero-point、padding、metadata 和未量化参数。** 因此不能将 INT4
永远解释为每参数严格 0.5 byte。

## Artifact Summary 模式

```text
artifact_storage_bytes = payload_bytes + metadata_bytes + alignment_bytes
estimated_resident_weight_bytes = artifact_storage_bytes
```

该模式只消费上游已经解析的字节摘要。artifact storage bytes 是磁盘/产物
表示的字节数，不等同于设备常驻内存；mmap、加载器缓冲区、运行时开销和
allocator 行为不在本阶段估算范围内，结果会明确给出 warning。
