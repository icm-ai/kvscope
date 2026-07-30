"""Domain objects for memory constraint analysis."""

from decimal import Decimal
from enum import StrEnum

from pydantic import Field, StrictStr

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import Confidence
from kvscope.domain.ranges import ByteRange
from kvscope.domain.signed_ranges import SignedByteRange


class ConstraintSeverity(StrEnum):
    """Severity levels for identified memory constraints."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class MemoryConstraint(DomainModel):
    """An identified memory limitation or bottleneck."""

    code: StrictStr
    severity: ConstraintSeverity
    category: StrictStr
    component: StrictStr | None = None

    title: StrictStr
    explanation: StrictStr

    observed: ByteRange | SignedByteRange | None = None
    boundary: ByteRange | int | None = None

    contribution_ratio_expected: Decimal | None = None
    contribution_ratio_upper: Decimal | None = None

    evidence_ids: list[StrictStr] = Field(default_factory=list)


class ConstraintPolicy(DomainModel):
    """Configuration thresholds used by the Constraint Analyzer."""

    low_headroom_ratio: Decimal = Decimal("0.10")
    dominant_component_ratio: Decimal = Decimal("0.50")
    low_confidence_is_constraint: bool = True


class ConstraintAnalysis(DomainModel):
    """Result of constraint analysis on a feasibility report."""

    schema_version: StrictStr = "v0.1"

    primary_constraint: MemoryConstraint | None = None
    constraints: list[MemoryConstraint] = Field(default_factory=list)

    dominant_component_expected: StrictStr | None = None
    dominant_component_upper: StrictStr | None = None

    component_shares_expected: dict[str, Decimal | None] = Field(default_factory=dict)
    component_shares_upper: dict[str, Decimal | None] = Field(default_factory=dict)

    confidence: Confidence
    warnings: list[str] = Field(default_factory=list)
