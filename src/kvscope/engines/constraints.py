"""Constraint Analyzer engine for identifying memory bottlenecks and limitations."""

from decimal import Decimal

from kvscope.domain.aggregation import MemoryAggregationResult
from kvscope.domain.constraints import (
    ConstraintAnalysis,
    ConstraintPolicy,
    ConstraintSeverity,
    MemoryConstraint,
)
from kvscope.domain.enums import (
    Confidence,
    InternalFeasibilityStatus,
    MemoryTopology,
)
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.memory_budget import HardwareMemoryBudget

_SEVERITY_WEIGHT: dict[ConstraintSeverity, int] = {
    ConstraintSeverity.CRITICAL: 0,
    ConstraintSeverity.HIGH: 1,
    ConstraintSeverity.MEDIUM: 2,
    ConstraintSeverity.LOW: 3,
    ConstraintSeverity.INFO: 4,
}


def analyze_memory_constraints(
    *,
    aggregation: MemoryAggregationResult,
    hardware_budget: HardwareMemoryBudget,
    feasibility: FeasibilityResult,
    policy: ConstraintPolicy | None = None,
) -> ConstraintAnalysis:
    """Analyze memory constraints without generating parameter recommendations."""
    pol = policy or ConstraintPolicy()

    component_shares_expected: dict[str, Decimal | None] = {}
    component_shares_upper: dict[str, Decimal | None] = {}

    components = [
        ("resident_weights", aggregation.resident_weights),
        ("kv_cache", aggregation.kv_cache),
        ("runtime_overhead", aggregation.runtime_overhead),
    ]

    total_req = aggregation.total_requirement

    for comp_name, comp_req in components:
        if total_req is not None and total_req.expected_bytes > 0:
            exp_share: Decimal | None = Decimal(
                comp_req.memory.expected_bytes
            ) / Decimal(total_req.expected_bytes)
        else:
            exp_share = None

        if total_req is not None and total_req.upper_bytes > 0:
            upp_share: Decimal | None = Decimal(comp_req.memory.upper_bytes) / Decimal(
                total_req.upper_bytes
            )
        else:
            upp_share = None

        component_shares_expected[comp_name] = exp_share
        component_shares_upper[comp_name] = upp_share

    raw_constraints: list[MemoryConstraint] = []

    # 1. PARTIAL_MEMORY_ESTIMATE
    if aggregation.is_partial:
        raw_constraints.append(
            MemoryConstraint(
                code="PARTIAL_MEMORY_ESTIMATE",
                severity=ConstraintSeverity.CRITICAL,
                category="completeness",
                component=None,
                title="Partial Memory Estimate",
                explanation=(
                    "Memory requirement estimation is incomplete; missing "
                    f"components: {aggregation.missing_components}."
                ),
                observed=aggregation.known_subtotal,
                boundary=None,
                evidence_ids=[],
            )
        )

    # 2. PHYSICAL_MEMORY_EXCEEDED
    if (
        feasibility.internal_status
        == InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED
    ):
        raw_constraints.append(
            MemoryConstraint(
                code="PHYSICAL_MEMORY_EXCEEDED",
                severity=ConstraintSeverity.CRITICAL,
                category="capacity",
                component=None,
                title="Physical Memory Exceeded",
                explanation=(
                    "Optimistic memory requirement exceeds the total physical "
                    "hardware memory."
                ),
                observed=feasibility.requirement,
                boundary=hardware_budget.physical_total_bytes,
                evidence_ids=[],
            )
        )

    # 3. ALLOCATABLE_MEMORY_EXCEEDED
    if feasibility.internal_status == InternalFeasibilityStatus.ALLOCATABLE_EXCEEDED:
        raw_constraints.append(
            MemoryConstraint(
                code="ALLOCATABLE_MEMORY_EXCEEDED",
                severity=ConstraintSeverity.CRITICAL,
                category="capacity",
                component=None,
                title="Allocatable Memory Exceeded",
                explanation=(
                    "Optimistic memory requirement exceeds maximum allocatable "
                    "budget after system reserves."
                ),
                observed=feasibility.requirement,
                boundary=hardware_budget.allocatable_before_headroom,
                evidence_ids=[],
            )
        )

    # 4. RECOMMENDED_BUDGET_EXCEEDED
    if feasibility.internal_status == InternalFeasibilityStatus.HEADROOM_EXCEEDED:
        raw_constraints.append(
            MemoryConstraint(
                code="RECOMMENDED_BUDGET_EXCEEDED",
                severity=ConstraintSeverity.HIGH,
                category="safety",
                component=None,
                title="Recommended Safety Budget Exceeded",
                explanation=(
                    "Memory requirement exceeds recommended safety allocatable budget "
                    "but fits within total allocatable memory."
                ),
                observed=feasibility.requirement,
                boundary=hardware_budget.recommended_allocatable,
                evidence_ids=[],
            )
        )

    # 5. REQUIREMENT_RANGE_CROSSES_BUDGET
    if (
        feasibility.internal_status
        in {
            InternalFeasibilityStatus.EXPECTED_FEASIBLE,
            InternalFeasibilityStatus.CONDITIONAL_FEASIBLE,
        }
        and feasibility.headroom_vs_recommended is not None
        and feasibility.headroom_vs_recommended.lower_bytes
        < 0
        <= feasibility.headroom_vs_recommended.upper_bytes
    ):
        raw_constraints.append(
            MemoryConstraint(
                code="REQUIREMENT_RANGE_CROSSES_BUDGET",
                severity=ConstraintSeverity.MEDIUM,
                category="variance",
                component=None,
                title="Requirement Range Crosses Budget Boundary",
                explanation=(
                    "The memory requirement interval crosses the recommended safety "
                    "budget boundary."
                ),
                observed=feasibility.headroom_vs_recommended,
                boundary=hardware_budget.recommended_allocatable,
                evidence_ids=[],
            )
        )

    # 6. ZERO_RECOMMENDED_HEADROOM
    if (
        feasibility.headroom_vs_recommended is not None
        and feasibility.headroom_vs_recommended.expected_bytes == 0
    ):
        raw_constraints.append(
            MemoryConstraint(
                code="ZERO_RECOMMENDED_HEADROOM",
                severity=ConstraintSeverity.MEDIUM,
                category="headroom",
                component=None,
                title="Zero Recommended Headroom",
                explanation=(
                    "Expected memory requirement equals the recommended allocatable "
                    "budget exactly."
                ),
                observed=feasibility.headroom_vs_recommended,
                boundary=hardware_budget.recommended_allocatable,
                evidence_ids=[],
            )
        )

    # 7. LOW_RECOMMENDED_HEADROOM
    if (
        feasibility.expected_headroom_ratio is not None
        and Decimal(0) < feasibility.expected_headroom_ratio < pol.low_headroom_ratio
    ):
        raw_constraints.append(
            MemoryConstraint(
                code="LOW_RECOMMENDED_HEADROOM",
                severity=ConstraintSeverity.MEDIUM,
                category="headroom",
                component=None,
                title="Low Recommended Headroom",
                explanation=(
                    "Expected headroom ratio "
                    f"({feasibility.expected_headroom_ratio:.2%}) is below the "
                    f"configured policy threshold ({pol.low_headroom_ratio:.2%})."
                ),
                observed=feasibility.headroom_vs_recommended,
                boundary=hardware_budget.recommended_allocatable,
                evidence_ids=[],
            )
        )

    # 8. Dominant Component Constraints
    code_map = {
        "resident_weights": (
            "WEIGHT_MEMORY_DOMINANT",
            "Weight Memory Dominant",
            "Model weights constitute the majority of memory consumption.",
        ),
        "kv_cache": (
            "KV_CACHE_DOMINANT",
            "KV Cache Memory Dominant",
            "KV Cache constitutes the majority of memory consumption.",
        ),
        "runtime_overhead": (
            "RUNTIME_OVERHEAD_DOMINANT",
            "Runtime Overhead Dominant",
            "Runtime overhead constitutes the majority of memory consumption.",
        ),
    }

    for comp_name, (code, title, explanation) in code_map.items():
        exp_share = component_shares_expected.get(comp_name)
        upp_share = component_shares_upper.get(comp_name)

        is_dominant = (
            exp_share is not None and exp_share >= pol.dominant_component_ratio
        ) or (upp_share is not None and upp_share >= pol.dominant_component_ratio)

        if is_dominant:
            comp_req = getattr(aggregation, comp_name)
            raw_constraints.append(
                MemoryConstraint(
                    code=code,
                    severity=ConstraintSeverity.LOW,
                    category="breakdown",
                    component=comp_name,
                    title=title,
                    explanation=explanation,
                    observed=comp_req.memory,
                    boundary=total_req,
                    contribution_ratio_expected=exp_share,
                    contribution_ratio_upper=upp_share,
                    evidence_ids=[],
                )
            )

    # 9. LOW_CONFIDENCE_ESTIMATE
    if (
        pol.low_confidence_is_constraint
        and not aggregation.is_partial
        and feasibility.confidence in {Confidence.LOW, Confidence.UNKNOWN}
    ):
        raw_constraints.append(
            MemoryConstraint(
                code="LOW_CONFIDENCE_ESTIMATE",
                severity=ConstraintSeverity.LOW,
                category="confidence",
                component=None,
                title="Low Confidence Estimate",
                explanation=(
                    "Overall feasibility assessment confidence is "
                    f"{feasibility.confidence.value.upper()}."
                ),
                observed=None,
                boundary=None,
                evidence_ids=[],
            )
        )

    # 10. UNIFIED_MEMORY_VARIABILITY
    if hardware_budget.memory_topology == MemoryTopology.UNIFIED:
        raw_constraints.append(
            MemoryConstraint(
                code="UNIFIED_MEMORY_VARIABILITY",
                severity=ConstraintSeverity.INFO,
                category="topology",
                component=None,
                title="Unified Memory Topology",
                explanation=(
                    "Device uses unified memory architecture; available capacity "
                    "varies dynamically based on system load."
                ),
                observed=None,
                boundary=None,
                evidence_ids=[],
            )
        )

    # Sort constraints deterministically
    def _sort_key(c: MemoryConstraint) -> tuple[int, int, Decimal, str]:
        sev_rank = _SEVERITY_WEIGHT[c.severity]
        # Primary relevance rank: 0 if c.code matches primary error code, else 1
        is_primary_code = c.code in (
            "PARTIAL_MEMORY_ESTIMATE",
            "PHYSICAL_MEMORY_EXCEEDED",
            "ALLOCATABLE_MEMORY_EXCEEDED",
            "RECOMMENDED_BUDGET_EXCEEDED",
        )
        status = feasibility.internal_status
        is_primary_match = (
            (c.code == "PARTIAL_MEMORY_ESTIMATE" and aggregation.is_partial)
            or (
                c.code == "PHYSICAL_MEMORY_EXCEEDED"
                and status == InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED
            )
            or (
                c.code == "ALLOCATABLE_MEMORY_EXCEEDED"
                and status == InternalFeasibilityStatus.ALLOCATABLE_EXCEEDED
            )
            or (
                c.code == "RECOMMENDED_BUDGET_EXCEEDED"
                and status == InternalFeasibilityStatus.HEADROOM_EXCEEDED
            )
        )
        primary_match = 0 if (is_primary_code and is_primary_match) else 1
        exp_share = c.contribution_ratio_expected or Decimal(0)
        return (sev_rank, primary_match, -exp_share, c.code)

    sorted_constraints = sorted(raw_constraints, key=_sort_key)
    primary = sorted_constraints[0] if sorted_constraints else None

    # Merge warnings
    all_warnings: list[str] = list(feasibility.warnings)

    return ConstraintAnalysis(
        schema_version="v0.1",
        primary_constraint=primary,
        constraints=sorted_constraints,
        dominant_component_expected=aggregation.dominant_component_expected,
        dominant_component_upper=aggregation.dominant_component_upper,
        component_shares_expected=component_shares_expected,
        component_shares_upper=component_shares_upper,
        confidence=feasibility.confidence,
        warnings=all_warnings,
    )
