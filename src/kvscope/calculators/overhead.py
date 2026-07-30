"""Runtime Overhead Engine for KVScope."""

from kvscope.domain.backend import BackendProfile
from kvscope.domain.enums import Confidence, MemoryTopology, ProfileStatus
from kvscope.domain.evidence import Evidence
from kvscope.domain.hardware import HardwareProfile
from kvscope.domain.ranges import (
    ByteRange,
    add_byte_ranges,
    ceil_div,
    multiply_bytes_by_ratio_range,
)
from kvscope.domain.runtime_overhead import (
    RuntimeOverheadEstimate,
    RuntimeOverheadOverrides,
)
from kvscope.errors import IncompleteBackendProfileError, RuntimeOverheadInputError

CONFIDENCE_RANKS: dict[Confidence, int] = {
    Confidence.EXACT: 5,
    Confidence.HIGH: 4,
    Confidence.MEDIUM: 3,
    Confidence.LOW: 2,
    Confidence.UNKNOWN: 1,
}

RANK_TO_CONFIDENCE: dict[int, Confidence] = {
    5: Confidence.EXACT,
    4: Confidence.HIGH,
    3: Confidence.MEDIUM,
    2: Confidence.LOW,
    1: Confidence.UNKNOWN,
}

ONE_BILLION = 1_000_000_000


def _downgrade_confidence(current: Confidence, steps: int = 1) -> Confidence:
    """Downgrade a confidence level by N steps."""
    rank = CONFIDENCE_RANKS.get(current, 1)
    new_rank = max(1, rank - steps)
    return RANK_TO_CONFIDENCE[new_rank]


def estimate_runtime_overhead(
    *,
    backend: BackendProfile,
    hardware: HardwareProfile,
    resident_weight_bytes: int,
    parameter_count: int | None = None,
    graph_capture_enabled: bool = False,
    user_overrides: RuntimeOverheadOverrides | None = None,
    allow_incomplete_profile: bool = False,
) -> RuntimeOverheadEstimate:
    """Calculate inference runtime overhead breakdown and total memory requirement."""
    if resident_weight_bytes < 0:
        raise RuntimeOverheadInputError(
            "resident_weight_bytes must be non-negative",
            field_name="resident_weight_bytes",
        )

    if parameter_count is not None and parameter_count < 0:
        raise RuntimeOverheadInputError(
            "parameter_count must be non-negative",
            field_name="parameter_count",
        )

    is_template = (
        any("template" in note.lower() for note in backend.notes)
        or "template" in backend.profile_id.lower()
        or "template" in backend.display_name.lower()
    )

    overrides = user_overrides or RuntimeOverheadOverrides()
    has_full_overrides = (
        overrides.base_runtime is not None
        and overrides.per_billion_parameters is not None
        and overrides.workspace_ratio is not None
        and overrides.graph_capture_reserve is not None
        and overrides.backend_buffers is not None
        and overrides.allocator_margin_ratio is not None
    )

    is_partial = is_template and not has_full_overrides
    missing_components: list[str] = (
        ["template_profile_unoverridden"] if is_partial else []
    )

    if is_partial and not allow_incomplete_profile and not has_full_overrides:
        err = (
            f"Backend profile '{backend.profile_id}' is a template profile. "
            "Set allow_incomplete_profile=True or supply full overrides."
        )
        raise IncompleteBackendProfileError(
            err,
            backend_id=backend.backend_id,
            profile_id=backend.profile_id,
        )

    if graph_capture_enabled and not backend.memory_model.graph_capture_supported:
        err = (
            f"Graph capture is requested but backend profile '{backend.profile_id}' "
            "does not support graph capture."
        )
        sug = (
            "Set graph_capture_enabled=False or use a backend profile with "
            "graph_capture_supported=True."
        )
        raise RuntimeOverheadInputError(
            err,
            field_name="graph_capture_enabled",
            suggestion=sug,
        )

    assumptions: list[str] = []
    warnings: list[str] = list(backend.notes)
    evidence: list[Evidence] = list(backend.evidence)

    if backend.status in {ProfileStatus.UNVERIFIED, ProfileStatus.EXPERIMENTAL}:
        warnings.append(
            f"Using unverified backend profile '{backend.profile_id}'. "
            "Benchmark validation is recommended."
        )

    if is_partial:
        missing_str = ", ".join(missing_components)
        warn = (
            f"PARTIAL ESTIMATE: Using generic template backend profile "
            f"'{backend.profile_id}' without full overrides. Missing components: "
            f"{missing_str}. This partial estimate MUST NOT be used as a complete "
            "feasibility bound."
        )
        warnings.append(warn)

    # 1. Base Runtime
    if overrides.base_runtime is not None:
        base_runtime = overrides.base_runtime
        assumptions.append(f"Base runtime overridden by user: {base_runtime}")
    else:
        base_runtime = backend.memory_model.base_runtime

    # 2. Parameter-scaled overhead
    per_billion = (
        overrides.per_billion_parameters
        if overrides.per_billion_parameters is not None
        else backend.memory_model.per_billion_parameters
    )

    if overrides.per_billion_parameters is not None:
        assumptions.append(
            f"Per-billion parameters overhead overridden by user: {per_billion}"
        )

    if parameter_count is not None:
        lower_p = ceil_div(parameter_count * per_billion.lower_bytes, ONE_BILLION)
        exp_p = ceil_div(parameter_count * per_billion.expected_bytes, ONE_BILLION)
        upper_p = ceil_div(parameter_count * per_billion.upper_bytes, ONE_BILLION)
        param_scaled = ByteRange(
            lower_bytes=lower_p, expected_bytes=exp_p, upper_bytes=upper_p
        )
    else:
        if per_billion.upper_bytes > 0:
            err = "parameter_count is required when per_billion overhead is non-zero."
            raise RuntimeOverheadInputError(
                err,
                field_name="parameter_count",
                suggestion="Pass parameter_count to estimate_runtime_overhead.",
            )
        param_scaled = ByteRange.exact(0)

    # 3. Workspace
    ws_ratio = (
        overrides.workspace_ratio
        if overrides.workspace_ratio is not None
        else backend.memory_model.workspace_ratio_of_resident_weights
    )

    if overrides.workspace_ratio is not None:
        assumptions.append(f"Workspace ratio overridden by user: {ws_ratio}")

    workspace = multiply_bytes_by_ratio_range(resident_weight_bytes, ws_ratio)

    # 4. Graph Capture
    if graph_capture_enabled:
        gc_reserve = (
            overrides.graph_capture_reserve
            if overrides.graph_capture_reserve is not None
            else backend.memory_model.graph_capture_reserve
        )
        if overrides.graph_capture_reserve is not None:
            assumptions.append(
                f"Graph capture reserve overridden by user: {gc_reserve}"
            )
        graph_capture = gc_reserve
    else:
        graph_capture = ByteRange.exact(0)

    # 5. Backend Buffers
    if overrides.backend_buffers is not None:
        backend_buffers = overrides.backend_buffers
        assumptions.append(f"Backend buffers overridden by user: {backend_buffers}")
    else:
        backend_buffers = backend.memory_model.backend_buffers

    # Subtotal
    subtotal = add_byte_ranges(
        base_runtime, param_scaled, workspace, graph_capture, backend_buffers
    )

    # 6. Allocator Margin
    margin_ratio = (
        overrides.allocator_margin_ratio
        if overrides.allocator_margin_ratio is not None
        else backend.memory_model.allocator_margin_ratio_of_subtotal
    )

    if overrides.allocator_margin_ratio is not None:
        assumptions.append(f"Allocator margin ratio overridden by user: {margin_ratio}")

    allocator_margin = multiply_bytes_by_ratio_range(subtotal, margin_ratio)

    # Total Overhead
    total_overhead = add_byte_ranges(subtotal, allocator_margin)

    # Confidence calculation
    if is_partial:
        calc_conf = Confidence.UNKNOWN
    else:
        b_conf = backend.confidence
        h_conf = hardware.confidence
        b_rank = CONFIDENCE_RANKS.get(b_conf, 1)
        h_rank = CONFIDENCE_RANKS.get(h_conf, 1)
        conf_rank = min(b_rank, h_rank)
        calc_conf = RANK_TO_CONFIDENCE[conf_rank]

        if hardware.memory_topology == MemoryTopology.UNIFIED:
            calc_conf = _downgrade_confidence(calc_conf, 1)
            warnings.append(
                "Unified memory topology reduces runtime overhead confidence."
            )

        if is_template or backend.status in {
            ProfileStatus.UNVERIFIED,
            ProfileStatus.EXPERIMENTAL,
        }:
            calc_conf = _downgrade_confidence(calc_conf, 1)

    return RuntimeOverheadEstimate(
        base_runtime=base_runtime,
        parameter_scaled_overhead=param_scaled,
        workspace=workspace,
        graph_capture=graph_capture,
        backend_buffers=backend_buffers,
        allocator_margin=allocator_margin,
        subtotal_before_allocator_margin=subtotal,
        total_runtime_overhead=total_overhead,
        backend_profile_id=backend.profile_id,
        backend_version_specifier=backend.version_specifier,
        hardware_profile_id=hardware.profile_id,
        confidence=calc_conf,
        is_partial=is_partial,
        missing_components=missing_components,
        assumptions=assumptions,
        warnings=warnings,
        evidence=evidence,
    )
