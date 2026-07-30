"""Feasibility Engine for comparing memory requirements against hardware budgets."""

from decimal import Decimal

from kvscope.domain.aggregation import MemoryAggregationResult
from kvscope.domain.enums import (
    Confidence,
    InternalFeasibilityStatus,
    ProductFeasibilityStatus,
)
from kvscope.domain.evidence import Evidence
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.signed_ranges import (
    subtract_byte_ranges,
    subtract_exact_bytes_from_range,
)
from kvscope.errors import IncompleteRequirementError

_CONFIDENCE_ORDER: dict[Confidence, int] = {
    Confidence.EXACT: 4,
    Confidence.HIGH: 3,
    Confidence.MEDIUM: 2,
    Confidence.LOW: 1,
    Confidence.UNKNOWN: 0,
}


def _min_confidence(*confidences: Confidence) -> Confidence:
    """Return the lowest confidence level from the given arguments."""
    if not confidences:
        return Confidence.UNKNOWN
    return min(confidences, key=lambda c: _CONFIDENCE_ORDER[c])


def evaluate_memory_feasibility(
    *,
    requirement: MemoryAggregationResult,
    hardware_budget: HardwareMemoryBudget,
    strict: bool = False,
) -> FeasibilityResult:
    """Evaluate feasibility by comparing requirements against hardware budgets."""
    if strict and requirement.is_partial:
        raise IncompleteRequirementError(
            "Cannot evaluate feasibility on a partial requirement in strict mode."
        )

    # Merge assumptions and warnings
    all_assumptions: list[str] = []
    for item in requirement.assumptions + hardware_budget.assumptions:
        if item not in all_assumptions:
            all_assumptions.append(item)

    all_warnings: list[str] = []
    for item in requirement.warnings + hardware_budget.warnings:
        if item not in all_warnings:
            all_warnings.append(item)

    all_evidence: list[Evidence] = list(requirement.evidence)

    P = hardware_budget.physical_total_bytes
    A = hardware_budget.allocatable_before_headroom
    B = hardware_budget.recommended_allocatable

    if requirement.is_partial or requirement.total_requirement is None:
        return FeasibilityResult(
            schema_version="v0.1",
            internal_status=InternalFeasibilityStatus.UNKNOWN,
            product_status=ProductFeasibilityStatus.UNKNOWN,
            requirement=None,
            known_subtotal=requirement.known_subtotal,
            physical_total_bytes=P,
            allocatable_before_headroom=A,
            recommended_allocatable=B,
            headroom_vs_physical=None,
            headroom_vs_allocatable=None,
            headroom_vs_recommended=None,
            expected_headroom_ratio=None,
            confidence=Confidence.UNKNOWN,
            is_actionable=False,
            primary_boundary=None,
            explanation=(
                "Memory requirement is partial; "
                "formal feasibility evaluation is UNKNOWN."
            ),
            assumptions=all_assumptions,
            warnings=all_warnings,
            evidence=all_evidence,
        )

    R = requirement.total_requirement

    # Compute signed headroom ranges
    headroom_physical = subtract_exact_bytes_from_range(P, R)
    headroom_allocatable = subtract_byte_ranges(A, R)
    headroom_recommended = subtract_byte_ranges(B, R)

    if B.expected_bytes > 0:
        headroom_ratio: Decimal | None = Decimal(
            headroom_recommended.expected_bytes
        ) / Decimal(B.expected_bytes)
    else:
        headroom_ratio = None

    # Step-by-step deterministic decision tree
    if R.lower_bytes > P:
        internal_status = InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED
        product_status = ProductFeasibilityStatus.INFEASIBLE
        primary_boundary = "physical_total"
        explanation = (
            "Optimistic memory requirement exceeds total physical hardware memory."
        )
    elif R.lower_bytes > A.upper_bytes:
        internal_status = InternalFeasibilityStatus.ALLOCATABLE_EXCEEDED
        product_status = ProductFeasibilityStatus.INFEASIBLE
        primary_boundary = "allocatable_before_headroom"
        explanation = (
            "Optimistic memory requirement exceeds maximum allocatable memory budget."
        )
    elif R.upper_bytes <= B.lower_bytes:
        internal_status = InternalFeasibilityStatus.GUARANTEED_FEASIBLE
        product_status = ProductFeasibilityStatus.FEASIBLE
        primary_boundary = "recommended_allocatable"
        explanation = (
            "Worst-case memory requirement fits comfortably within conservative "
            "recommended allocatable budget."
        )
    elif R.expected_bytes <= B.expected_bytes:
        internal_status = InternalFeasibilityStatus.EXPECTED_FEASIBLE
        product_status = ProductFeasibilityStatus.TIGHT
        primary_boundary = "recommended_allocatable"
        explanation = (
            "Expected memory requirement fits within expected recommended budget, "
            "but worst-case upper bound is tight."
        )
    elif R.lower_bytes <= B.upper_bytes:
        internal_status = InternalFeasibilityStatus.CONDITIONAL_FEASIBLE
        product_status = ProductFeasibilityStatus.TIGHT
        primary_boundary = "recommended_allocatable"
        explanation = (
            "Optimistic memory requirement fits within upper recommended budget, "
            "subject to favorable runtime conditions."
        )
    else:
        internal_status = InternalFeasibilityStatus.HEADROOM_EXCEEDED
        product_status = ProductFeasibilityStatus.TIGHT
        primary_boundary = "allocatable_before_headroom"
        explanation = (
            "Optimistic memory requirement exceeds recommended safety headroom "
            "but stays within absolute allocatable budget."
        )

    final_confidence = _min_confidence(
        requirement.confidence, hardware_budget.confidence
    )

    return FeasibilityResult(
        schema_version="v0.1",
        internal_status=internal_status,
        product_status=product_status,
        requirement=R,
        known_subtotal=requirement.known_subtotal,
        physical_total_bytes=P,
        allocatable_before_headroom=A,
        recommended_allocatable=B,
        headroom_vs_physical=headroom_physical,
        headroom_vs_allocatable=headroom_allocatable,
        headroom_vs_recommended=headroom_recommended,
        expected_headroom_ratio=headroom_ratio,
        confidence=final_confidence,
        is_actionable=True,
        primary_boundary=primary_boundary,
        explanation=explanation,
        assumptions=all_assumptions,
        warnings=all_warnings,
        evidence=all_evidence,
    )
