"""Markdown serialization for KVScope estimates and budget reports."""

from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.ranges import ByteRange
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate
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
