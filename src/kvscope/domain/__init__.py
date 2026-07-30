"""Stable domain model namespace for KVScope."""

from kvscope.domain.aggregation import (
    MemoryAggregationResult,
    MemoryComponentRequirement,
)
from kvscope.domain.backend import BackendMemoryModel, BackendProfile, BackendSpec
from kvscope.domain.config import InferenceConfig
from kvscope.domain.constraint import Constraint
from kvscope.domain.constraints import (
    ConstraintAnalysis,
    ConstraintPolicy,
    ConstraintSeverity,
    MemoryConstraint,
)
from kvscope.domain.dtypes import KVDType, WeightDType
from kvscope.domain.enums import (
    Confidence,
    FeasibilityStatus,
    InternalFeasibilityStatus,
    MemoryTopology,
    ProductFeasibilityStatus,
    ProfileStatus,
    RiskLevel,
)
from kvscope.domain.estimate import EstimateComponent, MemoryEstimate
from kvscope.domain.evidence import Evidence
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.hardware import (
    HardwareProfile,
    HardwareReserveProfile,
    HardwareSpec,
    MemoryQuantityInput,
)
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.model import ModelSpec
from kvscope.domain.model_source import ModelSource, ResolvedModel, ResolverAttempt
from kvscope.domain.ranges import (
    ByteRange,
    RatioRange,
    add_byte_ranges,
    ceil_decimal_multiply,
    ceil_div,
    multiply_bytes_by_ratio_range,
)
from kvscope.domain.recommendation import Recommendation
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
from kvscope.domain.units import (
    BYTES_PER_GIB,
    BYTES_PER_MIB,
    bytes_to_gib,
    bytes_to_mib,
    gib_to_bytes,
    mib_to_bytes,
)
from kvscope.domain.weight import WeightArtifactSummary

__all__ = [
    "AnalysisReport",
    "BackendMemoryModel",
    "BackendProfile",
    "BackendSpec",
    "ByteRange",
    "BYTES_PER_GIB",
    "BYTES_PER_MIB",
    "Confidence",
    "Constraint",
    "ConstraintAnalysis",
    "ConstraintPolicy",
    "ConstraintSeverity",
    "EstimateComponent",
    "Evidence",
    "FeasibilityResult",
    "FeasibilityStatus",
    "HardwareMemoryBudget",
    "HardwareProfile",
    "HardwareReserveProfile",
    "HardwareSpec",
    "InferenceConfig",
    "InternalFeasibilityStatus",
    "KVDType",
    "MemoryAggregationResult",
    "MemoryComponentRequirement",
    "MemoryEstimate",
    "MemoryFeasibilityReport",
    "MemoryConstraint",
    "MemoryQuantityInput",
    "MemoryTopology",
    "ModelSpec",
    "ModelSource",
    "ProductFeasibilityStatus",
    "ProfileStatus",
    "RatioRange",
    "ResolvedModel",
    "ResolverAttempt",
    "Recommendation",
    "RiskLevel",
    "RuntimeOverheadEstimate",
    "RuntimeOverheadOverrides",
    "SignedByteRange",
    "WeightDType",
    "WeightArtifactSummary",
    "add_byte_ranges",
    "bytes_to_gib",
    "bytes_to_mib",
    "ceil_decimal_multiply",
    "ceil_div",
    "gib_to_bytes",
    "mib_to_bytes",
    "multiply_bytes_by_ratio_range",
    "subtract_byte_ranges",
    "subtract_exact_bytes_from_range",
    "subtract_range_from_exact_bytes",
]
