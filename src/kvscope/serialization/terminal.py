"""Terminal formatting for KVScope hardware budget and runtime overhead estimates."""

from kvscope.domain.memory_budget import HardwareMemoryBudget
from kvscope.domain.ranges import ByteRange
from kvscope.domain.runtime_overhead import RuntimeOverheadEstimate
from kvscope.domain.units import bytes_to_gib


def _format_byte_range(br: ByteRange) -> str:
    if br.is_exact:
        return f"{br.expected_bytes} B ({bytes_to_gib(br.expected_bytes):.2f} GiB)"
    return (
        f"{br.expected_bytes} B ({bytes_to_gib(br.expected_bytes):.2f} GiB) "
        f"[range: {br.lower_bytes} B .. {br.upper_bytes} B]"
    )


def format_budget_terminal(budget: HardwareMemoryBudget) -> str:
    """Render a HardwareMemoryBudget as plain text formatted for terminal display."""
    tot_gib = bytes_to_gib(budget.physical_total_bytes)
    tot_str = f"{budget.physical_total_bytes} B ({tot_gib:.2f} GiB)"
    lines: list[str] = [
        "=== KVScope Hardware Memory Budget ===",
        f"Memory Topology:               {budget.memory_topology.value}",
        f"Physical Total Memory:         {tot_str}",
        f"Confidence Level:              {budget.confidence.value}",
        "",
        "--- Non-Model Reserves Breakdown ---",
        f"OS Reserve:                    {_format_byte_range(budget.os_reserve)}",
        f"Display Reserve:               {_format_byte_range(budget.display_reserve)}",
        f"Background Process Reserve:    "
        f"{_format_byte_range(budget.background_process_reserve)}",
        f"Device-Specific Reserve:       "
        f"{_format_byte_range(budget.device_specific_reserve)}",
        f"User Reserve:                  {_format_byte_range(budget.user_reserve)}",
        f"Total Non-Model Reserve:       "
        f"{_format_byte_range(budget.total_non_model_reserve)}",
        "",
        "--- Allocatable Memory Budget ---",
        f"Allocatable (Before Headroom): "
        f"{_format_byte_range(budget.allocatable_before_headroom)}",
        f"Recommended Headroom:          "
        f"{_format_byte_range(budget.recommended_headroom)}",
        f"Recommended Allocatable Range: "
        f"{_format_byte_range(budget.recommended_allocatable)}",
    ]

    if budget.assumptions:
        lines.append("")
        lines.append("Assumptions:")
        for item in budget.assumptions:
            lines.append(f"  - {item}")

    if budget.warnings:
        lines.append("")
        lines.append("Warnings:")
        for item in budget.warnings:
            lines.append(f"  - [WARNING] {item}")

    return "\n".join(lines)


def format_overhead_terminal(overhead: RuntimeOverheadEstimate) -> str:
    """Render a RuntimeOverheadEstimate as plain text formatted for terminal display."""
    ver_str = overhead.backend_version_specifier or "N/A"
    sub_str = _format_byte_range(overhead.subtotal_before_allocator_margin)
    lines: list[str] = [
        "=== KVScope Runtime Overhead Estimate ===",
        f"Backend Profile ID:            {overhead.backend_profile_id}",
        f"Version Specifier:             {ver_str}",
        f"Hardware Profile ID:           {overhead.hardware_profile_id}",
        f"Confidence Level:              {overhead.confidence.value}",
        "",
        "--- Runtime Overhead Breakdown ---",
        f"Base Runtime:                  {_format_byte_range(overhead.base_runtime)}",
        f"Parameter-Scaled Overhead:     "
        f"{_format_byte_range(overhead.parameter_scaled_overhead)}",
        f"Workspace (Resident Weights):  {_format_byte_range(overhead.workspace)}",
        f"Graph Capture Reserve:         {_format_byte_range(overhead.graph_capture)}",
        f"Backend Buffers:               "
        f"{_format_byte_range(overhead.backend_buffers)}",
        f"Subtotal (Before Allocator):   {sub_str}",
        f"Allocator Margin:              "
        f"{_format_byte_range(overhead.allocator_margin)}",
        f"Total Runtime Overhead:        "
        f"{_format_byte_range(overhead.total_runtime_overhead)}",
    ]

    if overhead.assumptions:
        lines.append("")
        lines.append("Assumptions:")
        for item in overhead.assumptions:
            lines.append(f"  - {item}")

    if overhead.warnings:
        lines.append("")
        lines.append("Warnings:")
        for item in overhead.warnings:
            lines.append(f"  - [WARNING] {item}")

    return "\n".join(lines)
