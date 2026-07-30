"""Feasibility evaluation result domain object."""

from decimal import Decimal
from typing import Annotated

from pydantic import Field, StrictInt, StrictStr

from kvscope.domain.base import DomainModel
from kvscope.domain.enums import (
    Confidence,
    InternalFeasibilityStatus,
    ProductFeasibilityStatus,
)
from kvscope.domain.evidence import Evidence
from kvscope.domain.ranges import ByteRange
from kvscope.domain.signed_ranges import SignedByteRange

NonNegativeInt = Annotated[StrictInt, Field(ge=0)]


class FeasibilityResult(DomainModel):
    """Evaluation result comparing memory requirements against hardware budgets."""

    schema_version: StrictStr = "v0.1"

    internal_status: InternalFeasibilityStatus
    product_status: ProductFeasibilityStatus

    requirement: ByteRange | None = None
    known_subtotal: ByteRange

    physical_total_bytes: NonNegativeInt
    allocatable_before_headroom: ByteRange
    recommended_allocatable: ByteRange

    headroom_vs_physical: SignedByteRange | None = None
    headroom_vs_allocatable: SignedByteRange | None = None
    headroom_vs_recommended: SignedByteRange | None = None

    expected_headroom_ratio: Decimal | None = None

    confidence: Confidence
    is_actionable: bool

    primary_boundary: StrictStr | None = None
    explanation: StrictStr

    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
