"""Coverage tests for Registries, Resolvers, and Serialization error branches."""

import json
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest

from kvscope.domain.backend import BackendMemoryModel, BackendProfile
from kvscope.domain.enums import Confidence, MemoryTopology, ProfileStatus
from kvscope.domain.evidence import Evidence
from kvscope.domain.hardware import (
    HardwareProfile,
    MemoryQuantityInput,
)
from kvscope.errors import (
    BackendProfileError,
    HardwareProfileConflictError,
    ProfileValidationError,
)
from kvscope.registries.backends import BackendRegistry
from kvscope.registries.hardware import HardwareRegistry
from kvscope.resolvers.backend import resolve_backend_profile
from kvscope.resolvers.hardware import resolve_hardware_profile


def test_backend_registry_validation_errors() -> None:
    prof = BackendProfile(
        schema_version="0.1",
        profile_id="p1",
        backend_id="b1",
        display_name="P1",
        aliases=["b1-alias"],
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )
    reg = BackendRegistry([prof])

    # Duplicate ID
    with pytest.raises(BackendProfileError, match="conflicts with entry or alias"):
        reg.add(prof)

    # Duplicate Alias
    prof_dup_alias = BackendProfile(
        schema_version="0.1",
        profile_id="p2",
        backend_id="b2",
        display_name="B2",
        aliases=["b1-alias"],
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )
    with pytest.raises(BackendProfileError, match="conflicts with ID or alias"):
        reg.add(prof_dup_alias)

    # Missing Evidence
    prof_no_ev = BackendProfile(
        schema_version="0.1",
        profile_id="p_no_ev",
        backend_id="b_no_ev",
        display_name="No EV",
        memory_model=BackendMemoryModel(),
        evidence=[],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )
    with pytest.raises(ProfileValidationError, match="must contain evidence"):
        reg.add(prof_no_ev)

    # Deprecated without notes
    prof_dep = BackendProfile(
        schema_version="0.1",
        profile_id="p_dep",
        backend_id="b_dep",
        display_name="Dep",
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        confidence=Confidence.HIGH,
        status=ProfileStatus.DEPRECATED,
        notes=[],
    )
    with pytest.raises(ProfileValidationError, match="must provide notes"):
        reg.add(prof_dep)

    # Synthetic test rejection when allow_synthetic=False
    prof_synth = BackendProfile(
        schema_version="0.1",
        profile_id="p_synth",
        backend_id="b_synth",
        display_name="Synth",
        memory_model=BackendMemoryModel(),
        evidence=[
            Evidence(evidence_id="e1", source_type="synthetic_test", source="s1")
        ],
        confidence=Confidence.HIGH,
        status=ProfileStatus.VERIFIED,
    )
    with pytest.raises(ProfileValidationError, match="synthetic_test' not allowed"):
        reg.add(prof_synth, allow_synthetic=False)


def test_hardware_registry_validation_errors() -> None:
    hw = HardwareProfile(
        schema_version="0.1",
        profile_id="hw1",
        name="HW 1",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        supported_backend_ids=["vllm", "vllm"],  # Duplicates
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )

    reg = HardwareRegistry()
    with pytest.raises(ProfileValidationError, match="backend_ids contains duplicates"):
        reg.add(hw)

    hw_dup = HardwareProfile(
        schema_version="0.1",
        profile_id="hw1",
        name="HW 1",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )
    reg2 = HardwareRegistry([hw_dup])
    with pytest.raises(HardwareProfileConflictError):
        reg2.add(hw_dup)


def test_backend_and_hardware_registry_from_directory() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        yaml_file = tmp_path / "custom.json"
        data = {
            "schema_version": "0.1",
            "profile_id": "dir-prof",
            "backend_id": "dir_be",
            "display_name": "Dir BE",
            "memory_model": {},
            "evidence": [{"evidence_id": "e1", "source_type": "doc", "source": "s1"}],
            "confidence": "high",
            "status": "verified",
        }
        yaml_file.write_text(json.dumps([data]), encoding="utf-8")

        reg = BackendRegistry.from_directory(tmp_path)
        assert reg.get("dir-prof") is not None


def test_resolver_candidate_rejections(monkeypatch: pytest.MonkeyPatch) -> None:
    prof_invalid_ver = BackendProfile(
        schema_version="0.1",
        profile_id="p_inv_ver",
        backend_id="b_rej",
        display_name="Inv Ver",
        version_specifier="<1.0.0",
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        status=ProfileStatus.VERIFIED,
    )
    prof_dep = BackendProfile(
        schema_version="0.1",
        profile_id="p_dep",
        backend_id="b_rej",
        display_name="Dep",
        version_specifier=">=1.0.0",
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        status=ProfileStatus.DEPRECATED,
        notes=["deprecated"],
    )
    prof_unver = BackendProfile(
        schema_version="0.1",
        profile_id="p_unver",
        backend_id="b_rej",
        display_name="Unver",
        version_specifier=">=1.0.0",
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        status=ProfileStatus.UNVERIFIED,
    )
    prof_valid = BackendProfile(
        schema_version="0.1",
        profile_id="p_valid",
        backend_id="b_rej",
        display_name="Valid",
        version_specifier=">=1.0.0",
        supported_memory_topologies=[MemoryTopology.DISCRETE],
        supported_vendors=["nvidia"],
        supported_families=["ampere"],
        memory_model=BackendMemoryModel(),
        evidence=[Evidence(evidence_id="e1", source_type="doc", source="s1")],
        status=ProfileStatus.VERIFIED,
    )

    custom_reg = BackendRegistry([prof_invalid_ver, prof_dep, prof_unver, prof_valid])
    monkeypatch.setattr(
        "kvscope.resolvers.backend.get_default_backend_registry",
        lambda: custom_reg,
    )

    # Rejection by version mismatch
    res1 = resolve_backend_profile("b_rej", version="1.5.0", allow_unverified=True)
    assert res1.profile.profile_id == "p_valid"

    # Rejection by allow_deprecated=False and allow_unverified=False
    res2 = resolve_backend_profile(
        "b_rej", version="1.0.0", allow_deprecated=False, allow_unverified=False
    )
    assert res2.profile.profile_id == "p_valid"


def test_hardware_resolver_rejections(monkeypatch: pytest.MonkeyPatch) -> None:
    hw_dep = HardwareProfile(
        schema_version="0.1",
        profile_id="hw_dep",
        name="HW Deprecated",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
        status=ProfileStatus.DEPRECATED,
        notes=["deprecated"],
    )
    hw_valid = HardwareProfile(
        schema_version="0.1",
        profile_id="hw_valid",
        name="HW Valid",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
        status=ProfileStatus.VERIFIED,
    )

    custom_reg = HardwareRegistry([hw_dep, hw_valid])
    monkeypatch.setattr(
        "kvscope.resolvers.hardware.get_default_hardware_registry",
        lambda: custom_reg,
    )

    res = resolve_hardware_profile("hw_valid", allow_deprecated=False)
    assert res.profile.profile_id == "hw_valid"
