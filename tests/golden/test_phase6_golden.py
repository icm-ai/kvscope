"""Golden tests for Phase 6 Hardware Memory Budget and Runtime Overhead calculations.

Golden Case Expected Values (Hand Calculated):

Golden Case A (Synthetic Discrete Backend):
- Physical Total: 16 GiB (17,179,869,184 B)
- Base Runtime: 512 MiB (536,870,912 B)
- Per-Billion Parameters (8B @ 64 MiB/B): 512 MiB (536,870,912 B)
- Workspace (4 GiB @ 5%): 214,748,365 B
- Graph Capture: 1 GiB (1,073,741,824 B)
- Backend Buffers: 128 MiB (134,217,728 B)
- Expected Subtotal: 2,496,449,681 B
- Expected Allocator Margin (5% of Subtotal): 124,822,485 B
- Expected Total Overhead: 2,621,272,166 B

Golden Case B (Synthetic Unified Memory Budget):
- Physical Total: 16 GiB (17,179,869,184 B)
- Total Reserve: [3.0 GiB (3,221,225,472 B), 4.5 GiB, 6.0 GiB (6,442,450,944 B)]
- Allocatable Before Headroom: [10.0 GiB, 11.5 GiB, 13.0 GiB]
- Recommended Headroom (10%): [1,073,741,824 B, 1,234,803,098 B, 1,395,864,372 B]
- Recommended Allocatable: [9,341,553,868 B, 11,113,227,878 B, 12,884,901,888 B]

Golden Case C (Graph Capture Disabled):
- Same setup as Case A, graph capture disabled.
- Graph Capture Reserve: 0 B
- Expected Subtotal: 1,422,707,917 B
- Expected Allocator Margin (5% of Subtotal): 71,135,396 B
- Expected Total Overhead: 1,493,843,313 B
"""

from decimal import Decimal

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


def _make_golden_synthetic_hardware(
    topology: MemoryTopology = MemoryTopology.DISCRETE,
) -> HardwareProfile:
    if topology == MemoryTopology.DISCRETE:
        res = HardwareReserveProfile(
            os_reserve=ByteRange.exact(0),
            display_reserve=ByteRange.exact(0),
            background_process_reserve=ByteRange.exact(0),
            device_specific_reserve=ByteRange.exact(0),
        )
    else:
        res = HardwareReserveProfile(
            os_reserve=ByteRange(
                lower_bytes=2 * 1024**3,
                expected_bytes=3 * 1024**3,
                upper_bytes=4 * 1024**3,
            ),
            display_reserve=ByteRange.exact(0),
            background_process_reserve=ByteRange(
                lower_bytes=512 * 1024**2,
                expected_bytes=1024**3,
                upper_bytes=1536 * 1024**2,
            ),
            device_specific_reserve=ByteRange.exact(0),
        )

    return HardwareProfile(
        schema_version="0.1",
        profile_id="synthetic-golden-hw",
        name="Synthetic Golden Hardware",
        vendor="synthetic",
        memory_topology=topology,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        reserves=res,
        recommended_headroom_ratio=RatioRange.exact(Decimal("0.10")),
        evidence=[
            Evidence(
                evidence_id="syn-1",
                source_type="synthetic_test",
                source="Phase 6 Golden Spec",
            )
        ],
        confidence=Confidence.EXACT,
        status=ProfileStatus.VERIFIED,
    )


def _make_golden_synthetic_backend() -> BackendProfile:
    return BackendProfile(
        schema_version="0.1",
        profile_id="synthetic-golden-backend",
        backend_id="synthetic_be",
        display_name="Synthetic Golden Backend",
        memory_model=BackendMemoryModel(
            base_runtime=ByteRange.exact(512 * 1024**2),
            per_billion_parameters=ByteRange.exact(64 * 1024**2),
            workspace_ratio_of_resident_weights=RatioRange.exact(Decimal("0.05")),
            graph_capture_reserve=ByteRange.exact(1024**3),
            backend_buffers=ByteRange.exact(128 * 1024**2),
            allocator_margin_ratio_of_subtotal=RatioRange.exact(Decimal("0.05")),
            graph_capture_supported=True,
        ),
        evidence=[
            Evidence(
                evidence_id="syn-2",
                source_type="synthetic_test",
                source="Phase 6 Golden Spec",
            )
        ],
        confidence=Confidence.EXACT,
        status=ProfileStatus.VERIFIED,
    )


def test_golden_case_a_synthetic_discrete_backend() -> None:
    hw = _make_golden_synthetic_hardware(topology=MemoryTopology.DISCRETE)
    be = _make_golden_synthetic_backend()

    overhead = estimate_runtime_overhead(
        backend=be,
        hardware=hw,
        resident_weight_bytes=4 * 1024**3,
        parameter_count=8_000_000_000,
        graph_capture_enabled=True,
        allow_incomplete_profile=True,
    )

    # Verify exact hand-calculated numbers
    assert overhead.parameter_scaled_overhead.expected_bytes == 536_870_912
    assert overhead.workspace.expected_bytes == 214_748_365
    assert overhead.base_runtime.expected_bytes == 536_870_912
    assert overhead.graph_capture.expected_bytes == 1_073_741_824
    assert overhead.backend_buffers.expected_bytes == 134_217_728

    assert overhead.subtotal_before_allocator_margin.expected_bytes == 2_496_449_741
    assert overhead.allocator_margin.expected_bytes == 124_822_488
    assert overhead.total_runtime_overhead.expected_bytes == 2_621_272_229


def test_golden_case_b_synthetic_unified_memory_budget() -> None:
    hw = _make_golden_synthetic_hardware(topology=MemoryTopology.UNIFIED)

    budget = estimate_hardware_memory_budget(hw, user_reserve_bytes=512 * 1024**2)

    # Total Non-Model Reserve
    assert budget.total_non_model_reserve.lower_bytes == 3_221_225_472
    assert budget.total_non_model_reserve.expected_bytes == 4_831_838_208
    assert budget.total_non_model_reserve.upper_bytes == 6_442_450_944

    # Allocatable Before Headroom
    assert budget.allocatable_before_headroom.lower_bytes == 10_737_418_240
    assert budget.allocatable_before_headroom.expected_bytes == 12_348_030_976
    assert budget.allocatable_before_headroom.upper_bytes == 13_958_643_712

    # Recommended Headroom (10%)
    assert budget.recommended_headroom.lower_bytes == 1_073_741_824
    assert budget.recommended_headroom.expected_bytes == 1_234_803_098
    assert budget.recommended_headroom.upper_bytes == 1_395_864_372

    # Recommended Allocatable Range
    assert budget.recommended_allocatable.lower_bytes == 9_341_553_868
    assert budget.recommended_allocatable.expected_bytes == 11_113_227_878
    assert budget.recommended_allocatable.upper_bytes == 12_884_901_888


def test_golden_case_c_graph_capture_disabled() -> None:
    hw = _make_golden_synthetic_hardware(topology=MemoryTopology.DISCRETE)
    be = _make_golden_synthetic_backend()

    overhead = estimate_runtime_overhead(
        backend=be,
        hardware=hw,
        resident_weight_bytes=4 * 1024**3,
        parameter_count=8_000_000_000,
        graph_capture_enabled=False,
        allow_incomplete_profile=True,
    )

    assert overhead.graph_capture.expected_bytes == 0
    assert overhead.subtotal_before_allocator_margin.expected_bytes == 1_422_707_917
    assert overhead.allocator_margin.expected_bytes == 71_135_396
    assert overhead.total_runtime_overhead.expected_bytes == 1_493_843_313
