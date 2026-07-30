"""Unit tests for template profile isolation and constraints."""

from decimal import Decimal
from pathlib import Path

import pytest

from kvscope.calculators.overhead import estimate_runtime_overhead
from kvscope.domain.backend import BackendMemoryModel, BackendProfile
from kvscope.domain.enums import Confidence, MemoryTopology, ProfileStatus
from kvscope.domain.evidence import Evidence
from kvscope.domain.hardware import HardwareProfile, MemoryQuantityInput
from kvscope.domain.ranges import ByteRange, RatioRange
from kvscope.domain.runtime_overhead import RuntimeOverheadOverrides
from kvscope.errors import BackendProfileNotFoundError, IncompleteBackendProfileError
from kvscope.registries.backends import get_default_backend_registry
from kvscope.registries.loader import parse_backend_profile, safe_load_file_content
from kvscope.resolvers.backend import resolve_backend_profile

EXAMPLES_TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "examples" / "templates"


@pytest.fixture
def dummy_hardware() -> HardwareProfile:
    return HardwareProfile(
        schema_version="0.1",
        profile_id="gpu-16g",
        name="Discrete GPU",
        vendor="nvidia",
        memory_topology=MemoryTopology.DISCRETE,
        total_memory=MemoryQuantityInput(value=Decimal("16"), unit="GiB"),
        evidence=[Evidence(evidence_id="e1", source_type="spec", source="s1")],
    )


def test_default_registry_does_not_contain_templates() -> None:
    """Verify that official registry does not include template profiles."""
    registry = get_default_backend_registry()
    profiles = registry.list_profiles()
    assert len(profiles) == 0
    assert registry.get("vllm-generic-template") is None
    assert registry.get("vllm") is None


def test_resolve_backend_profile_does_not_auto_select_templates() -> None:
    """Verify that resolve_backend_profile fails on default registry."""
    with pytest.raises(BackendProfileNotFoundError):
        resolve_backend_profile("vllm")


def test_template_file_isolation_and_overhead_engine_rejection(
    dummy_hardware: HardwareProfile,
) -> None:
    """Verify explicit template loading and overhead engine rejection."""
    tmpl_path = EXAMPLES_TEMPLATES_DIR / "vllm-generic-template.yaml"
    assert tmpl_path.exists()

    raw_content = safe_load_file_content(tmpl_path)
    assert isinstance(raw_content, dict)
    template_profile = parse_backend_profile(raw_content, source_path=tmpl_path)

    assert template_profile.confidence == Confidence.UNKNOWN

    # Must raise IncompleteBackendProfileError by default
    with pytest.raises(IncompleteBackendProfileError) as exc_info:
        estimate_runtime_overhead(
            backend=template_profile,
            hardware=dummy_hardware,
            resident_weight_bytes=10 * 1024**3,
        )

    assert "template profile" in str(exc_info.value)


def test_template_profile_allowed_with_explicit_overrides_or_flag(
    dummy_hardware: HardwareProfile,
) -> None:
    """Verify calculation paths when explicitly allowed or overridden."""
    tmpl_path = EXAMPLES_TEMPLATES_DIR / "vllm-generic-template.yaml"
    raw_content = safe_load_file_content(tmpl_path)
    assert isinstance(raw_content, dict)
    template_profile = parse_backend_profile(raw_content, source_path=tmpl_path)

    # Path 1: allow_incomplete_profile=True
    est_incomplete = estimate_runtime_overhead(
        backend=template_profile,
        hardware=dummy_hardware,
        resident_weight_bytes=10 * 1024**3,
        parameter_count=7_000_000_000,
        allow_incomplete_profile=True,
    )
    assert est_incomplete.confidence == Confidence.UNKNOWN
    assert any("template" in w for w in est_incomplete.warnings)

    # Path 2: Full user overrides
    full_overrides = RuntimeOverheadOverrides(
        base_runtime=ByteRange.exact(500 * 1024**2),
        per_billion_parameters=ByteRange.exact(50 * 1024**2),
        workspace_ratio=RatioRange.exact(Decimal("0.05")),
        graph_capture_reserve=ByteRange.exact(1024**3),
        backend_buffers=ByteRange.exact(100 * 1024**2),
        allocator_margin_ratio=RatioRange.exact(Decimal("0.05")),
    )

    est_overridden = estimate_runtime_overhead(
        backend=template_profile,
        hardware=dummy_hardware,
        resident_weight_bytes=10 * 1024**3,
        parameter_count=7_000_000_000,
        user_overrides=full_overrides,
    )
    assert est_overridden.subtotal_before_allocator_margin.lower_bytes > 0
    assert est_overridden.is_partial is False


def test_template_with_allow_incomplete_does_not_become_zero_exact_estimate(
    dummy_hardware: HardwareProfile,
) -> None:
    """Verify that an incomplete template profile with allow_incomplete_profile=True

    does NOT yield a complete zero-overhead estimate, but is explicitly flagged.
    """
    tmpl_path = EXAMPLES_TEMPLATES_DIR / "vllm-generic-template.yaml"
    raw_content = safe_load_file_content(tmpl_path)
    assert isinstance(raw_content, dict)
    template_profile = parse_backend_profile(raw_content, source_path=tmpl_path)

    # Construct a zeroed memory model for testing zeroed template behavior
    zero_model = BackendMemoryModel(
        base_runtime=ByteRange.exact(0),
        per_billion_parameters=ByteRange.exact(0),
        workspace_ratio_of_resident_weights=RatioRange.exact(Decimal("0")),
        graph_capture_reserve=ByteRange.exact(0),
        backend_buffers=ByteRange.exact(0),
        allocator_margin_ratio_of_subtotal=RatioRange.exact(Decimal("0")),
    )
    zeroed_profile = template_profile.model_copy(update={"memory_model": zero_model})

    est = estimate_runtime_overhead(
        backend=zeroed_profile,
        hardware=dummy_hardware,
        resident_weight_bytes=10 * 1024**3,
        allow_incomplete_profile=True,
    )

    # 1. Must be flagged as partial
    assert est.is_partial is True

    # 2. Must be Confidence.UNKNOWN
    assert est.confidence == Confidence.UNKNOWN

    # 3. missing_components must be non-empty
    assert len(est.missing_components) > 0
    assert "template_profile_unoverridden" in est.missing_components

    # 4. Warnings must contain prominent PARTIAL ESTIMATE warning
    assert any("PARTIAL ESTIMATE" in w for w in est.warnings)
    assert any("MUST NOT be used as a complete" in w for w in est.warnings)


def test_complete_unverified_profile_is_not_partial(
    dummy_hardware: HardwareProfile,
) -> None:
    """Verify that an unverified profile with complete fields is NOT partial."""
    profile = BackendProfile(
        schema_version="0.1",
        profile_id="community-vllm-0.6.0",
        backend_id="vllm",
        display_name="Community vLLM 0.6.0",
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
                evidence_id="e1",
                source_type="community_benchmark",
                source="github",
            )
        ],
        status=ProfileStatus.UNVERIFIED,
        confidence=Confidence.UNKNOWN,
    )

    result = estimate_runtime_overhead(
        backend=profile,
        hardware=dummy_hardware,
        resident_weight_bytes=4 * 1024**3,
        parameter_count=7_000_000_000,
        graph_capture_enabled=True,
    )

    assert result.is_partial is False
    assert result.missing_components == []
    assert result.confidence == Confidence.UNKNOWN
    assert any("unverified" in warning.lower() for warning in result.warnings)
