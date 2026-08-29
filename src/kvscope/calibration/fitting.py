"""Scoped empirical reserve fitting and human review artifacts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from kvscope.calibration.schema import (
    CalibrationCandidateScope,
    CalibrationCandidateStatus,
    CalibrationComparison,
    CalibrationComparisonStatus,
    CalibrationIdentityVerification,
    CalibrationProfileCandidate,
    CalibrationReviewDecision,
    CalibrationReviewStatus,
)
from kvscope.domain.enums import Confidence
from kvscope.domain.ranges import ByteRange
from kvscope.errors import CalibrationFitError


def _candidate_scope(comparison: CalibrationComparison) -> CalibrationCandidateScope:
    """Extract the exact workload scope from one verified comparison."""
    measurement = comparison.measurement
    if measurement.backend_version is None:
        raise CalibrationFitError("verified comparisons require backend_version")
    return CalibrationCandidateScope(
        backend_profile_id=measurement.backend_profile_id,
        backend_version=measurement.backend_version,
        hardware_profile_id=measurement.hardware_profile_id,
        model_id=measurement.model_id,
        model_revision=measurement.model_revision,
        model_config_digest=measurement.model_config_digest,
        inference_config=measurement.inference_config,
    )


def _scope_key(scope: CalibrationCandidateScope) -> str:
    """Create deterministic canonical scope JSON for equality and candidate IDs."""
    return json.dumps(scope.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)


def _candidate_digest(candidate: CalibrationProfileCandidate) -> str:
    """Hash stable candidate facts for review artifact binding."""
    payload = candidate.model_dump(mode="json", exclude={"candidate_id"})
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fit_calibration_comparisons(
    comparisons: list[CalibrationComparison],
    *,
    minimum_samples: int = 3,
) -> CalibrationProfileCandidate:
    """Create a non-generalized empirical reserve envelope from verified inputs.

    This deliberately does not infer backend formula coefficients. It scopes the
    resulting reserve to one exact backend, hardware, model, and inference setup.
    """
    if minimum_samples <= 0:
        raise CalibrationFitError("minimum_samples must be positive")
    if not comparisons:
        raise CalibrationFitError("at least one comparison is required for fitting")

    scopes: list[CalibrationCandidateScope] = []
    adjustments: list[int] = []
    record_ids: list[str] = []
    for comparison in comparisons:
        if comparison.status is not CalibrationComparisonStatus.COMPARABLE:
            raise CalibrationFitError(
                f"comparison {comparison.measurement_record_id} is not comparable"
            )
        if (
            comparison.identity_verification
            is not CalibrationIdentityVerification.VERIFIED
        ):
            raise CalibrationFitError(
                f"comparison {comparison.measurement_record_id} is not "
                "identity verified"
            )
        if comparison.predicted_total_requirement is None:
            raise CalibrationFitError(
                f"comparison {comparison.measurement_record_id} lacks total requirement"
            )
        scopes.append(_candidate_scope(comparison))
        adjustments.append(max(0, comparison.delta_vs_expected_bytes or 0))
        record_ids.append(comparison.measurement_record_id)

    scope = scopes[0]
    expected_scope_key = _scope_key(scope)
    if any(_scope_key(item) != expected_scope_key for item in scopes[1:]):
        raise CalibrationFitError(
            "all comparisons must have an identical verified calibration scope"
        )

    sorted_adjustments = sorted(adjustments)
    sample_count = len(sorted_adjustments)
    median_adjustment = sorted_adjustments[sample_count // 2]
    status: CalibrationCandidateStatus
    warnings: list[str] = [
        "Candidate is an empirical reserve scoped to this exact workload, not a "
        "general backend profile update.",
        "Acceptance records a review decision only; it does not modify any profile.",
    ]
    if sample_count < minimum_samples:
        status = CalibrationCandidateStatus.INSUFFICIENT_DATA
        warnings.append(
            f"Only {sample_count} verified samples are available; at least "
            f"{minimum_samples} are required for review-ready status."
        )
    else:
        status = CalibrationCandidateStatus.SCOPED_ENVELOPE

    candidate_seed = {
        "scope": scope.model_dump(mode="json"),
        "record_ids": record_ids,
        "adjustments": sorted_adjustments,
    }
    candidate_digest = hashlib.sha256(
        json.dumps(candidate_seed, sort_keys=True).encode()
    ).hexdigest()
    candidate_id = f"scoped-reserve-{candidate_digest[:16]}"
    return CalibrationProfileCandidate(
        candidate_id=candidate_id,
        status=status,
        scope=scope,
        comparison_record_ids=record_ids,
        sample_count=sample_count,
        additional_reserve_bytes=ByteRange(
            lower_bytes=sorted_adjustments[0],
            expected_bytes=median_adjustment,
            upper_bytes=sorted_adjustments[-1],
        ),
        confidence=Confidence.MEDIUM
        if status is CalibrationCandidateStatus.SCOPED_ENVELOPE
        else Confidence.LOW,
        assumptions=[
            "Additional reserve is max(0, observed peak - predicted expected total).",
            "The upper reserve is the maximum observed positive discrepancy.",
        ],
        warnings=warnings,
        evidence=[
            evidence for comparison in comparisons for evidence in comparison.evidence
        ],
    )


def review_calibration_candidate(
    candidate: CalibrationProfileCandidate,
    *,
    reviewer_id: str,
    status: Literal["accepted", "rejected"],
    notes: str,
) -> CalibrationReviewDecision:
    """Create an immutable human review artifact without promoting a profile."""
    if (
        candidate.status is CalibrationCandidateStatus.INSUFFICIENT_DATA
        and status == "accepted"
    ):
        raise CalibrationFitError("insufficient-data candidates cannot be accepted")
    return CalibrationReviewDecision(
        review_id=f"review-{_candidate_digest(candidate)[:16]}",
        candidate_id=candidate.candidate_id,
        candidate_digest=_candidate_digest(candidate),
        reviewer_id=reviewer_id,
        reviewed_at=datetime.now(UTC),
        status=CalibrationReviewStatus(status),
        notes=notes,
    )
