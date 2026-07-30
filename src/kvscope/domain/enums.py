"""Stable enumerations used by the domain schemas."""

from enum import StrEnum


class MemoryTopology(StrEnum):
    """How device memory is exposed to the operating system."""

    DISCRETE = "discrete"
    UNIFIED = "unified"
    SYSTEM = "system"


class Confidence(StrEnum):
    """Confidence levels for estimates and evidence-backed assumptions."""

    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class ProfileStatus(StrEnum):
    """Lifecycle status of a hardware or backend profile."""

    EXPERIMENTAL = "experimental"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    DEPRECATED = "deprecated"


class InternalFeasibilityStatus(StrEnum):
    """Fine-grained internal feasibility evaluation status."""

    GUARANTEED_FEASIBLE = "guaranteed_feasible"
    EXPECTED_FEASIBLE = "expected_feasible"
    CONDITIONAL_FEASIBLE = "conditional_feasible"
    HEADROOM_EXCEEDED = "headroom_exceeded"
    ALLOCATABLE_EXCEEDED = "allocatable_exceeded"
    PHYSICAL_MEMORY_EXCEEDED = "physical_memory_exceeded"
    UNKNOWN = "unknown"


class ProductFeasibilityStatus(StrEnum):
    """User-facing product feasibility status."""

    FEASIBLE = "feasible"
    TIGHT = "tight"
    INFEASIBLE = "infeasible"
    UNKNOWN = "unknown"


class FeasibilityStatus(StrEnum):
    """High-level deployment feasibility status (alias to ProductFeasibilityStatus)."""

    FEASIBLE = "feasible"
    TIGHT = "tight"
    INFEASIBLE = "infeasible"
    UNKNOWN = "unknown"


class RiskLevel(StrEnum):
    """Risk level accompanying a feasibility conclusion."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"
