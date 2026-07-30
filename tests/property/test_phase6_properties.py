"""Property-based tests for Phase 6 calculations using Hypothesis."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from kvscope.calculators.hardware_budget import estimate_hardware_memory_budget
from kvscope.calculators.overhead import estimate_runtime_overhead
from kvscope.domain.backend import BackendMemoryModel, BackendProfile
from kvscope.domain.enums import Confidence, MemoryTopology, ProfileStatus
from kvscope.domain.evidence import Evidence
from kvscope.domain.hardware import (
    HardwareProfile,
    HardwareReserveProfile,
    MemoryQuantityInput,
)
from kvscope.domain.ranges import ByteRange, RatioRange


def _make_test_hardware(
    headroom_ratio: Decimal = Decimal("0.10"),
    topology: MemoryTopology = MemoryTopology.DISCRETE,
) -> HardwareProfile:
    return HardwareProfile(
        schema_version="0.1",
        profile_id="prop-hw",
        name="Property Hardware",
        vendor="vendor",
        memory_topology=topology,
        total_memory=MemoryQuantityInput(value=Decimal("32"), unit="GiB"),
        reserves=HardwareReserveProfile(
            os_reserve=ByteRange.exact(1024**3),
            display_reserve=ByteRange.exact(512 * 1024**2),
            background_process_reserve=ByteRange.exact(512 * 1024**2),
            device_specific_reserve=ByteRange.exact(256 * 1024**2),
        ),
        recommended_headroom_ratio=RatioRange.exact(headroom_ratio),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
        status=ProfileStatus.VERIFIED,
    )


def _make_test_backend(
    workspace_ratio: Decimal = Decimal("0.05"),
    margin_ratio: Decimal = Decimal("0.05"),
) -> BackendProfile:
    return BackendProfile(
        schema_version="0.1",
        profile_id="prop-backend",
        backend_id="prop_be",
        display_name="Property Backend",
        memory_model=BackendMemoryModel(
            base_runtime=ByteRange.exact(512 * 1024**2),
            per_billion_parameters=ByteRange.exact(64 * 1024**2),
            workspace_ratio_of_resident_weights=RatioRange.exact(workspace_ratio),
            graph_capture_reserve=ByteRange.exact(1024**3),
            backend_buffers=ByteRange.exact(128 * 1024**2),
            allocator_margin_ratio_of_subtotal=RatioRange.exact(margin_ratio),
            graph_capture_supported=True,
        ),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )


@given(
    weights_1=st.integers(min_value=0, max_value=50 * 1024**3),
    weights_delta=st.integers(min_value=0, max_value=50 * 1024**3),
)
def test_workspace_monotonicity_with_resident_weight(
    weights_1: int, weights_delta: int
) -> None:
    """Invariant 1: resident weight 增加时 workspace 不应减少."""
    weights_2 = weights_1 + weights_delta
    hw = _make_test_hardware()
    be = _make_test_backend()

    res1 = estimate_runtime_overhead(
        backend=be,
        hardware=hw,
        resident_weight_bytes=weights_1,
        parameter_count=7_000_000_000,
    )
    res2 = estimate_runtime_overhead(
        backend=be,
        hardware=hw,
        resident_weight_bytes=weights_2,
        parameter_count=7_000_000_000,
    )

    assert res2.workspace.lower_bytes >= res1.workspace.lower_bytes
    assert res2.workspace.expected_bytes >= res1.workspace.expected_bytes
    assert res2.workspace.upper_bytes >= res1.workspace.upper_bytes


@given(
    param_1=st.integers(min_value=0, max_value=100_000_000_000),
    param_delta=st.integers(min_value=0, max_value=100_000_000_000),
)
def test_parameter_scaled_overhead_monotonicity(param_1: int, param_delta: int) -> None:
    """Invariant 2: parameter_count 增加时 parameter-scaled overhead 不应减少."""
    param_2 = param_1 + param_delta
    hw = _make_test_hardware()
    be = _make_test_backend()

    res1 = estimate_runtime_overhead(
        backend=be,
        hardware=hw,
        resident_weight_bytes=4 * 1024**3,
        parameter_count=param_1,
    )
    res2 = estimate_runtime_overhead(
        backend=be,
        hardware=hw,
        resident_weight_bytes=4 * 1024**3,
        parameter_count=param_2,
    )

    assert (
        res2.parameter_scaled_overhead.expected_bytes
        >= res1.parameter_scaled_overhead.expected_bytes
    )


@given(
    weights=st.integers(min_value=1024**3, max_value=10 * 1024**3),
    param_count=st.integers(min_value=1_000_000_000, max_value=20_000_000_000),
)
def test_graph_capture_total_overhead_comparison(
    weights: int, param_count: int
) -> None:
    """Invariant 5: 开启 graph capture 后 total 不应小于关闭状态."""
    hw = _make_test_hardware()
    be = _make_test_backend()

    res_off = estimate_runtime_overhead(
        backend=be,
        hardware=hw,
        resident_weight_bytes=weights,
        parameter_count=param_count,
        graph_capture_enabled=False,
    )
    res_on = estimate_runtime_overhead(
        backend=be,
        hardware=hw,
        resident_weight_bytes=weights,
        parameter_count=param_count,
        graph_capture_enabled=True,
    )

    assert (
        res_on.total_runtime_overhead.expected_bytes
        >= res_off.total_runtime_overhead.expected_bytes
    )


@given(
    user_reserve_1=st.integers(min_value=0, max_value=10 * 1024**3),
    user_reserve_delta=st.integers(min_value=0, max_value=10 * 1024**3),
)
def test_reserve_allocatable_monotonicity(
    user_reserve_1: int, user_reserve_delta: int
) -> None:
    """Invariant 6: reserve 增加时 allocatable memory 不应增加."""
    user_reserve_2 = user_reserve_1 + user_reserve_delta
    hw = _make_test_hardware()

    b1 = estimate_hardware_memory_budget(hw, user_reserve_bytes=user_reserve_1)
    b2 = estimate_hardware_memory_budget(hw, user_reserve_bytes=user_reserve_2)

    assert (
        b2.allocatable_before_headroom.expected_bytes
        <= b1.allocatable_before_headroom.expected_bytes
    )
    assert (
        b2.recommended_allocatable.expected_bytes
        <= b1.recommended_allocatable.expected_bytes
    )


@given(
    weights=st.integers(min_value=0, max_value=20 * 1024**3),
    param_count=st.integers(min_value=0, max_value=50_000_000_000),
)
def test_subtotal_and_total_invariants(weights: int, param_count: int) -> None:
    """Invariants 8 & 9: total is component sum; subtotal excludes margin."""
    hw = _make_test_hardware()
    be = _make_test_backend()

    res = estimate_runtime_overhead(
        backend=be,
        hardware=hw,
        resident_weight_bytes=weights,
        parameter_count=param_count,
        graph_capture_enabled=True,
    )

    expected_subtotal = (
        res.base_runtime.expected_bytes
        + res.parameter_scaled_overhead.expected_bytes
        + res.workspace.expected_bytes
        + res.graph_capture.expected_bytes
        + res.backend_buffers.expected_bytes
    )
    assert res.subtotal_before_allocator_margin.expected_bytes == expected_subtotal

    expected_total = expected_subtotal + res.allocator_margin.expected_bytes
    assert res.total_runtime_overhead.expected_bytes == expected_total

    # Non-negative integer check
    assert res.subtotal_before_allocator_margin.expected_bytes >= 0
    assert res.total_runtime_overhead.expected_bytes >= 0
