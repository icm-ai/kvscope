"""Offline comparison of feasibility estimates and collected peak measurements."""

from __future__ import annotations

from kvscope.calibration.schema import (
    CalibrationComparison,
    CalibrationComparisonStatus,
    CalibrationIdentityVerification,
    CalibrationMeasurement,
    RelativeError,
)
from kvscope.domain.enums import Confidence
from kvscope.domain.evidence import Evidence
from kvscope.domain.experiment_identity import (
    ExperimentIdentityView,
    verify_experiment_identity,
)
from kvscope.domain.report import MemoryFeasibilityReport
from kvscope.domain.signed_ranges import subtract_exact_bytes_from_range

_CONFIDENCE_ORDER: dict[Confidence, int] = {
    Confidence.UNKNOWN: 0,
    Confidence.LOW: 1,
    Confidence.MEDIUM: 2,
    Confidence.HIGH: 3,
    Confidence.EXACT: 4,
}


def _minimum_confidence(*values: Confidence) -> Confidence:
    """Return the least confident value using KVScope's stable confidence order."""
    return min(values, key=lambda value: _CONFIDENCE_ORDER[value])


def _deduplicate_evidence(evidence: list[Evidence]) -> list[Evidence]:
    """Preserve first-seen evidence while avoiding repeated evidence identifiers."""
    seen_ids: set[str] = set()
    result: list[Evidence] = []
    for item in evidence:
        if item.evidence_id not in seen_ids:
            seen_ids.add(item.evidence_id)
            result.append(item)
    return result


def _non_comparable_result(
    *,
    status: CalibrationComparisonStatus,
    report: MemoryFeasibilityReport,
    measurement: CalibrationMeasurement,
    identity_verification: CalibrationIdentityVerification,
    identity_mismatches: list[str],
    predicted_total_requirement: object,
    assumptions: list[str],
    warnings: list[str],
    evidence: list[Evidence],
) -> CalibrationComparison:
    """Return a structured result without deriving an unsafe error conclusion."""
    from kvscope.domain.ranges import ByteRange

    predicted = (
        predicted_total_requirement
        if isinstance(predicted_total_requirement, ByteRange)
        else None
    )
    return CalibrationComparison(
        status=status,
        measurement_record_id=measurement.record_id,
        report_schema_version=report.schema_version,
        measurement=measurement,
        identity_verification=identity_verification,
        identity_mismatches=identity_mismatches,
        predicted_total_requirement=predicted,
        observed_peak_memory_bytes=measurement.observed_peak_memory_bytes,
        observed_within_predicted_range=None,
        delta_vs_lower_bytes=None,
        delta_vs_expected_bytes=None,
        delta_vs_upper_bytes=None,
        signed_error=None,
        relative_error_vs_expected=None,
        confidence=Confidence.UNKNOWN,
        assumptions=assumptions,
        warnings=warnings,
        evidence=evidence,
    )


def compare_calibration_measurement(
    report: MemoryFeasibilityReport,
    measurement: CalibrationMeasurement,
) -> CalibrationComparison:
    """Compare one measurement with a complete, identity-matching report.

    The signed deltas are ``observed - predicted``. A positive value means the
    observed peak was larger than the corresponding predicted boundary. A report
    that mismatches the recorded model, backend, hardware, or inference settings
    is rejected without an error conclusion. This function never changes profiles.
    """
    aggregation = report.aggregation
    assumptions = [
        "The observed peak is compared only with aggregation.total_requirement.",
        "Observed memory accuracy depends on the measurement source and method "
        "recorded in the calibration measurement.",
    ]
    warnings = ["This offline comparison does not modify backend profiles or reserves."]
    evidence = _deduplicate_evidence([*measurement.evidence, *aggregation.evidence])
    provenance = report.provenance
    report_identity = (
        ExperimentIdentityView(
            model_id=provenance.model_id,
            backend_profile_id=provenance.backend_profile_id,
            hardware_profile_id=provenance.hardware_profile_id,
            inference_config=provenance.inference_config,
            backend_version=provenance.backend_version,
            model_revision=provenance.model_revision,
            model_config_digest=provenance.model_config_digest,
        )
        if provenance is not None
        else None
    )
    measurement_identity = ExperimentIdentityView(
        model_id=measurement.model_id,
        backend_profile_id=measurement.backend_profile_id,
        hardware_profile_id=measurement.hardware_profile_id,
        inference_config=measurement.inference_config,
        backend_version=measurement.backend_version,
        model_revision=measurement.model_revision,
        model_config_digest=measurement.model_config_digest,
    )
    identity_result = verify_experiment_identity(report_identity, measurement_identity)
    identity = CalibrationIdentityVerification(identity_result.state.value)
    mismatches = list(identity_result.mismatches)
    warnings.extend(identity_result.warnings)

    if aggregation.is_partial or aggregation.total_requirement is None:
        missing_components = ", ".join(aggregation.missing_components) or "unspecified"
        warnings.append(
            "Comparison is incomplete because the feasibility report has no complete "
            f"total requirement (missing components: {missing_components})."
        )
        return _non_comparable_result(
            status=CalibrationComparisonStatus.INCOMPLETE_REPORT,
            report=report,
            measurement=measurement,
            identity_verification=identity,
            identity_mismatches=mismatches,
            predicted_total_requirement=None,
            assumptions=assumptions,
            warnings=warnings,
            evidence=evidence,
        )

    predicted = aggregation.total_requirement
    if identity is CalibrationIdentityVerification.UNAVAILABLE:
        warnings.append(
            "Comparison was not calculated because report provenance is unavailable."
        )
        return _non_comparable_result(
            status=CalibrationComparisonStatus.IDENTITY_UNVERIFIED,
            report=report,
            measurement=measurement,
            identity_verification=identity,
            identity_mismatches=mismatches,
            predicted_total_requirement=predicted,
            assumptions=assumptions,
            warnings=warnings,
            evidence=evidence,
        )
    if identity is CalibrationIdentityVerification.MISMATCH:
        warnings.append(
            "Comparison was not calculated because report provenance does not match "
            "the measurement record."
        )
        return _non_comparable_result(
            status=CalibrationComparisonStatus.IDENTITY_MISMATCH,
            report=report,
            measurement=measurement,
            identity_verification=identity,
            identity_mismatches=mismatches,
            predicted_total_requirement=predicted,
            assumptions=assumptions,
            warnings=warnings,
            evidence=evidence,
        )

    observed = measurement.observed_peak_memory_bytes
    delta_vs_lower = observed - predicted.lower_bytes
    delta_vs_expected = observed - predicted.expected_bytes
    delta_vs_upper = observed - predicted.upper_bytes
    relative_error = (
        RelativeError(
            numerator_bytes=delta_vs_expected,
            denominator_bytes=predicted.expected_bytes,
        )
        if predicted.expected_bytes > 0
        else None
    )
    if relative_error is None:
        warnings.append(
            "Expected predicted requirement is zero, so relative error is unavailable."
        )
    if identity is CalibrationIdentityVerification.PARTIAL:
        warnings.append(
            "Partial identity verification caps comparison confidence at medium."
        )

    confidence = _minimum_confidence(
        aggregation.confidence,
        report.feasibility.confidence,
        measurement.confidence,
    )
    if identity is CalibrationIdentityVerification.PARTIAL:
        confidence = _minimum_confidence(confidence, Confidence.MEDIUM)

    return CalibrationComparison(
        status=CalibrationComparisonStatus.COMPARABLE,
        measurement_record_id=measurement.record_id,
        report_schema_version=report.schema_version,
        measurement=measurement,
        identity_verification=identity,
        identity_mismatches=mismatches,
        predicted_total_requirement=predicted,
        observed_peak_memory_bytes=observed,
        observed_within_predicted_range=(
            predicted.lower_bytes <= observed <= predicted.upper_bytes
        ),
        delta_vs_lower_bytes=delta_vs_lower,
        delta_vs_expected_bytes=delta_vs_expected,
        delta_vs_upper_bytes=delta_vs_upper,
        signed_error=subtract_exact_bytes_from_range(observed, predicted),
        relative_error_vs_expected=relative_error,
        confidence=confidence,
        assumptions=assumptions,
        warnings=warnings,
        evidence=evidence,
    )
