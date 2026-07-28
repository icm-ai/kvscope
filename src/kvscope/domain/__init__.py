"""Stable domain model namespace for KVScope."""

from kvscope.domain.backend import BackendSpec
from kvscope.domain.config import InferenceConfig
from kvscope.domain.constraint import Constraint
from kvscope.domain.dtypes import KVDType, WeightDType
from kvscope.domain.enums import (
    Confidence,
    FeasibilityStatus,
    MemoryTopology,
    RiskLevel,
)
from kvscope.domain.estimate import EstimateComponent, MemoryEstimate
from kvscope.domain.evidence import Evidence
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.hardware import HardwareSpec
from kvscope.domain.model import ModelSpec
from kvscope.domain.recommendation import Recommendation
from kvscope.domain.report import AnalysisReport
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
    "BackendSpec",
    "BYTES_PER_GIB",
    "BYTES_PER_MIB",
    "Confidence",
    "Constraint",
    "EstimateComponent",
    "Evidence",
    "FeasibilityResult",
    "FeasibilityStatus",
    "HardwareSpec",
    "InferenceConfig",
    "KVDType",
    "MemoryEstimate",
    "MemoryTopology",
    "ModelSpec",
    "Recommendation",
    "RiskLevel",
    "WeightDType",
    "WeightArtifactSummary",
    "bytes_to_gib",
    "bytes_to_mib",
    "gib_to_bytes",
    "mib_to_bytes",
]
