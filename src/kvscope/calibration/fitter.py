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
from kvscope.domain.report import AnalysisProvenance, MemoryFeasibilityReport
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


def _format_mismatch(
    field_name: str, report_value: object, measurement_value: object
) -> str:
    """Describe one deterministic report-to-measurement identity mismatch."""
    return (
        f"{field_name}: report={report_value!r}, "
        f"measurement={measurement_value!r}"
    )


def _verify_identity(
    provenance: AnalysisProvenance | None,
    measurement: CalibrationMeasurement,
) -> tuple[CalibrationIdentityVerification, list[str], list[str]]:
    """Compare report provenance with measurement identity without guessing."""
    if provenance is None:
        return (
            CalibrationIdentityVerification.UNAVAILABLE,
            [],
            [
                "The feasibility report has no provenance, so its model, backend, "
                "hardware, and inference configuration cannot be verified."
            ],
        )

    mismatches: list[str] = []
    warnings: list[str] = []
    required_values = {
        "model_id": (provenance.model_id, measurement.model_id),
        "backend_profile_id": (
            provenance.backend_profile_id,
            measurement.backend_profile_id,
        ),
        "hardware_profile_id": (
            provenance.hardware_profile_id,
            measurement.hardware_profile_id,
        ),
    }
    for field_name, (report_value, measurement_value) in required_values.items():
        if report_value != measurement_value:
            mismatches.append(
                _format_mismatch(field_name, report_value, measurement_value)
            )

    report_config = provenance.inference_config
    measurement_config = measurement.inference_config
    config_values = {
        "context_length": (
            report_config.context_length,
            measurement_config.context_length,
        ),
        "batch_size": (report_config.batch_size, measurement_config.batch_size),
        "max_num_seqs": (report_config.max_num_seqs, measurement_config.max_num_seqs),
        "active_sequences": (
            report_config.active_sequences,
            measurement_config.active_sequences,
        ),
        "prefix_tokens": (
            report_config.prefix_tokens,
            measurement_config.prefix_tokens,
        ),
        "multimodal_tokens": (
            report_config.multimodal_tokens,
            measurement_config.multimodal_tokens,
        ),
        "weight_dtype": (report_config.weight_dtype, measurement_config.weight_dtype),
        "kv_dtype": (report_config.kv_dtype, measurement_config.kv_dtype),
        "graph_capture_enabled": (
            report_config.graph_capture_enabled,
            measurement_config.graph_capture_enabled,
        ),
        "cpu_offload_bytes": (
            report_config.cpu_offload_bytes,
            measurement_config.cpu_offload_bytes,
        ),
    }
    for config_field_name, (
        config_report_value,
        config_measurement_value,
    ) in config_values.items():
        if config_report_value != config_measurement_value:
            mismatches.append(
                _format_mismatch(
                    f"inference_config.{config_field_name}",
                    config_report_value,
                    config_measurement_value,
                )
            )

    is_partial = False
    if provenance.backend_version is None or measurement.backend_version is None:
        is_partial = True
        warnings.append(
            "backend_version is unknown in the report or measurement; identity "
            "verification is partial."
        )
    elif provenance.backend_version != measurement.backend_version:
        mismatches.append(
            _format_mismatch(
                "backend_version",
                provenance.backend_version,
                measurement.backend_version,
            )
        )

    shared_model_fingerprint = False
    model_fingerprints = {
        "model_revision": (provenance.model_revision, measurement.model_revision),
        "model_config_digest": (
            provenance.model_config_digest,
            measurement.model_config_digest,
        ),
    }
    for fingerprint_name, (
        report_fingerprint,
        measurement_fingerprint,
    ) in model_fingerprints.items():
        if report_fingerprint is None or measurement_fingerprint is None:
            continue
        shared_model_fingerprint = True
        if report_fingerprint != measurement_fingerprint:
            mismatches.append(
                _format_mismatch(
                    fingerprint_name,
                    report_fingerprint,
                    measurement_fingerprint,
                )
            )
    if not shared_model_fingerprint:
        is_partial = True
        warnings.append(
            "No common model revision or config digest is available; identity "
            "verification is partial."
        )

    if mismatches:
        return CalibrationIdentityVerification.MISMATCH, mismatches, warnings
    if is_partial:
        return CalibrationIdentityVerification.PARTIAL, [], warnings
    return CalibrationIdentityVerification.VERIFIED, [], warnings


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
    identity, mismatches, identity_warnings = _verify_identity(
        report.provenance, measurement
    )
    warnings.extend(identity_warnings)

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
