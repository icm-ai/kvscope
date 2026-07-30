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


class FeasibilityStatus(StrEnum):
    """High-level deployment feasibility status."""

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
