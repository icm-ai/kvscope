"""Stable Python API boundary for KVScope's implemented calculation engines."""

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
from kvscope.domain.backend import BackendMemoryModel, BackendProfile, BackendSpec
from kvscope.domain.config import InferenceConfig
from kvscope.domain.estimate import EstimateComponent, MemoryEstimate
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.hardware import (
    HardwareProfile,
    HardwareReserveProfile,
    HardwareSpec,
)
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.model import ModelSpec
from kvscope.domain.model_source import ModelSource, ResolvedModel, ResolverAttempt
from kvscope.domain.ranges import ByteRange, RatioRange
from kvscope.domain.report import AnalysisReport
from kvscope.domain.runtime_overhead import (
    RuntimeOverheadEstimate,
    RuntimeOverheadOverrides,
)
from kvscope.domain.weight import WeightArtifactSummary
from kvscope.errors import (
    BackendProfileAmbiguousError,
    BackendProfileError,
    BackendProfileNotFoundError,
    BackendVersionMismatchError,
    HardwareProfileConflictError,
    HardwareProfileError,
    HardwareProfileNotFoundError,
    IncompleteBackendProfileError,
    InvalidModelConfigError,
    KVScopeError,
    ModelConfigConflictError,
    ModelConfigParseError,
    ModelSourceNotFoundError,
    OfflineCacheMissError,
    OptionalDependencyMissingError,
    ProfileValidationError,
    RegistryValidationError,
    RuntimeOverheadInputError,
    UnsupportedArchitectureError,
    UnsupportedMemoryTopologyError,
)
from kvscope.resolvers.backend import ResolvedBackendProfile, resolve_backend_profile
from kvscope.resolvers.chain import resolve_model
from kvscope.resolvers.hardware import (
    ResolvedHardwareProfile,
    resolve_hardware_profile,
)

__all__ = [
    "AnalysisReport",
    "AttentionMode",
    "BackendMemoryModel",
    "BackendProfile",
    "BackendProfileAmbiguousError",
    "BackendProfileError",
    "BackendProfileNotFoundError",
    "BackendSpec",
    "BackendVersionMismatchError",
    "ByteRange",
    "EstimateComponent",
    "FeasibilityResult",
    "HardwareMemoryBudget",
    "HardwareProfile",
    "HardwareProfileConflictError",
    "HardwareProfileError",
    "HardwareProfileNotFoundError",
    "HardwareReserveProfile",
    "HardwareSpec",
    "IncompleteBackendProfileError",
    "InferenceConfig",
    "InvalidModelConfigError",
    "KVCacheEstimate",
    "KVCacheFormulaInputs",
    "KVScopeError",
    "MemoryEstimate",
    "ModelConfigConflictError",
    "ModelConfigParseError",
    "ModelSourceNotFoundError",
    "ModelSpec",
    "ModelSource",
    "OfflineCacheMissError",
    "OptionalDependencyMissingError",
    "ProfileValidationError",
    "RatioRange",
    "RegistryValidationError",
    "ResolvedBackendProfile",
    "ResolvedHardwareProfile",
    "ResolvedModel",
    "ResolverAttempt",
    "RuntimeOverheadEstimate",
    "RuntimeOverheadInputError",
    "RuntimeOverheadOverrides",
    "UnsupportedArchitectureError",
    "UnsupportedMemoryTopologyError",
    "WeightArtifactSummary",
    "WeightEstimationMethod",
    "WeightMemoryEstimate",
    "calculate_kv_cache",
    "estimate_hardware_memory_budget",
    "estimate_kv_cache",
    "estimate_runtime_overhead",
    "estimate_weight_memory",
    "resolve_backend_profile",
    "resolve_hardware_profile",
    "resolve_model",
]
