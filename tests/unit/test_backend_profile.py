"""Unit tests for Backend Profile domain models, registry, and resolver."""

from decimal import Decimal

import pytest

from kvscope.domain.backend import BackendMemoryModel, BackendProfile
from kvscope.domain.enums import Confidence, MemoryTopology, ProfileStatus
from kvscope.domain.evidence import Evidence
from kvscope.domain.hardware import HardwareProfile, MemoryQuantityInput
from kvscope.domain.ranges import ByteRange, RatioRange
from kvscope.errors import (
    BackendProfileAmbiguousError,
    BackendProfileNotFoundError,
    BackendVersionMismatchError,
)
from kvscope.registries.backends import BackendRegistry, get_default_backend_registry
from kvscope.resolvers.backend import resolve_backend_profile


def test_backend_profile_validation() -> None:
    prof = BackendProfile(
        schema_version="0.1",
        profile_id="vllm-0.9.0",
        backend_id="vllm",
        display_name="vLLM 0.9.0",
        version_specifier=">=0.9.0,<0.10.0",
        supported_memory_topologies=[MemoryTopology.DISCRETE],
        memory_model=BackendMemoryModel(
            base_runtime=ByteRange.exact(512 * 1024**2),
            per_billion_parameters=ByteRange.exact(64 * 1024**2),
            workspace_ratio_of_resident_weights=RatioRange.exact(Decimal("0.05")),
            graph_capture_reserve=ByteRange.exact(1024**3),
            backend_buffers=ByteRange.exact(128 * 1024**2),
            allocator_margin_ratio_of_subtotal=RatioRange.exact(Decimal("0.05")),
        ),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="vllm docs")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )
    assert prof.profile_id == "vllm-0.9.0"
    assert prof.backend_id == "vllm"


def test_default_backend_registry() -> None:
    reg = get_default_backend_registry()
    profiles = reg.list_profiles()
    assert len(profiles) == 0
    assert reg.get("vllm-generic-template") is None
    assert reg.get("vllm") is None


def test_resolve_backend_profile_version_specifier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prof = BackendProfile(
        schema_version="0.1",
        profile_id="vllm-0.5.0",
        backend_id="vllm",
        display_name="vLLM 0.5.0",
        aliases=["vllm-test"],
        version_specifier=">=0.4.0,<1.0.0",
        supported_memory_topologies=[MemoryTopology.DISCRETE],
        supported_vendors=["nvidia"],
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )
    custom_reg = BackendRegistry([prof])
    monkeypatch.setattr(
        "kvscope.resolvers.backend.get_default_backend_registry",
        lambda: custom_reg,
    )

    # Generic lookup without version
    res = resolve_backend_profile("vllm", allow_unverified=True)
    assert res.profile.backend_id == "vllm"
    assert any("No backend version specified" in w for w in res.warnings)

    # Valid version matching
    res_ver = resolve_backend_profile("vllm", version="0.5.0", allow_unverified=True)
    assert res_ver.profile.backend_id == "vllm"

    # Version mismatch
    with pytest.raises(BackendVersionMismatchError):
        resolve_backend_profile("vllm", version="2.0.0", allow_unverified=True)


def test_resolve_backend_profile_hardware_matching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prof = BackendProfile(
        schema_version="0.1",
        profile_id="vllm-0.5.0",
        backend_id="vllm",
        display_name="vLLM 0.5.0",
        version_specifier=">=0.4.0,<1.0.0",
        supported_memory_topologies=[MemoryTopology.DISCRETE],
        supported_vendors=["nvidia"],
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )
    custom_reg = BackendRegistry([prof])
    monkeypatch.setattr(
        "kvscope.resolvers.backend.get_default_backend_registry",
        lambda: custom_reg,
    )

    hw_discrete = HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete GPU",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )

    res = resolve_backend_profile("vllm", hardware=hw_discrete, allow_unverified=True)
    assert res.profile.backend_id == "vllm"


def test_resolve_backend_profile_not_found() -> None:
    with pytest.raises(BackendProfileNotFoundError):
        resolve_backend_profile("nonexistent_backend", allow_unverified=True)


def test_resolve_backend_profile_ambiguity(monkeypatch: pytest.MonkeyPatch) -> None:
    prof1 = BackendProfile(
        schema_version="0.1",
        profile_id="test-backend-v1",
        backend_id="test_be_tied",
        display_name="Test BE v1",
        version_specifier=">=1.0.0",
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        status=ProfileStatus.VERIFIED,
    )
    prof2 = BackendProfile(
        schema_version="0.1",
        profile_id="test-backend-v2",
        backend_id="test_be_tied",
        display_name="Test BE v2",
        version_specifier=">=1.0.0",
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        status=ProfileStatus.VERIFIED,
    )

    custom_reg = BackendRegistry([prof1, prof2])
    monkeypatch.setattr(
        "kvscope.resolvers.backend.get_default_backend_registry",
        lambda: custom_reg,
    )

    with pytest.raises(BackendProfileAmbiguousError):
        resolve_backend_profile("test_be_tied", version="1.0.0", allow_unverified=True)
