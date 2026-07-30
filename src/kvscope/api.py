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
from kvscope.domain.aggregation import (
    MemoryAggregationResult,
    MemoryComponentRequirement,
)
from kvscope.domain.backend import BackendMemoryModel, BackendProfile, BackendSpec
from kvscope.domain.config import InferenceConfig
from kvscope.domain.constraints import (
    ConstraintAnalysis,
    ConstraintPolicy,
    ConstraintSeverity,
    MemoryConstraint,
)
from kvscope.domain.enums import (
    Confidence,
    FeasibilityStatus,
    InternalFeasibilityStatus,
    MemoryTopology,
    ProductFeasibilityStatus,
)
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
from kvscope.domain.report import AnalysisReport, MemoryFeasibilityReport
from kvscope.domain.runtime_overhead import (
    RuntimeOverheadEstimate,
    RuntimeOverheadOverrides,
)
from kvscope.domain.signed_ranges import (
    SignedByteRange,
    subtract_byte_ranges,
    subtract_exact_bytes_from_range,
    subtract_range_from_exact_bytes,
)
from kvscope.domain.weight import WeightArtifactSummary
from kvscope.engines.aggregation import aggregate_memory_requirements
from kvscope.engines.analysis import assess_memory_feasibility
from kvscope.engines.constraints import analyze_memory_constraints
from kvscope.engines.feasibility import evaluate_memory_feasibility
from kvscope.errors import (
    BackendProfileAmbiguousError,
    BackendProfileError,
    BackendProfileNotFoundError,
    BackendVersionMismatchError,
    ConstraintAnalysisError,
    FeasibilityEvaluationError,
    HardwareProfileConflictError,
    HardwareProfileError,
    HardwareProfileNotFoundError,
    IncompleteBackendProfileError,
    IncompleteRequirementError,
    InvalidMemoryEstimateError,
    InvalidModelConfigError,
    KVScopeError,
    MemoryAggregationError,
    MissingMemoryComponentError,
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
    "Confidence",
    "ConstraintAnalysis",
    "ConstraintAnalysisError",
    "ConstraintPolicy",
    "ConstraintSeverity",
    "EstimateComponent",
    "FeasibilityEvaluationError",
    "FeasibilityResult",
    "FeasibilityStatus",
    "HardwareMemoryBudget",
    "HardwareProfile",
    "HardwareProfileConflictError",
    "HardwareProfileError",
    "HardwareProfileNotFoundError",
    "HardwareReserveProfile",
    "HardwareSpec",
    "IncompleteBackendProfileError",
    "IncompleteRequirementError",
    "InferenceConfig",
    "InternalFeasibilityStatus",
    "InvalidMemoryEstimateError",
    "InvalidModelConfigError",
    "KVCacheEstimate",
    "KVCacheFormulaInputs",
    "KVScopeError",
    "MemoryAggregationError",
    "MemoryAggregationResult",
    "MemoryComponentRequirement",
    "MemoryConstraint",
    "MemoryEstimate",
    "MemoryFeasibilityReport",
    "MemoryTopology",
    "MissingMemoryComponentError",
    "ModelConfigConflictError",
    "ModelConfigParseError",
    "ModelSourceNotFoundError",
    "ModelSpec",
    "ModelSource",
    "OfflineCacheMissError",
    "OptionalDependencyMissingError",
    "ProductFeasibilityStatus",
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
    "SignedByteRange",
    "UnsupportedArchitectureError",
    "UnsupportedMemoryTopologyError",
    "WeightArtifactSummary",
    "WeightEstimationMethod",
    "WeightMemoryEstimate",
    "aggregate_memory_requirements",
    "analyze_memory_constraints",
    "assess_memory_feasibility",
    "calculate_kv_cache",
    "evaluate_memory_feasibility",
    "estimate_hardware_memory_budget",
    "estimate_kv_cache",
    "estimate_runtime_overhead",
    "estimate_weight_memory",
    "resolve_backend_profile",
    "resolve_hardware_profile",
    "resolve_model",
    "subtract_byte_ranges",
    "subtract_exact_bytes_from_range",
    "subtract_range_from_exact_bytes",
]
