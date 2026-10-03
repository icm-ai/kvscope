"""Serialization and presentation for deployment-target comparisons."""

import json
from typing import Any

from kvscope.domain.comparison import DeploymentComparisonReport
from kvscope.domain.ranges import ByteRange
from kvscope.domain.signed_ranges import SignedByteRange
from kvscope.domain.units import bytes_to_gib
from kvscope.serialization.moe import (
    format_moe_weight_analysis_markdown,
    format_moe_weight_analysis_terminal,
)


def serialize_deployment_comparison_json(
    report: DeploymentComparisonReport, indent: int = 2
) -> str:
    """Serialize a deployment comparison as its versioned JSON fact source."""
    data: dict[str, Any] = json.loads(report.model_dump_json())
    data["kind"] = "deployment_comparison"
    return json.dumps(data, ensure_ascii=False, indent=indent)


def _format_range(value: ByteRange | SignedByteRange | None) -> str:
    if value is None:
        return "unknown"
    lower = value.lower_bytes
    expected = value.expected_bytes
    upper = value.upper_bytes
    expected_gib = bytes_to_gib(abs(expected))
    if expected < 0:
        expected_gib = -expected_gib
    return (
        f"{expected} B ({expected_gib:.2f} GiB) "
        f"[{lower} B .. {upper} B]"
    )


def format_deployment_comparison_terminal(
    report: DeploymentComparisonReport,
) -> str:
    """Render a compact terminal summary while preserving explicit input order."""
    lines = [
        "=== KVScope Deployment Target Comparison ===",
        f"Model: {report.model_id} ({report.parameter_count} parameters)",
        f"Workload: context={report.inference_config.context_length}, "
        f"batch={report.inference_config.batch_size}, "
        f"active_sequences={report.inference_config.active_sequences}, "
        f"weight_dtype={report.inference_config.weight_dtype.value}, "
        f"kv_dtype={report.inference_config.kv_dtype.value}",
        "",
    ]
    moe_analysis = report.targets[0].report.moe_weight_analysis
    if moe_analysis is not None:
        lines.extend([format_moe_weight_analysis_terminal(moe_analysis), ""])
    for result in report.targets:
        feasibility = result.report.feasibility
        requirement = _format_range(feasibility.requirement)
        headroom = _format_range(feasibility.headroom_vs_recommended)
        lines.extend(
            [
                f"[{result.target_id}] {feasibility.product_status.value.upper()}",
                f"  Hardware: {result.hardware_profile_id}",
                f"  Backend: {result.backend_profile_id}"
                f" ({result.backend_version or 'version unspecified'})",
                f"  Confidence: {feasibility.confidence.value}",
                f"  Total requirement: {requirement}",
                f"  Headroom vs recommended: {headroom}",
            ]
        )
        primary = result.report.constraint_analysis.primary_constraint
        if primary is not None:
            lines.append(f"  Primary constraint: {primary.code} — {primary.title}")
        lines.append("")
    lines.append(
        "Results retain the supplied target order; overlapping uncertainty ranges "
        "are not used to claim a single best target."
    )
    return "\n".join(lines)


def serialize_deployment_comparison_markdown(
    report: DeploymentComparisonReport,
) -> str:
    """Render a Markdown comparison table plus per-target constraint notes."""
    lines = [
        "# KVScope Deployment Target Comparison",
        "",
        f"- Model: `{report.model_id}`",
        f"- Parameter count: {report.parameter_count}",
        f"- Context length: {report.inference_config.context_length}",
        f"- Batch size: {report.inference_config.batch_size}",
        f"- Active sequences: {report.inference_config.active_sequences}",
        f"- Weight dtype: `{report.inference_config.weight_dtype.value}`",
        f"- KV dtype: `{report.inference_config.kv_dtype.value}`",
        "",
    ]
    moe_analysis = report.targets[0].report.moe_weight_analysis
    if moe_analysis is not None:
        lines.extend([format_moe_weight_analysis_markdown(moe_analysis), ""])
    lines.extend(
        [
            "| Target | Hardware | Backend (version) | Feasibility | Confidence | "
            "Requirement | Recommended headroom | Primary constraint |",
            "|---|---|---|---|---|---:|---:|---|",
        ]
    )
    for result in report.targets:
        feasibility = result.report.feasibility
        primary = result.report.constraint_analysis.primary_constraint
        constraint = (
            f"`{primary.code}` {primary.title}" if primary is not None else "—"
        )
        lines.append(
            f"| `{result.target_id}` | `{result.hardware_profile_id}` | "
            f"`{result.backend_profile_id}` "
            f"({result.backend_version or 'unspecified'}) | "
            f"{feasibility.product_status.value} | "
            f"{feasibility.confidence.value} | "
            f"{_format_range(feasibility.requirement)} | "
            f"{_format_range(feasibility.headroom_vs_recommended)} | "
            f"{constraint} |"
        )
    lines.extend(
        [
            "",
            "Targets are shown in the order supplied. Uncertainty intervals are "
            "preserved; no single winner is inferred when ranges overlap.",
        ]
    )
    return "\n".join(lines)
