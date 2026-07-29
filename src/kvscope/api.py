"""Stable Python API boundary for KVScope's implemented calculation engines."""

from kvscope.calculators.kv_cache import (
    AttentionMode,
    KVCacheEstimate,
    KVCacheFormulaInputs,
    calculate_kv_cache,
    estimate_kv_cache,
)
from kvscope.calculators.weights import (
    WeightEstimationMethod,
    WeightMemoryEstimate,
    estimate_weight_memory,
)
from kvscope.domain.backend import BackendSpec
from kvscope.domain.config import InferenceConfig
from kvscope.domain.estimate import EstimateComponent, MemoryEstimate
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.hardware import HardwareSpec
from kvscope.domain.model import ModelSpec
from kvscope.domain.model_source import ModelSource, ResolvedModel, ResolverAttempt
from kvscope.domain.report import AnalysisReport
from kvscope.domain.weight import WeightArtifactSummary
from kvscope.errors import (
    InvalidModelConfigError,
    KVScopeError,
    ModelConfigConflictError,
    ModelConfigParseError,
    ModelSourceNotFoundError,
    OfflineCacheMissError,
    OptionalDependencyMissingError,
    ProfileValidationError,
    RegistryValidationError,
    UnsupportedArchitectureError,
)
from kvscope.resolvers.chain import resolve_model

__all__ = [
    "AnalysisReport",
    "AttentionMode",
    "BackendSpec",
    "EstimateComponent",
    "FeasibilityResult",
    "HardwareSpec",
    "InferenceConfig",
    "InvalidModelConfigError",
    "KVCacheEstimate",
    "KVCacheFormulaInputs",
    "KVScopeError",
    "MemoryEstimate",
    "ModelSpec",
    "ModelSource",
    "ResolvedModel",
    "ResolverAttempt",
    "ModelConfigConflictError",
    "ModelConfigParseError",
    "ModelSourceNotFoundError",
    "OfflineCacheMissError",
    "OptionalDependencyMissingError",
    "RegistryValidationError",
    "UnsupportedArchitectureError",
    "resolve_model",
    "ProfileValidationError",
    "WeightArtifactSummary",
    "WeightEstimationMethod",
    "WeightMemoryEstimate",
    "calculate_kv_cache",
    "estimate_kv_cache",
    "estimate_weight_memory",
]
