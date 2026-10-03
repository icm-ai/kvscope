# Static MoE weight analysis

When a resolved model provides MoE metadata, feasibility reports include an
optional `moe_weight_analysis` section with total parameter count, active
parameter count, expert count, experts selected per token, and the resident-weight
basis. It appears in `kvscope analyze`, `compare`, and `sweep` reports and is
available as `MoEWeightAnalysis` through the Python API.

```python
from kvscope.api import analyze_moe_weight_structure, resolve_model

model = resolve_model("local-or-registered-moe-model").spec
moe_analysis = analyze_moe_weight_structure(model)
```

The existing weight estimate and feasibility calculation continue to use
`parameter_count` (the model's total parameter count). For example, a model with
1 billion total parameters and 100 million active parameters per token, using
FP16, still budgets 2,000,000,000 bytes for weights—not 200,000,000 bytes.

`active_parameter_count` describes parameters participating in a token's
computation; it does not say which expert weights remain loaded in device memory.
KVScope does not convert active parameters into a resident-byte estimate and
does not assume inactive experts are offloaded. Expert placement, CPU/disk
offload, backend-specific loading, and runtime behavior remain out of scope.
When no expert or active-parameter metadata is available, `moe_weight_analysis`
is `null`.
