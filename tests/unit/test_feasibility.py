"""Unit tests for Feasibility Engine."""

import pytest

from kvscope.domain.aggregation import (
    MemoryAggregationResult,
    MemoryComponentRequirement,
)
from kvscope.domain.enums import (
    Confidence,
    InternalFeasibilityStatus,
    MemoryTopology,
    ProductFeasibilityStatus,
)
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.ranges import ByteRange
from kvscope.engines.feasibility import evaluate_memory_feasibility
from kvscope.errors import IncompleteRequirementError


def _make_hardware_budget(
    physical_total: int = 16 * 1024 * 1024 * 1024,
    reserve_bytes: int = 2 * 1024 * 1024 * 1024,
    headroom_bytes: int = 2 * 1024 * 1024 * 1024,
    topology: MemoryTopology = MemoryTopology.DISCRETE,
    confidence: Confidence = Confidence.HIGH,
) -> HardwareMemoryBudget:
    allocatable_before = physical_total - reserve_bytes
    recommended = allocatable_before - headroom_bytes

    return HardwareMemoryBudget(
        physical_total_bytes=physical_total,
        os_reserve=ByteRange.exact(reserve_bytes),
        display_reserve=ByteRange.exact(0),
        background_process_reserve=ByteRange.exact(0),
        device_specific_reserve=ByteRange.exact(0),
        user_reserve=ByteRange.exact(0),
        total_non_model_reserve=ByteRange.exact(reserve_bytes),
        allocatable_before_headroom=ByteRange.exact(allocatable_before),
        recommended_headroom=ByteRange.exact(headroom_bytes),
        recommended_allocatable=ByteRange.exact(recommended),
        memory_topology=topology,
        confidence=confidence,
        assumptions=[],
        warnings=[],
    )


def _make_aggregation_result(
    total_range: ByteRange | None,
    is_partial: bool = False,
    confidence: Confidence = Confidence.HIGH,
) -> MemoryAggregationResult:
    subtotal = total_range if total_range is not None else ByteRange.exact(1000)
    req = MemoryComponentRequirement(
        component="dummy",
        memory=subtotal,
        confidence=confidence,
    )
    return MemoryAggregationResult(
        schema_version="v0.1",
        resident_weights=req,
        kv_cache=req,
        runtime_overhead=req,
        known_subtotal=subtotal,
        total_requirement=total_range if not is_partial else None,
        is_partial=is_partial,
        missing_components=["runtime_overhead"] if is_partial else [],
        confidence=confidence if not is_partial else Confidence.UNKNOWN,
    )


def test_feasibility_guaranteed_feasible():
    budget = _make_hardware_budget(
        physical_total=16000, reserve_bytes=2000, headroom_bytes=2000
    )
    # Recommended allocatable = 12000
    # Requirement upper = 10000 <= 12000
    req = _make_aggregation_result(
        ByteRange(lower_bytes=8000, expected_bytes=9000, upper_bytes=10000)
    )

    res = evaluate_memory_feasibility(requirement=req, hardware_budget=budget)

    assert res.internal_status == InternalFeasibilityStatus.GUARANTEED_FEASIBLE
    assert res.product_status == ProductFeasibilityStatus.FEASIBLE
    assert res.is_actionable
    assert res.primary_boundary == "recommended_allocatable"


def test_feasibility_expected_feasible():
    budget = _make_hardware_budget(
        physical_total=16000, reserve_bytes=2000, headroom_bytes=2000
    )
    # Recommended allocatable = 12000
    # Requirement: lower=11000, expected=12000, upper=13000
    # R.upper (13000) > 12000 but R.expected (12000) <= 12000
    req = _make_aggregation_result(
        ByteRange(lower_bytes=11000, expected_bytes=12000, upper_bytes=13000)
    )

    res = evaluate_memory_feasibility(requirement=req, hardware_budget=budget)

    assert res.internal_status == InternalFeasibilityStatus.EXPECTED_FEASIBLE
    assert res.product_status == ProductFeasibilityStatus.TIGHT


def test_feasibility_conditional_feasible():
    budget = _make_hardware_budget(
        physical_total=16000, reserve_bytes=2000, headroom_bytes=2000
    )
    # Recommended allocatable = 12000
    # Requirement: lower=11500, expected=12500, upper=13500
    # R.expected (12500) > 12000 but R.lower (11500) <= 12000
    req = _make_aggregation_result(
        ByteRange(lower_bytes=11500, expected_bytes=12500, upper_bytes=13500)
    )

    res = evaluate_memory_feasibility(requirement=req, hardware_budget=budget)

    assert res.internal_status == InternalFeasibilityStatus.CONDITIONAL_FEASIBLE
    assert res.product_status == ProductFeasibilityStatus.TIGHT


def test_feasibility_headroom_exceeded():
    budget = _make_hardware_budget(
        physical_total=16000, reserve_bytes=2000, headroom_bytes=2000
    )
    # Allocatable before headroom = 14000
    # Recommended allocatable = 12000
    # Requirement: lower=12500, expected=13000, upper=13500
    # R.lower (12500) > 12000 but <= 14000
    req = _make_aggregation_result(
        ByteRange(lower_bytes=12500, expected_bytes=13000, upper_bytes=13500)
    )

    res = evaluate_memory_feasibility(requirement=req, hardware_budget=budget)

    assert res.internal_status == InternalFeasibilityStatus.HEADROOM_EXCEEDED
    assert res.product_status == ProductFeasibilityStatus.TIGHT


def test_feasibility_allocatable_exceeded():
    budget = _make_hardware_budget(
        physical_total=16000, reserve_bytes=2000, headroom_bytes=2000
    )
    # Allocatable before headroom = 14000
    # Requirement: lower=14500, expected=15000, upper=15500
    # R.lower (14500) > 14000
    req = _make_aggregation_result(
        ByteRange(lower_bytes=14500, expected_bytes=15000, upper_bytes=15500)
    )

    res = evaluate_memory_feasibility(requirement=req, hardware_budget=budget)

    assert res.internal_status == InternalFeasibilityStatus.ALLOCATABLE_EXCEEDED
    assert res.product_status == ProductFeasibilityStatus.INFEASIBLE


def test_feasibility_physical_memory_exceeded():
    budget = _make_hardware_budget(
        physical_total=16000, reserve_bytes=2000, headroom_bytes=2000
    )
    # Physical total = 16000
    # Requirement: lower=16500, expected=17000, upper=18000
    req = _make_aggregation_result(
        ByteRange(lower_bytes=16500, expected_bytes=17000, upper_bytes=18000)
    )

    res = evaluate_memory_feasibility(requirement=req, hardware_budget=budget)

    assert res.internal_status == InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED
    assert res.product_status == ProductFeasibilityStatus.INFEASIBLE


def test_feasibility_partial_returns_unknown():
    budget = _make_hardware_budget()
    req = _make_aggregation_result(total_range=None, is_partial=True)

    res = evaluate_memory_feasibility(requirement=req, hardware_budget=budget)

    assert res.internal_status == InternalFeasibilityStatus.UNKNOWN
    assert res.product_status == ProductFeasibilityStatus.UNKNOWN
    assert not res.is_actionable

    with pytest.raises(IncompleteRequirementError):
        evaluate_memory_feasibility(
            requirement=req, hardware_budget=budget, strict=True
        )


def test_feasibility_low_confidence_does_not_force_unknown():
    budget = _make_hardware_budget(confidence=Confidence.LOW)
    req = _make_aggregation_result(ByteRange.exact(10000), confidence=Confidence.LOW)

    res = evaluate_memory_feasibility(requirement=req, hardware_budget=budget)

    assert res.internal_status == InternalFeasibilityStatus.GUARANTEED_FEASIBLE
    assert res.confidence == Confidence.LOW


def test_feasibility_zero_recommended_allocatable_headroom_ratio_none():
    budget = _make_hardware_budget(
        physical_total=2000, reserve_bytes=1000, headroom_bytes=1000
    )
    req = _make_aggregation_result(ByteRange.exact(500))

    res = evaluate_memory_feasibility(requirement=req, hardware_budget=budget)

    assert res.expected_headroom_ratio is None


def test_feasibility_merges_assumptions_and_warnings():
    budget = _make_hardware_budget()
    budget.assumptions.append("budget assumption")
    budget.warnings.append("budget warning")

    req = _make_aggregation_result(ByteRange.exact(500))
    req.assumptions.append("req assumption")
    req.warnings.append("req warning")

    res = evaluate_memory_feasibility(requirement=req, hardware_budget=budget)

    assert "budget assumption" in res.assumptions
    assert "req assumption" in res.assumptions
    assert "budget warning" in res.warnings
    assert "req warning" in res.warnings
