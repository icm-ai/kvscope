"""Serialization of Phase 10b local runner, fit, and review artifacts."""

import json
from typing import Any

from pydantic import BaseModel

from kvscope.calibration.schema import (
    CalibrationProfileCandidate,
    CalibrationReviewDecision,
    CalibrationRunResult,
)
from kvscope.domain.ranges import ByteRange
from kvscope.domain.units import bytes_to_gib


def _serialize(model: BaseModel, *, kind: str, indent: int) -> str:
    """Serialize one frozen artifact with a stable kind discriminator."""
    data: dict[str, Any] = json.loads(model.model_dump_json())
    data["kind"] = kind
    return json.dumps(data, ensure_ascii=False, indent=indent)


def serialize_calibration_run_json(
    result: CalibrationRunResult, indent: int = 2
) -> str:
    """Serialize a local runner result as JSON facts."""
    return _serialize(result, kind="calibration_run_result", indent=indent)


def serialize_calibration_profile_candidate_json(
    candidate: CalibrationProfileCandidate, indent: int = 2
) -> str:
    """Serialize a review-only empirical candidate as JSON facts."""
    return _serialize(candidate, kind="calibration_profile_candidate", indent=indent)


def serialize_calibration_review_json(
    review: CalibrationReviewDecision, indent: int = 2
) -> str:
    """Serialize a human review artifact as JSON facts."""
    return _serialize(review, kind="calibration_review_decision", indent=indent)


def _format_range(value: ByteRange) -> str:
    """Format an empirical byte reserve range for human output."""
    return (
        f"{value.expected_bytes} B ({bytes_to_gib(value.expected_bytes):.2f} GiB) "
        f"[range: {value.lower_bytes} B .. {value.upper_bytes} B]"
    )


def format_calibration_run_terminal(result: CalibrationRunResult) -> str:
    """Render a local runner result without exposing command output."""
    lines = [
        "=== KVScope Calibration Local Run ===",
        f"Run ID:                         {result.run_id}",
        f"Successful Samples:             {len(result.successful_measurements)}",
        f"Failed Samples:                 {len(result.failures)}",
        f"Selected Measurement:            {result.selected_measurement_id or 'N/A'}",
        "Conservative Peak Memory:       "
        f"{result.conservative_peak_memory_bytes or 'N/A'} B",
        f"Command SHA-256:                 {result.command_digest}",
    ]
    if result.failures:
        lines.extend(["", "Failures:"])
        lines.extend(
            f"  - sample {item.sample_index}: {item.code}" for item in result.failures
        )
    if result.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"  - [WARNING] {item}" for item in result.warnings)
    return "\n".join(lines)


def format_calibration_candidate_terminal(
    candidate: CalibrationProfileCandidate,
) -> str:
    """Render a review-only empirical candidate for a terminal."""
    lines = [
        "=== KVScope Calibration Profile Candidate ===",
        f"Candidate ID:                    {candidate.candidate_id}",
        f"Status:                          {candidate.status.value.upper()}",
        f"Sample Count:                    {candidate.sample_count}",
        f"Backend Profile:                 {candidate.scope.backend_profile_id}",
        f"Hardware Profile:                {candidate.scope.hardware_profile_id}",
        "Additional Reserve:              "
        f"{_format_range(candidate.additional_reserve_bytes)}",
        f"Confidence:                      {candidate.confidence.value.upper()}",
    ]
    if candidate.warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"  - [WARNING] {item}" for item in candidate.warnings)
    return "\n".join(lines)


def format_calibration_review_terminal(review: CalibrationReviewDecision) -> str:
    """Render a human review decision for a terminal."""
    return "\n".join(
        [
            "=== KVScope Calibration Review ===",
            f"Review ID:                      {review.review_id}",
            f"Candidate ID:                   {review.candidate_id}",
            f"Reviewer:                       {review.reviewer_id}",
            f"Decision:                       {review.status.value.upper()}",
            f"Candidate SHA-256:              {review.candidate_digest}",
            f"Notes:                          {review.notes}",
        ]
    )


def serialize_calibration_run_markdown(result: CalibrationRunResult) -> str:
    """Render a local runner result as Markdown."""
    lines = [
        "# KVScope Calibration Local Run",
        "",
        f"- **Run ID**: `{result.run_id}`",
        f"- **Successful samples**: `{len(result.successful_measurements)}`",
        f"- **Failed samples**: `{len(result.failures)}`",
        f"- **Selected measurement**: `{result.selected_measurement_id or 'N/A'}`",
        "- **Conservative peak**: "
        f"`{result.conservative_peak_memory_bytes or 'N/A'}` B",
    ]
    if result.failures:
        lines.extend(["", "## Failures", ""])
        lines.extend(
            f"- Sample `{item.sample_index}`: `{item.code}`" for item in result.failures
        )
    return "\n".join(lines)


def serialize_calibration_candidate_markdown(
    candidate: CalibrationProfileCandidate,
) -> str:
    """Render a review-only empirical candidate as Markdown."""
    reserve = candidate.additional_reserve_bytes
    return "\n".join(
        [
            "# KVScope Calibration Profile Candidate",
            "",
            f"- **Candidate ID**: `{candidate.candidate_id}`",
            f"- **Status**: `{candidate.status.value}`",
            f"- **Scope**: `{candidate.scope.backend_profile_id}` on "
            f"`{candidate.scope.hardware_profile_id}`",
            f"- **Samples**: `{candidate.sample_count}`",
            f"- **Additional reserve (lower/expected/upper)**: "
            f"`{reserve.lower_bytes}` / `{reserve.expected_bytes}` / "
            f"`{reserve.upper_bytes}` B",
            "",
            "> [!WARNING]",
            "> This is a review-only scoped candidate and does not alter a "
            "backend profile.",
        ]
    )


def serialize_calibration_review_markdown(review: CalibrationReviewDecision) -> str:
    """Render a human review decision as Markdown."""
    return "\n".join(
        [
            "# KVScope Calibration Review",
            "",
            f"- **Review ID**: `{review.review_id}`",
            f"- **Candidate ID**: `{review.candidate_id}`",
            f"- **Reviewer**: `{review.reviewer_id}`",
            f"- **Decision**: `{review.status.value}`",
            f"- **Candidate digest**: `{review.candidate_digest}`",
            "",
            review.notes,
        ]
    )
