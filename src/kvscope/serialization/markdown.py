"""Markdown serialization for KVScope estimates and budget reports."""

from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.ranges import ByteRange
from kvscope.domain.report import MemoryFeasibilityReport
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate
from kvscope.domain.signed_ranges import SignedByteRange
from kvscope.domain.units import bytes_to_gib


def _md_range(br: ByteRange) -> str:
    exp_gib = bytes_to_gib(br.expected_bytes)
    if br.is_exact:
        return f"`{br.expected_bytes}` B ({exp_gib:.2f} GiB)"
    low_gib = bytes_to_gib(br.lower_bytes)
    up_gib = bytes_to_gib(br.upper_bytes)
    return f"`{br.expected_bytes}` B ({exp_gib:.2f} GiB) _[{low_gib:.2f}-{up_gib:.2f}]_"


def _row(name: str, br: ByteRange, is_bold: bool = False) -> str:
    l_g = bytes_to_gib(br.lower_bytes)
    e_g = bytes_to_gib(br.expected_bytes)
    u_g = bytes_to_gib(br.upper_bytes)
    exp_b = br.expected_bytes
    if is_bold:
        b_name = f"**{name}**"
        return (
            f"| {b_name} | **{l_g:.2f}** | **{e_g:.2f}** | **{u_g:.2f}** | `{exp_b}` |"
        )
    return f"| {name} | {l_g:.2f} | {e_g:.2f} | {u_g:.2f} | `{exp_b}` |"


def _sbr_row(name: str, sbr: SignedByteRange) -> str:
    l_g = bytes_to_gib(sbr.lower_bytes)
    e_g = bytes_to_gib(sbr.expected_bytes)
    u_g = bytes_to_gib(sbr.upper_bytes)
    exp_b = sbr.expected_bytes
    return f"| {name} | {l_g:.2f} | {e_g:.2f} | {u_g:.2f} | `{exp_b}` |"


def serialize_budget_to_markdown(budget: HardwareMemoryBudget) -> str:
    """Serialize HardwareMemoryBudget to Markdown format."""
    tot_gib = bytes_to_gib(budget.physical_total_bytes)
    tot_str = f"`{budget.physical_total_bytes}` B ({tot_gib:.2f} GiB)"
    alloc_str = _md_range(budget.allocatable_before_headroom)
    lines: list[str] = [
        "# KVScope Hardware Memory Budget Report",
        "",
        f"- **Memory Topology**: `{budget.memory_topology.value}`",
        f"- **Physical Total Memory**: {tot_str}",
        f"- **Confidence**: `{budget.confidence.value}`",
        "",
        "## Non-Model Reserves Breakdown",
        "",
        "| Component | Lower (GiB) | Expected (GiB) | Upper (GiB) | Bytes (Expected) |",
        "| :--- | :--- | :--- | :--- | :--- |",
        _row("OS Reserve", budget.os_reserve),
        _row("Display Reserve", budget.display_reserve),
        _row("Background Process Reserve", budget.background_process_reserve),
        _row("Device-Specific Reserve", budget.device_specific_reserve),
        _row("User Reserve", budget.user_reserve),
        _row("Total Non-Model Reserve", budget.total_non_model_reserve, is_bold=True),
        "",
        "## Allocatable Memory Summary",
        "",
        f"- **Allocatable (Before Headroom)**: {alloc_str}",
        f"- **Recommended Headroom**: {_md_range(budget.recommended_headroom)}",
        f"- **Recommended Allocatable**: {_md_range(budget.recommended_allocatable)}",
    ]

    if budget.warnings:
        lines.append("")
        lines.append("### Warnings")
        lines.append("")
        for w in budget.warnings:
            lines.append(f"> [!WARNING]\n> {w}")

    return "\n".join(lines)


def serialize_overhead_to_markdown(estimate: RuntimeOverheadEstimate) -> str:
    """Serialize RuntimeOverheadEstimate to Markdown format."""
    ver_str = estimate.backend_version_specifier or "N/A"
    lines: list[str] = [
        "# KVScope Runtime Overhead Report",
        "",
        f"- **Backend Profile**: `{estimate.backend_profile_id}` ({ver_str})",
        f"- **Hardware Profile**: `{estimate.hardware_profile_id}`",
        f"- **Confidence**: `{estimate.confidence.value}`",
        "",
        "## Runtime Overhead Component Breakdown",
        "",
        "| Component | Lower (GiB) | Expected (GiB) | Upper (GiB) | Bytes (Expected) |",
        "| :--- | :--- | :--- | :--- | :--- |",
        _row("Base Runtime", estimate.base_runtime),
        _row("Parameter-Scaled Overhead", estimate.parameter_scaled_overhead),
        _row("Workspace (Resident Weights)", estimate.workspace),
        _row("Graph Capture Reserve", estimate.graph_capture),
        _row("Backend Buffers", estimate.backend_buffers),
        _row(
            "Subtotal (Before Margin)",
            estimate.subtotal_before_allocator_margin,
            is_bold=True,
        ),
        _row("Allocator Margin", estimate.allocator_margin),
        _row("Total Runtime Overhead", estimate.total_runtime_overhead, is_bold=True),
    ]

    if estimate.warnings:
        lines.append("")
        lines.append("### Warnings")
        lines.append("")
        for w in estimate.warnings:
            lines.append(f"> [!WARNING]\n> {w}")

    return "\n".join(lines)


def serialize_feasibility_report_markdown(report: MemoryFeasibilityReport) -> str:
    """Serialize MemoryFeasibilityReport to Markdown format."""
    agg = report.aggregation
    feas = report.feasibility
    con = report.constraint_analysis

    lines: list[str] = [
        "# KVScope Memory Feasibility Report",
        "",
        f"- **Product Status**: `{feas.product_status.value.upper()}`",
        f"- **Internal Status**: `{feas.internal_status.value}`",
        f"- **Confidence**: `{feas.confidence.value.upper()}`",
        f"- **Primary Boundary**: `{feas.primary_boundary or 'N/A'}`",
        f"- **Explanation**: {feas.explanation}",
        "",
    ]

    if agg.is_partial:
        lines.extend(
            [
                "> [!WARNING]",
                "> **Partial Estimate**: Memory requirement calculation is incomplete.",
                f"> Missing components: `{agg.missing_components}`",
                "",
            ]
        )

    header_row = (
        "| Component | Lower (GiB) | Expected (GiB) | Upper (GiB) | Bytes (Expected) |"
    )
    sep_row = "| :--- | :--- | :--- | :--- | :--- |"

    lines.extend(
        [
            "## Memory Requirement Breakdown",
            "",
            header_row,
            sep_row,
            _row("Resident Weights", agg.resident_weights.memory),
            _row("Allocated KV Cache", agg.kv_cache.memory),
            _row("Runtime Overhead", agg.runtime_overhead.memory),
            _row("Known Subtotal", agg.known_subtotal, is_bold=True),
        ]
    )

    if not agg.is_partial and agg.total_requirement is not None:
        lines.append(_row("Total Requirement", agg.total_requirement, is_bold=True))

    tot_gib = bytes_to_gib(feas.physical_total_bytes)
    tot_row = (
        f"| Physical Total Memory | {tot_gib:.2f} | {tot_gib:.2f} | "
        f"{tot_gib:.2f} | `{feas.physical_total_bytes}` |"
    )
    budget_header_row = (
        "| Budget Tier | Lower (GiB) | Expected (GiB) | Upper (GiB) | Bytes |"
    )
    lines.extend(
        [
            "",
            "## Hardware Memory Budget",
            "",
            budget_header_row,
            sep_row,
            tot_row,
            _row("Allocatable (Before Headroom)", feas.allocatable_before_headroom),
            _row("Recommended Allocatable", feas.recommended_allocatable, is_bold=True),
        ]
    )

    boundary_header_row = (
        "| Boundary Level | Lower (GiB) | Expected (GiB) | Upper (GiB) | Bytes |"
    )
    lines.extend(
        [
            "",
            "## Memory Headroom / Deficit Range",
            "",
            boundary_header_row,
            sep_row,
        ]
    )
    if feas.headroom_vs_physical is not None:
        lines.append(_sbr_row("Versus Physical Memory", feas.headroom_vs_physical))
    if feas.headroom_vs_allocatable is not None:
        lines.append(
            _sbr_row("Versus Allocatable Budget", feas.headroom_vs_allocatable)
        )
    if feas.headroom_vs_recommended is not None:
        lines.append(
            _sbr_row("Versus Recommended Budget", feas.headroom_vs_recommended)
        )

    lines.extend(
        [
            "",
            "## Identified Constraints",
            "",
        ]
    )
    if not con.constraints:
        lines.append("_No active risk constraints identified._")
    else:
        lines.extend(
            [
                "| Severity | Code | Component | Explanation |",
                "| :--- | :--- | :--- | :--- |",
            ]
        )
        for c in con.constraints:
            comp_str = c.component or "N/A"
            c_sev = c.severity.value.upper()
            lines.append(f"| `{c_sev}` | `{c.code}` | `{comp_str}` | {c.explanation} |")

    if feas.warnings:
        lines.extend(["", "### Warnings", ""])
        for w in feas.warnings:
            lines.append(f"> [!WARNING]\n> {w}")

    if feas.evidence:
        lines.extend(["", "### Evidence", ""])
        for ev in feas.evidence:
            lines.append(
                f"- **[{ev.evidence_id}]** {ev.source} _(Type: {ev.source_type})_"
            )

    return "\n".join(lines)
