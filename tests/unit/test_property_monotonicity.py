"""Property-based tests using Hypothesis for Phase 7 invariants."""

from fractions import Fraction

from hypothesis import given
from hypothesis import strategies as st

from kvscope.calculators.kv_cache import KVCacheEstimate, KVCacheFormulaInputs
from kvscope.calculators.weights import WeightEstimationMethod, WeightMemoryEstimate
from kvscope.domain.dtypes import KVDType
from kvscope.domain.enums import Confidence, InternalFeasibilityStatus, MemoryTopology
from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.ranges import ByteRange
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate
from kvscope.engines.aggregation import aggregate_memory_requirements
from kvscope.engines.feasibility import evaluate_memory_feasibility

_STATUS_RANK = {
    InternalFeasibilityStatus.GUARANTEED_FEASIBLE: 0,
    InternalFeasibilityStatus.EXPECTED_FEASIBLE: 1,
    InternalFeasibilityStatus.CONDITIONAL_FEASIBLE: 2,
    InternalFeasibilityStatus.HEADROOM_EXCEEDED: 3,
    InternalFeasibilityStatus.ALLOCATABLE_EXCEEDED: 4,
    InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED: 5,
}


def _make_budget(phys: int, res: int, head: int) -> HardwareMemoryBudget:
    alloc = phys - res
    rec = alloc - head
    return HardwareMemoryBudget(
        physical_total_bytes=phys,
        os_reserve=ByteRange.exact(res),
        display_reserve=ByteRange.exact(0),
        background_process_reserve=ByteRange.exact(0),
        device_specific_reserve=ByteRange.exact(0),
        user_reserve=ByteRange.exact(0),
        total_non_model_reserve=ByteRange.exact(res),
        allocatable_before_headroom=ByteRange.exact(alloc),
        recommended_headroom=ByteRange.exact(head),
        recommended_allocatable=ByteRange.exact(rec),
        memory_topology=MemoryTopology.DISCRETE,
        confidence=Confidence.HIGH,
        assumptions=[],
        warnings=[],
    )


def _make_weights(b: int) -> WeightMemoryEstimate:
    return WeightMemoryEstimate(
        quantized_payload_bytes=b,
        unquantized_payload_bytes=0,
        scale_overhead_bytes=0,
        zero_point_overhead_bytes=0,
        metadata_bytes=0,
        alignment_overhead_bytes=0,
        total_bytes=b,
        effective_bits_per_weight=Fraction(16, 1),
        estimation_method=WeightEstimationMethod.PARAMETER_COUNT,
        confidence=Confidence.EXACT,
        assumptions=(),
        warnings=(),
        estimated_resident_weight_bytes=b,
    )


def _make_kv(b: int) -> KVCacheEstimate:
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
        raw_bytes=b,
        allocated_bytes=b,
        alignment_waste_bytes=0,
        bytes_per_token=256,
        bytes_per_sequence=1048576,
    )


def _make_overhead(b_lower: int, b_exp: int, b_upper: int) -> RuntimeOverheadEstimate:
    r = ByteRange(lower_bytes=b_lower, expected_bytes=b_exp, upper_bytes=b_upper)
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
        is_partial=False,
        missing_components=[],
        assumptions=[],
        warnings=[],
        evidence=[],
    )


@given(
    b1=st.integers(min_value=100, max_value=10000),
    b2=st.integers(min_value=100, max_value=10000),
)
def test_property_component_addition_nondecreasing(b1: int, b2: int):
    w = _make_weights(b1)
    kv = _make_kv(b1)
    ov = _make_overhead(b1, b1, b1)

    r1 = aggregate_memory_requirements(weights=w, kv_cache=kv, runtime_overhead=ov)

    w_larger = _make_weights(b1 + b2)
    r2 = aggregate_memory_requirements(
        weights=w_larger, kv_cache=kv, runtime_overhead=ov
    )

    assert r2.total_requirement is not None and r1.total_requirement is not None
    assert r2.total_requirement.expected_bytes >= r1.total_requirement.expected_bytes


@given(
    req_b1=st.integers(min_value=1000, max_value=10000),
    req_b2=st.integers(min_value=0, max_value=5000),
)
def test_property_increasing_requirement_never_improves_status(
    req_b1: int, req_b2: int
):
    budget = _make_budget(phys=20000, res=2000, head=2000)

    w1 = _make_weights(req_b1)
    kv = _make_kv(1000)
    ov = _make_overhead(1000, 1000, 1000)

    agg1 = aggregate_memory_requirements(weights=w1, kv_cache=kv, runtime_overhead=ov)
    feas1 = evaluate_memory_feasibility(requirement=agg1, hardware_budget=budget)

    w2 = _make_weights(req_b1 + req_b2)
    agg2 = aggregate_memory_requirements(weights=w2, kv_cache=kv, runtime_overhead=ov)
    feas2 = evaluate_memory_feasibility(requirement=agg2, hardware_budget=budget)

    rank1 = _STATUS_RANK[feas1.internal_status]
    rank2 = _STATUS_RANK[feas2.internal_status]

    assert rank2 >= rank1


@given(
    phys=st.integers(min_value=10000, max_value=30000),
    req_upper=st.integers(min_value=1000, max_value=8000),
)
def test_property_guaranteed_feasible_invariant(phys: int, req_upper: int):
    # Recommended allocatable = phys - 2000 - 2000 = phys - 4000
    # If req_upper <= recommended allocatable lower bound, must be GUARANTEED_FEASIBLE
    res = 2000
    head = 2000
    rec_alloc = phys - res - head

    if req_upper <= rec_alloc:
        budget = _make_budget(phys=phys, res=res, head=head)
        w = _make_weights(req_upper // 2)
        kv = _make_kv(req_upper // 4)
        ov = _make_overhead(
            req_upper // 4,
            req_upper // 4,
            req_upper - (req_upper // 2 + req_upper // 4),
        )

        agg = aggregate_memory_requirements(weights=w, kv_cache=kv, runtime_overhead=ov)
        feas = evaluate_memory_feasibility(requirement=agg, hardware_budget=budget)

        assert feas.internal_status == InternalFeasibilityStatus.GUARANTEED_FEASIBLE


@given(phys=st.integers(min_value=10000, max_value=30000))
def test_property_physical_exceeded_invariant(phys: int):
    budget = _make_budget(phys=phys, res=2000, head=2000)
    w = _make_weights(phys + 1)
    kv = _make_kv(0)
    ov = _make_overhead(0, 0, 0)

    agg = aggregate_memory_requirements(weights=w, kv_cache=kv, runtime_overhead=ov)
    feas = evaluate_memory_feasibility(requirement=agg, hardware_budget=budget)

    assert feas.internal_status == InternalFeasibilityStatus.PHYSICAL_MEMORY_EXCEEDED


@given(b=st.integers(min_value=1000, max_value=10000))
def test_property_partial_always_unknown(b: int):
    budget = _make_budget(phys=20000, res=2000, head=2000)
    w = _make_weights(b)
    kv = _make_kv(b)
    ov = RuntimeOverheadEstimate(
        base_runtime=ByteRange.exact(0),
        parameter_scaled_overhead=ByteRange.exact(0),
        workspace=ByteRange.exact(0),
        graph_capture=ByteRange.exact(0),
        backend_buffers=ByteRange.exact(0),
        allocator_margin=ByteRange.exact(0),
        subtotal_before_allocator_margin=ByteRange.exact(0),
        total_runtime_overhead=ByteRange.exact(0),
        backend_profile_id="p1",
        backend_version_specifier=None,
        hardware_profile_id="h1",
        confidence=Confidence.UNKNOWN,
        is_partial=True,
        missing_components=["workspace"],
        assumptions=[],
        warnings=[],
        evidence=[],
    )

    agg = aggregate_memory_requirements(weights=w, kv_cache=kv, runtime_overhead=ov)
    feas = evaluate_memory_feasibility(requirement=agg, hardware_budget=budget)

    assert agg.is_partial
    assert feas.internal_status == InternalFeasibilityStatus.UNKNOWN
