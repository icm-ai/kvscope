"""Unit tests for Hardware Memory Budget Engine."""

from decimal import Decimal

from kvscope.calculators.hardware_budget import estimate_hardware_memory_budget
from kvscope.domain.enums import MemoryTopology
from kvscope.domain.evidence import Evidence
from kvscope.domain.hardware import (
    HardwareProfile,
    HardwareReserveProfile,
    MemoryQuantityInput,
)
from kvscope.domain.ranges import ByteRange, RatioRange


def test_hardware_budget_discrete() -> None:
    prof = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete 16G",
        vendor="vendor",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        reserves=HardwareReserveProfile(
            os_reserve=ByteRange.exact(0),
            display_reserve=ByteRange.exact(512 * 1024**2),
            background_process_reserve=ByteRange.exact(0),
            device_specific_reserve=ByteRange.exact(256 * 1024**2),
        ),
        recommended_headroom_ratio=RatioRange.exact(Decimal("0.10")),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )

    budget = estimate_hardware_memory_budget(prof, user_reserve_bytes=512 * 1024**2)

    total_bytes = 16 * 1024**3
    res_bytes = (512 + 256 + 512) * 1024**2  # 1280 MiB

    assert budget.physical_total_bytes == total_bytes
    assert budget.total_non_model_reserve.expected_bytes == res_bytes
    alloc_expected = total_bytes - res_bytes
    assert budget.allocatable_before_headroom.expected_bytes == alloc_expected

    # Headroom = ceil(alloc_expected * 0.10)
    headroom_expected = 1583769191
    assert budget.recommended_headroom.expected_bytes == headroom_expected
    assert (
        budget.recommended_allocatable.expected_bytes
        == alloc_expected - headroom_expected
    )


def test_hardware_budget_unified_warning() -> None:
    prof = HardwareProfile(
        schema_version="0.1",
        profile_id="unified-16g",
        name="Unified 16G",
        vendor="vendor",
        memory_topology=MemoryTopology.UNIFIED,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )
    budget = estimate_hardware_memory_budget(prof)
    assert any("Unified memory" in w for w in budget.warnings)


def test_hardware_budget_total_override() -> None:
    prof = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete 16G",
        vendor="vendor",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )
    budget = estimate_hardware_memory_budget(
        prof, total_memory_override_bytes=24 * 1024**3
    )
    assert budget.physical_total_bytes == 24 * 1024**3
    assert any("Physical total memory overridden" in a for a in budget.assumptions)


def test_hardware_budget_invalid_inputs_and_additional_reserves() -> None:
    prof = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete 16G",
        vendor="vendor",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )

    import pytest

    with pytest.raises(ValueError, match="user_reserve_bytes must be non-negative"):
        estimate_hardware_memory_budget(prof, user_reserve_bytes=-10)

    with pytest.raises(ValueError, match="strictly positive"):
        estimate_hardware_memory_budget(prof, total_memory_override_bytes=0)

    # Test custom additional reserves
    custom_res = [ByteRange.exact(100 * 1024**2), ByteRange.exact(200 * 1024**2)]
    budget = estimate_hardware_memory_budget(prof, additional_reserves=custom_res)
    assert any("additional custom reserve ranges" in a for a in budget.assumptions)
