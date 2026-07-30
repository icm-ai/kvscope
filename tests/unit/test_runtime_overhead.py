"""Unit tests for Runtime Overhead Engine."""

from decimal import Decimal

import pytest

from kvscope.calculators.overhead import estimate_runtime_overhead
from kvscope.domain.backend import BackendMemoryModel, BackendProfile
from kvscope.domain.enums import Confidence, MemoryTopology, ProfileStatus
from kvscope.domain.evidence import Evidence
from kvscope.domain.hardware import HardwareProfile, MemoryQuantityInput
from kvscope.domain.ranges import ByteRange, RatioRange
from kvscope.domain.runtime_overhead import RuntimeOverheadOverrides
from kvscope.errors import IncompleteBackendProfileError, RuntimeOverheadInputError


def test_runtime_overhead_calculation() -> None:
    hw = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete 16G",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )

    backend = BackendProfile(
        schema_version="0.1",
        profile_id="test-backend-verified",
        backend_id="test_be",
        display_name="Verified Backend",
        memory_model=BackendMemoryModel(
            base_runtime=ByteRange.exact(512 * 1024**2),  # 512 MiB
            per_billion_parameters=ByteRange.exact(64 * 1024**2),  # 64 MiB/B
            workspace_ratio_of_resident_weights=RatioRange.exact(Decimal("0.05")),  # 5%
            graph_capture_reserve=ByteRange.exact(1024**3),  # 1 GiB
            backend_buffers=ByteRange.exact(128 * 1024**2),  # 128 MiB
            allocator_margin_ratio_of_subtotal=RatioRange.exact(Decimal("0.05")),  # 5%
            graph_capture_supported=True,
        ),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )

    # 8B parameters, 4 GiB weights, graph capture enabled
    res = estimate_runtime_overhead(
        backend=backend,
        hardware=hw,
        resident_weight_bytes=4 * 1024**3,
        parameter_count=8_000_000_000,
        graph_capture_enabled=True,
    )

    # Base: 512 MiB = 536870912
    assert res.base_runtime.expected_bytes == 512 * 1024**2

    # Param scaled: 8 * 64 MiB = 512 MiB
    assert res.parameter_scaled_overhead.expected_bytes == 512 * 1024**2

    # Workspace: 5% of 4 GiB = 214,748,364.8 -> 214748365 bytes (ceil)
    ws_expected = 214_748_365
    assert res.workspace.expected_bytes == ws_expected

    # Graph capture: 1 GiB = 1073741824
    assert res.graph_capture.expected_bytes == 1024**3

    # Backend buffers: 128 MiB = 134217728
    assert res.backend_buffers.expected_bytes == 128 * 1024**2

    # Subtotal
    subtotal_expected = 2_496_449_741
    assert res.subtotal_before_allocator_margin.expected_bytes == subtotal_expected

    # Allocator margin: 5% of subtotal
    margin_expected = 124_822_488
    assert res.allocator_margin.expected_bytes == margin_expected

    # Total
    assert (
        res.total_runtime_overhead.expected_bytes == subtotal_expected + margin_expected
    )


def test_runtime_overhead_unverified_rejection() -> None:
    hw = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete 16G",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )

    backend = BackendProfile(
        schema_version="0.1",
        profile_id="unverified-be",
        backend_id="test_unverified",
        display_name="Unverified Backend Template",
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
        confidence=Confidence.UNKNOWN,
        status=ProfileStatus.UNVERIFIED,
        notes=["Template profile"],
    )

    # Should raise IncompleteBackendProfileError without allow_incomplete_profile
    with pytest.raises(IncompleteBackendProfileError):
        estimate_runtime_overhead(
            backend=backend,
            hardware=hw,
            resident_weight_bytes=4 * 1024**3,
            parameter_count=7_000_000_000,
            allow_incomplete_profile=False,
        )

    # Should succeed when allow_incomplete_profile=True
    res = estimate_runtime_overhead(
        backend=backend,
        hardware=hw,
        resident_weight_bytes=4 * 1024**3,
        parameter_count=7_000_000_000,
        allow_incomplete_profile=True,
    )
    assert res.backend_profile_id == "unverified-be"


def test_runtime_overhead_graph_capture_unsupported() -> None:
    hw = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete 16G",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )

    backend = BackendProfile(
        schema_version="0.1",
        profile_id="no-gc-backend",
        backend_id="no_gc",
        display_name="No GC Backend",
        memory_model=BackendMemoryModel(graph_capture_supported=False),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )

    with pytest.raises(RuntimeOverheadInputError):
        estimate_runtime_overhead(
            backend=backend,
            hardware=hw,
            resident_weight_bytes=4 * 1024**3,
            parameter_count=7_000_000_000,
            graph_capture_enabled=True,
        )


def test_runtime_overhead_overrides() -> None:
    hw = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete 16G",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )

    backend = BackendProfile(
        schema_version="0.1",
        profile_id="unverified-be",
        backend_id="test_unverified",
        display_name="Unverified Backend Template",
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
        confidence=Confidence.UNKNOWN,
        status=ProfileStatus.UNVERIFIED,
    )

    overrides = RuntimeOverheadOverrides(
        base_runtime=ByteRange.exact(256 * 1024**2),
        per_billion_parameters=ByteRange.exact(0),
        workspace_ratio=RatioRange.exact(Decimal("0.02")),
        graph_capture_reserve=ByteRange.exact(0),
        backend_buffers=ByteRange.exact(64 * 1024**2),
        allocator_margin_ratio=RatioRange.exact(Decimal("0.01")),
    )

    res = estimate_runtime_overhead(
        backend=backend,
        hardware=hw,
        resident_weight_bytes=4 * 1024**3,
        parameter_count=7_000_000_000,
        user_overrides=overrides,
    )
    assert res.base_runtime.expected_bytes == 256 * 1024**2
    assert any("Base runtime overridden" in a for a in res.assumptions)


def test_runtime_overhead_negative_inputs_and_missing_param_count() -> None:
    hw = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete 16G",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )

    backend = BackendProfile(
        schema_version="0.1",
        profile_id="test-backend-verified",
        backend_id="test_be",
        display_name="Verified Backend",
        memory_model=BackendMemoryModel(
            per_billion_parameters=ByteRange.exact(64 * 1024**2),
            graph_capture_supported=True,
        ),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )

    # Negative resident_weight_bytes
    with pytest.raises(RuntimeOverheadInputError) as exc1:
        estimate_runtime_overhead(
            backend=backend,
            hardware=hw,
            resident_weight_bytes=-1,
        )
    assert "resident_weight_bytes" in str(exc1.value)

    # Negative parameter_count
    with pytest.raises(RuntimeOverheadInputError) as exc2:
        estimate_runtime_overhead(
            backend=backend,
            hardware=hw,
            resident_weight_bytes=100,
            parameter_count=-5,
        )
    assert "parameter_count" in str(exc2.value)

    # Missing parameter_count when per_billion > 0
    with pytest.raises(RuntimeOverheadInputError) as exc3:
        estimate_runtime_overhead(
            backend=backend,
            hardware=hw,
            resident_weight_bytes=100,
            parameter_count=None,
        )
    assert "parameter_count is required" in str(exc3.value)


def test_runtime_overhead_unified_memory_warning_and_override_branches() -> None:
    hw_unified = HardwareProfile(
        schema_version="0.1",
        profile_id="mac-unified-36g",
        name="M3 Max Unified",
        vendor="apple",
        memory_topology=MemoryTopology.UNIFIED,
        confidence=Confidence.HIGH,
        total_memory=MemoryQuantityInput(value=Decimal("36"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )

    backend = BackendProfile(
        schema_version="0.1",
        profile_id="test-backend-verified",
        backend_id="test_be",
        display_name="Verified Backend",
        confidence=Confidence.HIGH,
        memory_model=BackendMemoryModel(graph_capture_supported=True),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        status=ProfileStatus.VERIFIED,
    )

    overrides = RuntimeOverheadOverrides(
        graph_capture_reserve=ByteRange.exact(512 * 1024**2),
    )

    res = estimate_runtime_overhead(
        backend=backend,
        hardware=hw_unified,
        resident_weight_bytes=4 * 1024**3,
        parameter_count=7_000_000_000,
        graph_capture_enabled=True,
        user_overrides=overrides,
    )

    assert res.confidence == Confidence.MEDIUM  # downgraded due to UNIFIED
    assert any("Unified memory topology" in w for w in res.warnings)
    assert any("Graph capture reserve overridden" in a for a in res.assumptions)
