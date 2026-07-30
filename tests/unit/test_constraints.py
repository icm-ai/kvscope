"""Unit tests for Constraint Analyzer engine."""

from decimal import Decimal

from kvscope.domain.aggregation import (
    MemoryAggregationResult,
    MemoryComponentRequirement,
)
from kvscope.domain.constraints import ConstraintSeverity
from kvscope.domain.enums import (
    Confidence,
    InternalFeasibilityStatus,
    MemoryTopology,
    ProductFeasibilityStatus,
)
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.ranges import ByteRange
from kvscope.domain.signed_ranges import SignedByteRange
from kvscope.engines.constraints import analyze_memory_constraints


def _make_dummy_budget(
    topology: MemoryTopology = MemoryTopology.DISCRETE,
) -> HardwareMemoryBudget:
    return HardwareMemoryBudget(
        physical_total_bytes=16000,
        os_reserve=ByteRange.exact(2000),
        display_reserve=ByteRange.exact(0),
        background_process_reserve=ByteRange.exact(0),
        device_specific_reserve=ByteRange.exact(0),
        user_reserve=ByteRange.exact(0),
        total_non_model_reserve=ByteRange.exact(2000),
        allocatable_before_headroom=ByteRange.exact(14000),
        recommended_headroom=ByteRange.exact(2000),
        recommended_allocatable=ByteRange.exact(12000),
        memory_topology=topology,
        confidence=Confidence.HIGH,
        assumptions=[],
        warnings=[],
    )


def _make_dummy_aggregation(
    weights_b: int = 6000,
    kv_b: int = 2000,
    overhead_b: int = 2000,
    is_partial: bool = False,
) -> MemoryAggregationResult:
    w_req = MemoryComponentRequirement(
        component="resident_weights",
        memory=ByteRange.exact(weights_b),
        confidence=Confidence.HIGH,
    )
    kv_req = MemoryComponentRequirement(
        component="kv_cache",
        memory=ByteRange.exact(kv_b),
        confidence=Confidence.EXACT,
    )
    ov_req = MemoryComponentRequirement(
        component="runtime_overhead",
        memory=ByteRange.exact(overhead_b),
        confidence=Confidence.HIGH,
    )
    total_b = weights_b + kv_b + overhead_b
    subtotal = ByteRange.exact(total_b)
    return MemoryAggregationResult(
        schema_version="v0.1",
        resident_weights=w_req,
        kv_cache=kv_req,
        runtime_overhead=ov_req,
        known_subtotal=subtotal,
        total_requirement=subtotal if not is_partial else None,
        is_partial=is_partial,
        missing_components=["runtime_overhead"] if is_partial else [],
        dominant_component_expected="resident_weights",
        dominant_component_upper="resident_weights",
        confidence=Confidence.HIGH if not is_partial else Confidence.UNKNOWN,
    )


def test_partial_memory_estimate_constraint():
    agg = _make_dummy_aggregation(is_partial=True)
    budget = _make_dummy_budget()
    feas = FeasibilityResult(
        schema_version="v0.1",
        internal_status=InternalFeasibilityStatus.UNKNOWN,
        product_status=ProductFeasibilityStatus.UNKNOWN,
        requirement=None,
        known_subtotal=agg.known_subtotal,
        physical_total_bytes=16000,
        allocatable_before_headroom=ByteRange.exact(14000),
        recommended_allocatable=ByteRange.exact(12000),
        confidence=Confidence.UNKNOWN,
        is_actionable=False,
        explanation="Partial estimate",
    )

    analysis = analyze_memory_constraints(
        aggregation=agg, hardware_budget=budget, feasibility=feas
    )

    assert len(analysis.constraints) >= 1
    assert analysis.primary_constraint is not None
    assert analysis.primary_constraint.code == "PARTIAL_MEMORY_ESTIMATE"
    assert analysis.primary_constraint.severity == ConstraintSeverity.CRITICAL

    codes = [c.code for c in analysis.constraints]
    assert "PARTIAL_MEMORY_ESTIMATE" in codes
    assert "LOW_CONFIDENCE_ESTIMATE" not in codes


def test_complete_low_confidence_emits_low_confidence_constraint():
    agg = _make_dummy_aggregation(weights_b=3000, kv_b=1000, overhead_b=1000)
    budget = _make_dummy_budget()
    feas = FeasibilityResult(
        schema_version="v0.1",
        internal_status=InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        product_status=ProductFeasibilityStatus.FEASIBLE,
        requirement=agg.total_requirement,
        known_subtotal=agg.known_subtotal,
        physical_total_bytes=16000,
        allocatable_before_headroom=ByteRange.exact(14000),
        recommended_allocatable=ByteRange.exact(12000),
        confidence=Confidence.LOW,
        is_actionable=True,
        explanation="Feasible",
    )

    analysis = analyze_memory_constraints(
        aggregation=agg, hardware_budget=budget, feasibility=feas
    )

    codes = [c.code for c in analysis.constraints]
    assert "LOW_CONFIDENCE_ESTIMATE" in codes


def test_physical_memory_exceeded_constraint():
    agg = _make_dummy_aggregation(weights_b=10000, kv_b=5000, overhead_b=3000)
    budget = _make_dummy_budget()
    feas = FeasibilityResult(
        schema_version="v0.1",
        internal_status=InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED,
        product_status=ProductFeasibilityStatus.INFEASIBLE,
        requirement=agg.total_requirement,
        known_subtotal=agg.known_subtotal,
        physical_total_bytes=16000,
        allocatable_before_headroom=ByteRange.exact(14000),
        recommended_allocatable=ByteRange.exact(12000),
        confidence=Confidence.HIGH,
        is_actionable=True,
        explanation="Exceeded physical memory",
    )

    analysis = analyze_memory_constraints(
        aggregation=agg, hardware_budget=budget, feasibility=feas
    )

    assert analysis.primary_constraint is not None
    assert analysis.primary_constraint.code == "PHYSICAL_MEMORY_EXCEEDED"
    assert analysis.primary_constraint.severity == ConstraintSeverity.CRITICAL


def test_dominant_component_and_unified_memory_constraints():
    agg = _make_dummy_aggregation(weights_b=7000, kv_b=1000, overhead_b=1000)
    # Total = 9000, Weights share = 7000 / 9000 = 77.7% >= 50%
    budget = _make_dummy_budget(topology=MemoryTopology.UNIFIED)
    feas = FeasibilityResult(
        schema_version="v0.1",
        internal_status=InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        product_status=ProductFeasibilityStatus.FEASIBLE,
        requirement=agg.total_requirement,
        known_subtotal=agg.known_subtotal,
        physical_total_bytes=16000,
        allocatable_before_headroom=ByteRange.exact(14000),
        recommended_allocatable=ByteRange.exact(12000),
        headroom_vs_recommended=SignedByteRange.exact(3000),
        expected_headroom_ratio=Decimal("0.25"),
        confidence=Confidence.HIGH,
        is_actionable=True,
        explanation="Feasible",
    )

    analysis = analyze_memory_constraints(
        aggregation=agg, hardware_budget=budget, feasibility=feas
    )

    codes = [c.code for c in analysis.constraints]
    assert "WEIGHT_MEMORY_DOMINANT" in codes
    assert "UNIFIED_MEMORY_VARIABILITY" in codes

    # No recommendation field in constraint models
    for c in analysis.constraints:
        assert not hasattr(c, "recommendation")
        assert not hasattr(c, "action")
