"""Calculation engine namespace for KVScope."""

from kvscope.calculators.hardware_budget import estimate_hardware_memory_budget
from kvscope.calculators.kv_cache import (
    AttentionMode,
    KVCacheEstimate,
    KVCacheFormulaInputs,
    calculate_kv_cache,
    estimate_kv_cache,
)
from kvscope.calculators.overhead import estimate_runtime_overhead
from kvscope.calculators.weights import (
    WeightEstimationMethod,
    WeightMemoryEstimate,
    estimate_weight_memory,
)

__all__ = [
    "AttentionMode",
    "KVCacheEstimate",
    "KVCacheFormulaInputs",
    "WeightEstimationMethod",
    "WeightMemoryEstimate",
    "calculate_kv_cache",
    "estimate_hardware_memory_budget",
    "estimate_kv_cache",
    "estimate_runtime_overhead",
    "estimate_weight_memory",
]
