"""Serialization of versioned offline calibration comparisons."""

from decimal import Decimal

from kvscope.calibration.artifacts import COMPARISON, serialize_artifact_json
from kvscope.calibration.schema import CalibrationComparison
from kvscope.domain.ranges import ByteRange
from kvscope.domain.signed_ranges import SignedByteRange
from kvscope.domain.units import BYTES_PER_GIB, bytes_to_gib


def serialize_calibration_comparison_json(
    comparison: CalibrationComparison, indent: int = 2
) -> str:
    """Serialize a calibration comparison as versioned JSON facts."""
    return serialize_artifact_json(comparison, COMPARISON, indent)


def _format_range(memory: ByteRange) -> str:
    """Format a byte range with its expected GiB value."""
    return (
        f"{memory.expected_bytes} B ({bytes_to_gib(memory.expected_bytes):.2f} GiB) "
        f"[range: {memory.lower_bytes} B .. {memory.upper_bytes} B]"
    )


def _format_signed_range(memory: SignedByteRange) -> str:
    """Format a signed byte range without losing negative values."""
    expected_gib = Decimal(memory.expected_bytes) / BYTES_PER_GIB
    return (
        f"{memory.expected_bytes} B ({expected_gib:.2f} GiB) "
        f"[range: {memory.lower_bytes} B .. {memory.upper_bytes} B]"
    )


def format_calibration_comparison_terminal(comparison: CalibrationComparison) -> str:
    """Render a calibration comparison as terminal text."""
    lines = [
        "=== KVScope Calibration Comparison ===",
        f"Status:                         {comparison.status.value.upper()}",
        f"Measurement Record ID:          {comparison.measurement_record_id}",
        f"Confidence Level:               {comparison.confidence.value.upper()}",
        "Identity Verification:          "
        f"{comparison.identity_verification.value.upper()}",
        f"Observed Peak Memory:           {comparison.observed_peak_memory_bytes} B",
    ]
    if comparison.predicted_total_requirement is None:
        lines.append("Predicted Total Requirement:    UNAVAILABLE — INCOMPLETE REPORT")
    else:
        signed_error = comparison.signed_error
        lines.extend(
            [
                "",
                "--- Prediction vs Observation ---",
                "Predicted Total Requirement:    "
                f"{_format_range(comparison.predicted_total_requirement)}",
                "Observed Within Prediction:     "
                f"{comparison.observed_within_predicted_range}",
                f"Observed - Lower:               {comparison.delta_vs_lower_bytes} B",
                "Observed - Expected:            "
                f"{comparison.delta_vs_expected_bytes} B",
                f"Observed - Upper:               {comparison.delta_vs_upper_bytes} B",
            ]
        )
        if signed_error is not None:
            lines.append(
                f"Signed Error Interval:          {_format_signed_range(signed_error)}"
            )
        if comparison.relative_error_vs_expected is not None:
            ratio = comparison.relative_error_vs_expected
            lines.append(
                "Relative Error vs Expected:     "
                f"{ratio.numerator_bytes}/{ratio.denominator_bytes}"
            )

    if comparison.identity_mismatches:
        lines.extend(["", "Identity Mismatches:"])
        lines.extend(
            f"  - [MISMATCH] {item}" for item in comparison.identity_mismatches
        )
    if comparison.assumptions:
        lines.extend(["", "Assumptions:"])
        lines.extend(f"  - {item}" for item in comparison.assumptions)
    if comparison.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"  - [WARNING] {item}" for item in comparison.warnings)
    if comparison.evidence:
        lines.extend(["", "Evidence:"])
        lines.extend(
            f"  - [{item.evidence_id}] {item.source} (type: {item.source_type})"
            for item in comparison.evidence
        )
    return "\n".join(lines)


def serialize_calibration_comparison_markdown(
    comparison: CalibrationComparison,
) -> str:
    """Render a calibration comparison as Markdown."""
    lines = [
        "# KVScope Calibration Comparison",
        "",
        f"- **Status**: `{comparison.status.value}`",
        f"- **Measurement record**: `{comparison.measurement_record_id}`",
        f"- **Confidence**: `{comparison.confidence.value}`",
        f"- **Identity verification**: `{comparison.identity_verification.value}`",
        f"- **Observed peak memory**: `{comparison.observed_peak_memory_bytes}` B",
        "",
    ]
    if comparison.predicted_total_requirement is None:
        lines.extend(
            [
                "> [!WARNING]",
                "> The source report is incomplete; no total-memory error conclusion "
                "was made.",
            ]
        )
    else:
        prediction = comparison.predicted_total_requirement
        lines.extend(
            [
                "## Prediction vs Observation",
                "",
                "| Metric | Bytes |",
                "| :--- | ---: |",
                f"| Predicted lower | `{prediction.lower_bytes}` |",
                f"| Predicted expected | `{prediction.expected_bytes}` |",
                f"| Predicted upper | `{prediction.upper_bytes}` |",
                f"| Observed peak | `{comparison.observed_peak_memory_bytes}` |",
                "| Observed within interval | "
                f"`{comparison.observed_within_predicted_range}` |",
                f"| Observed - lower | `{comparison.delta_vs_lower_bytes}` |",
                f"| Observed - expected | `{comparison.delta_vs_expected_bytes}` |",
                f"| Observed - upper | `{comparison.delta_vs_upper_bytes}` |",
            ]
        )
        if comparison.relative_error_vs_expected is not None:
            ratio = comparison.relative_error_vs_expected
            lines.append(
                "| Relative error vs expected (exact) | "
                f"`{ratio.numerator_bytes}/{ratio.denominator_bytes}` |"
            )

    if comparison.identity_mismatches:
        lines.extend(["", "## Identity Mismatches", ""])
        lines.extend(f"- {item}" for item in comparison.identity_mismatches)
    if comparison.assumptions:
        lines.extend(["", "## Assumptions", ""])
        lines.extend(f"- {item}" for item in comparison.assumptions)
    if comparison.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"> [!WARNING]\n> {item}" for item in comparison.warnings)
    if comparison.evidence:
        lines.extend(["", "## Evidence", ""])
        lines.extend(
            f"- **[{item.evidence_id}]** {item.source} _(Type: {item.source_type})_"
            for item in comparison.evidence
        )
    return "\n".join(lines)
