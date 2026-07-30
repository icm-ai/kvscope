"""Golden integration tests for Phase 7 Feasibility & Constraint Engine."""

from fractions import Fraction

from kvscope import assess_memory_feasibility
from kvscope.calculators.kv_cache import KVCacheEstimate, KVCacheFormulaInputs
from kvscope.calculators.weights import WeightEstimationMethod, WeightMemoryEstimate
from kvscope.domain.dtypes import KVDType
from kvscope.domain.enums import (
    Confidence,
    InternalFeasibilityStatus,
    MemoryTopology,
    ProductFeasibilityStatus,
)
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.ranges import ByteRange
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate

GIB = 1024 * 1024 * 1024


def _weights(bytes_val: int) -> WeightMemoryEstimate:
    return WeightMemoryEstimate(
        quantized_payload_bytes=bytes_val,
        unquantized_payload_bytes=0,
        scale_overhead_bytes=0,
        zero_point_overhead_bytes=0,
        metadata_bytes=0,
        alignment_overhead_bytes=0,
        total_bytes=bytes_val,
        effective_bits_per_weight=Fraction(16, 1),
        estimation_method=WeightEstimationMethod.PARAMETER_COUNT,
        confidence=Confidence.EXACT,
        assumptions=(),
        warnings=(),
        estimated_resident_weight_bytes=bytes_val,
    )


def _kv(allocated_bytes: int) -> KVCacheEstimate:
    inputs = KVCacheFormulaInputs(
        num_hidden_layers=32,
        num_attention_heads=32,
        num_key_value_heads=8,
        head_dim=128,
        context_tokens=4096,
        prefix_tokens=0,
        multimodal_tokens=0,
        active_sequences=1,
        kv_dtype=KVDType.FP16,
        bytes_per_element=2,
        block_size=16,
    )
    return KVCacheEstimate(
        formula_inputs=inputs,
        raw_bytes=allocated_bytes,
        allocated_bytes=allocated_bytes,
        alignment_waste_bytes=0,
        bytes_per_token=256,
        bytes_per_sequence=1048576,
    )


def _overhead(
    lower_gib: float, expected_gib: float, upper_gib: float, is_partial: bool = False
) -> RuntimeOverheadEstimate:
    l_b = int(lower_gib * GIB)
    e_b = int(expected_gib * GIB)
    u_b = int(upper_gib * GIB)
    r = ByteRange(lower_bytes=l_b, expected_bytes=e_b, upper_bytes=u_b)
    return RuntimeOverheadEstimate(
        base_runtime=ByteRange.exact(0),
        parameter_scaled_overhead=ByteRange.exact(0),
        workspace=ByteRange.exact(0),
        graph_capture=ByteRange.exact(0),
        backend_buffers=ByteRange.exact(0),
        allocator_margin=ByteRange.exact(0),
        subtotal_before_allocator_margin=r,
        total_runtime_overhead=r,
        backend_profile_id="p1",
        backend_version_specifier=None,
        hardware_profile_id="h1",
        confidence=Confidence.HIGH,
        is_partial=is_partial,
        missing_components=["workspace"] if is_partial else [],
        assumptions=[],
        warnings=[],
        evidence=[],
    )


def _budget(phys_gib: float, alloc_gib: float, rec_gib: float) -> HardwareMemoryBudget:
    p_b = int(phys_gib * GIB)
    a_b = int(alloc_gib * GIB)
    r_b = int(rec_gib * GIB)
    res_b = p_b - a_b
    head_b = a_b - r_b

    return HardwareMemoryBudget(
        physical_total_bytes=p_b,
        os_reserve=ByteRange.exact(res_b),
        display_reserve=ByteRange.exact(0),
        background_process_reserve=ByteRange.exact(0),
        device_specific_reserve=ByteRange.exact(0),
        user_reserve=ByteRange.exact(0),
        total_non_model_reserve=ByteRange.exact(res_b),
        allocatable_before_headroom=ByteRange.exact(a_b),
        recommended_headroom=ByteRange.exact(head_b),
        recommended_allocatable=ByteRange.exact(r_b),
        memory_topology=MemoryTopology.DISCRETE,
        confidence=Confidence.HIGH,
        assumptions=[],
        warnings=[],
    )


def test_golden_case_a_guaranteed_feasible():
    # Weight: 4 GiB exact, KV: 2 GiB exact, Overhead: 1/1.5/2 GiB
    # Requirement: 7 / 7.5 / 8 GiB
    # Recommended Budget: 10 / 11 / 12 GiB (using exact 10 GiB lower)
    report = assess_memory_feasibility(
        weights=_weights(4 * GIB),
        kv_cache=_kv(2 * GIB),
        runtime_overhead=_overhead(1.0, 1.5, 2.0),
        hardware_budget=_budget(phys_gib=16.0, alloc_gib=14.0, rec_gib=10.0),
    )

    assert (
        report.feasibility.internal_status
        == InternalFeasibilityStatus.GUARANTEED_FEASIBLE
    )
    assert report.feasibility.product_status == ProductFeasibilityStatus.FEASIBLE
    assert report.aggregation.total_requirement is not None
    assert report.aggregation.total_requirement.lower_bytes == int(7.0 * GIB)
    assert report.aggregation.total_requirement.expected_bytes == int(7.5 * GIB)
    assert report.aggregation.total_requirement.upper_bytes == int(8.0 * GIB)


def test_golden_case_b_expected_feasible():
    # Requirement: 9 / 10 / 11 GiB
    # Recommended Budget: 10 GiB
    # R.upper (11) > B.lower (10), but R.expected (10) <= B.expected (10)
    report = assess_memory_feasibility(
        weights=_weights(4 * GIB),
        kv_cache=_kv(4 * GIB),
        runtime_overhead=_overhead(1.0, 2.0, 3.0),
        hardware_budget=_budget(phys_gib=16.0, alloc_gib=14.0, rec_gib=10.0),
    )

    assert (
        report.feasibility.internal_status
        == InternalFeasibilityStatus.EXPECTED_FEASIBLE
    )
    assert report.feasibility.product_status == ProductFeasibilityStatus.TIGHT


def test_golden_case_c_conditional_feasible():
    # Requirement: 10.5 / 11.5 / 12.5 GiB
    # Recommended Budget: 10 GiB (let's say 10 / 10 / 12 GiB range for B)
    # R.expected (11.5) > B.expected (10), but R.lower (10.5) <= B.upper (12)
    budget = HardwareMemoryBudget(
        physical_total_bytes=16 * GIB,
        os_reserve=ByteRange.exact(2 * GIB),
        display_reserve=ByteRange.exact(0),
        background_process_reserve=ByteRange.exact(0),
        device_specific_reserve=ByteRange.exact(0),
        user_reserve=ByteRange.exact(0),
        total_non_model_reserve=ByteRange.exact(2 * GIB),
        allocatable_before_headroom=ByteRange.exact(14 * GIB),
        recommended_headroom=ByteRange.exact(2 * GIB),
        recommended_allocatable=ByteRange(
            lower_bytes=8 * GIB, expected_bytes=10 * GIB, upper_bytes=12 * GIB
        ),
        memory_topology=MemoryTopology.DISCRETE,
        confidence=Confidence.HIGH,
        assumptions=[],
        warnings=[],
    )

    report = assess_memory_feasibility(
        weights=_weights(5 * GIB),
        kv_cache=_kv(4 * GIB),
        runtime_overhead=_overhead(1.5, 2.5, 3.5),
        hardware_budget=budget,
    )

    assert (
        report.feasibility.internal_status
        == InternalFeasibilityStatus.CONDITIONAL_FEASIBLE
    )
    assert report.feasibility.product_status == ProductFeasibilityStatus.TIGHT


def test_golden_case_d_headroom_exceeded():
    # Requirement: 13 / 13.5 / 14 GiB
    # Recommended Budget: 10 GiB
    # Allocatable Budget: 15 GiB
    # R.lower (13) > Recommended.upper (10), but R.lower (13) <= Allocatable.upper (15)
    report = assess_memory_feasibility(
        weights=_weights(8 * GIB),
        kv_cache=_kv(4 * GIB),
        runtime_overhead=_overhead(1.0, 1.5, 2.0),
        hardware_budget=_budget(phys_gib=18.0, alloc_gib=15.0, rec_gib=10.0),
    )

    assert (
        report.feasibility.internal_status
        == InternalFeasibilityStatus.HEADROOM_EXCEEDED
    )
    assert report.feasibility.product_status == ProductFeasibilityStatus.TIGHT


def test_golden_case_e_allocatable_exceeded():
    # Requirement: 17 / 17.5 / 18 GiB
    # Allocatable Budget: 15 GiB
    # Physical Total: 24 GiB
    # R.lower (17) > Allocatable (15), but <= Physical (24)
    report = assess_memory_feasibility(
        weights=_weights(12 * GIB),
        kv_cache=_kv(4 * GIB),
        runtime_overhead=_overhead(1.0, 1.5, 2.0),
        hardware_budget=_budget(phys_gib=24.0, alloc_gib=15.0, rec_gib=10.0),
    )

    assert (
        report.feasibility.internal_status
        == InternalFeasibilityStatus.ALLOCATABLE_EXCEEDED
    )
    assert report.feasibility.product_status == ProductFeasibilityStatus.INFEASIBLE


def test_golden_case_f_physical_memory_exceeded():
    # Requirement: 29 / 29.5 / 30 GiB
    # Physical Total: 24 GiB
    # R.lower (29) > Physical (24)
    report = assess_memory_feasibility(
        weights=_weights(20 * GIB),
        kv_cache=_kv(8 * GIB),
        runtime_overhead=_overhead(1.0, 1.5, 2.0),
        hardware_budget=_budget(phys_gib=24.0, alloc_gib=20.0, rec_gib=16.0),
    )

    assert (
        report.feasibility.internal_status
        == InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED
    )
    assert report.feasibility.product_status == ProductFeasibilityStatus.INFEASIBLE


def test_golden_case_g_partial_unknown():
    report = assess_memory_feasibility(
        weights=_weights(4 * GIB),
        kv_cache=_kv(2 * GIB),
        runtime_overhead=_overhead(1.0, 1.5, 2.0, is_partial=True),
        hardware_budget=_budget(phys_gib=16.0, alloc_gib=14.0, rec_gib=10.0),
    )

    assert report.aggregation.is_partial
    assert report.aggregation.total_requirement is None
    assert report.feasibility.internal_status == InternalFeasibilityStatus.UNKNOWN
    assert report.feasibility.product_status == ProductFeasibilityStatus.UNKNOWN
