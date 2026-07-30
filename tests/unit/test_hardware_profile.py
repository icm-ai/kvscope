"""Unit tests for Hardware Profile domain models, registry, and resolver."""

from decimal import Decimal

import pytest

from kvscope.domain.enums import Confidence, MemoryTopology, ProfileStatus
from kvscope.domain.evidence import Evidence
from kvscope.domain.hardware import (
    HardwareProfile,
    MemoryQuantityInput,
)
from kvscope.errors import (
    HardwareProfileConflictError,
    HardwareProfileNotFoundError,
    ProfileValidationError,
)
from kvscope.registries.hardware import HardwareRegistry, get_default_hardware_registry
from kvscope.resolvers.hardware import resolve_hardware_profile


def test_memory_quantity_input() -> None:
    mq1 = MemoryQuantityInput(value=Decimal("16"), unit="GiB")
    assert mq1.to_bytes() == 16 * 1024**3

    mq2 = MemoryQuantityInput(value=Decimal("512"), unit="MiB")
    assert mq2.to_bytes() == 512 * 1024**2

    with pytest.raises(ValueError):
        MemoryQuantityInput(value=Decimal("0"), unit="GiB")


def test_hardware_profile_validation() -> None:
    prof = HardwareProfile(
        schema_version="0.1",
        profile_id="test-gpu-16g",
        name="Test GPU 16GB",
        vendor="test_vendor",
        aliases=["test-16g"],
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[
            Evidence(
                evidence_id="ev-1",
                source_type="measured_bench",
                source="test doc",
            )
        ],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )
    assert prof.total_memory_bytes == 16 * 1024**3
    assert prof.profile_id == "test-gpu-16g"


def test_hardware_registry_duplicates() -> None:
    prof1 = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-a",
        name="GPU A",
        vendor="vendor_a",
        aliases=["gpu-alias"],
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("8"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
    )
    prof2 = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-b",
        name="GPU B",
        vendor="vendor_a",
        aliases=["gpu-alias"],  # Conflict on alias!
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("8"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
    )

    reg = HardwareRegistry()
    reg.add(prof1)
    with pytest.raises(HardwareProfileConflictError):
        reg.add(prof2)


def test_hardware_registry_synthetic_rejection() -> None:
    prof_syn = HardwareProfile(
        schema_version="0.1",
        profile_id="syn-gpu",
        name="Synthetic GPU",
        vendor="synthetic",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("8"), unit="GiB"),
        evidence=[
            Evidence(
                evidence_id="e-syn",
                source_type="synthetic_test",
                source="test fixture",
            )
        ],
    )
    reg = HardwareRegistry()
    with pytest.raises(ProfileValidationError):
        reg.add(prof_syn, allow_synthetic=False)

    # Should succeed when allow_synthetic=True
    reg.add(prof_syn, allow_synthetic=True)
    assert reg.get("syn-gpu") is not None


def test_default_hardware_registry() -> None:
    reg = get_default_hardware_registry()
    profiles = reg.list_profiles()
    assert len(profiles) >= 6
    assert reg.get("generic-discrete-16gib") is not None
    assert reg.get("discrete-16gb") is not None  # alias lookup


def test_resolve_hardware_profile() -> None:
    # Resolve by ID
    res = resolve_hardware_profile("generic-discrete-16gib")
    assert res.profile.profile_id == "generic-discrete-16gib"
    assert res.source_type == "built_in_registry_id"

    # Resolve by alias
    res_alias = resolve_hardware_profile("discrete-16gb")
    assert res_alias.profile.profile_id == "generic-discrete-16gib"
    assert res_alias.source_type == "built_in_registry_alias"

    # Resolve by instance
    res_inst = resolve_hardware_profile(res.profile)
    assert res_inst.source_type == "instance"

    # Unknown profile error
    with pytest.raises(HardwareProfileNotFoundError):
        resolve_hardware_profile("nonexistent-gpu")
