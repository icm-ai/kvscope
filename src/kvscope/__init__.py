"""Public package metadata and core API surface for KVScope."""

__version__ = "0.1.0"

from kvscope.api import (
    estimate_hardware_memory_budget,
    estimate_kv_cache,
    estimate_runtime_overhead,
    estimate_weight_memory,
    resolve_backend_profile,
    resolve_hardware_profile,
    resolve_model,
)
from kvscope.domain import (
    BackendProfile,
    ByteRange,
    HardwareMemoryBudget,
    HardwareProfile,
    ModelSource,
    ModelSpec,
    RatioRange,
    ResolvedModel,
    RuntimeOverheadEstimate,
    RuntimeOverheadOverrides,
)
from kvscope.resolvers import ResolvedBackendProfile, ResolvedHardwareProfile

__all__ = [
    "BackendProfile",
    "ByteRange",
    "HardwareMemoryBudget",
    "HardwareProfile",
    "ModelSource",
    "ModelSpec",
    "RatioRange",
    "ResolvedBackendProfile",
    "ResolvedHardwareProfile",
    "ResolvedModel",
    "RuntimeOverheadEstimate",
    "RuntimeOverheadOverrides",
    "__version__",
    "estimate_hardware_memory_budget",
    "estimate_kv_cache",
    "estimate_runtime_overhead",
    "estimate_weight_memory",
    "resolve_backend_profile",
    "resolve_hardware_profile",
    "resolve_model",
]
