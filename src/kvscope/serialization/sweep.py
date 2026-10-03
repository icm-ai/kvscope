"""Serialization and presentation for workload sensitivity sweeps."""

import json
from typing import Any

from kvscope.domain.ranges import ByteRange
from kvscope.domain.signed_ranges import SignedByteRange
from kvscope.domain.sweep import WorkloadSweepReport
from kvscope.domain.units import bytes_to_gib
from kvscope.serialization.comparison import format_deployment_comparison_terminal
from kvscope.serialization.moe import format_moe_weight_analysis_markdown


def serialize_workload_sweep_json(report: WorkloadSweepReport, indent: int = 2) -> str:
    """Serialize sweep results as versioned JSON, including each comparison kind."""
    data: dict[str, Any] = json.loads(report.model_dump_json())
    data["kind"] = "workload_sweep"
    for point in data["points"]:
        comparison = point["comparison"]
        comparison["kind"] = "deployment_comparison"
    return json.dumps(data, ensure_ascii=False, indent=indent)


def _format_range(value: ByteRange | SignedByteRange | None) -> str:
    if value is None:
        return "unknown"
    expected_gib = bytes_to_gib(abs(value.expected_bytes))
    if value.expected_bytes < 0:
        expected_gib = -expected_gib
    return (
        f"{value.expected_bytes} B ({expected_gib:.2f} GiB) "
        f"[{value.lower_bytes} B .. {value.upper_bytes} B]"
    )


def format_workload_sweep_terminal(report: WorkloadSweepReport) -> str:
    """Render each ordered sweep point followed by its target comparison."""
    lines = [
        "=== KVScope Workload Sensitivity Sweep ===",
        f"Model: {report.model_id} ({report.parameter_count} parameters)",
        f"Dimension: {report.dimension.value}",
        "",
    ]
    for point in report.points:
        lines.append(f"--- {report.dimension.value}={point.value} ---")
        lines.append(format_deployment_comparison_terminal(point.comparison))
        lines.append("")
    lines.append("Observed feasibility transitions (sampled brackets only):")
    if report.transitions:
        for transition in report.transitions:
            lines.append(
                f"  {transition.target_id}: {transition.from_value} -> "
                f"{transition.to_value} ({transition.from_status.value} -> "
                f"{transition.to_status.value})"
            )
    else:
        lines.append("  No status transitions observed across sampled points.")
    lines.append("  Exact boundaries are unknown; no interpolation is performed.")
    return "\n".join(lines).rstrip()


def serialize_workload_sweep_markdown(report: WorkloadSweepReport) -> str:
    """Render a compact table of feasibility and memory margins per sweep point."""
    lines = [
        "# KVScope Workload Sensitivity Sweep",
        "",
        f"- Model: `{report.model_id}`",
        f"- Parameter count: {report.parameter_count}",
        f"- Swept dimension: `{report.dimension.value}`",
        "",
    ]
    moe_analysis = report.points[0].comparison.targets[0].report.moe_weight_analysis
    if moe_analysis is not None:
        lines.extend([format_moe_weight_analysis_markdown(moe_analysis), ""])
    lines.extend(
        [
            f"| {report.dimension.value} | Target | Hardware | Backend (version) | "
            "Feasibility | Confidence | Requirement | Recommended headroom | "
            "Primary constraint |",
            "|---:|---|---|---|---|---|---:|---:|---|---|",
        ]
    )
    for point in report.points:
        for target in point.comparison.targets:
            feasibility = target.report.feasibility
            primary = target.report.constraint_analysis.primary_constraint
            constraint = (
                f"`{primary.code}` {primary.title}" if primary is not None else "—"
            )
            lines.append(
                f"| {point.value} | `{target.target_id}` | "
                f"`{target.hardware_profile_id}` | "
                f"`{target.backend_profile_id}` "
                f"({target.backend_version or 'unspecified'}) | "
                f"{feasibility.product_status.value} | "
                f"{feasibility.confidence.value} | "
                f"{_format_range(feasibility.requirement)} | "
                f"{_format_range(feasibility.headroom_vs_recommended)} | "
                f"{constraint} |"
            )
    lines.extend(
        [
            "",
            "Only the selected workload dimension varies; model, targets, and "
            "other inference settings remain fixed. Values and targets retain "
            "their input order.",
            "",
            "## Observed feasibility transitions",
            "",
            "Transitions bracket adjacent supplied samples only; exact boundaries "
            "are unknown and are not interpolated.",
            "",
            "| Target | From value | To value | From status | To status |",
            "|---|---:|---:|---|---|",
        ]
    )
    if report.transitions:
        for transition in report.transitions:
            lines.append(
                f"| `{transition.target_id}` | {transition.from_value} | "
                f"{transition.to_value} | {transition.from_status.value} | "
                f"{transition.to_status.value} |"
            )
    else:
        lines.append("| — | — | — | No changes observed | — |")
    return "\n".join(lines)
