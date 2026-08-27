"""Tests for Phase 10a offline calibration import and comparison."""

import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from kvscope.calibration import (
    CalibrationComparisonStatus,
    CalibrationMeasurement,
    compare_calibration_measurement,
    load_calibration_measurement,
)
from kvscope.cli.app import main
from kvscope.domain.aggregation import (
    MemoryAggregationResult,
    MemoryComponentRequirement,
)
from kvscope.domain.constraints import ConstraintAnalysis
from kvscope.domain.enums import (
    Confidence,
    InternalFeasibilityStatus,
    ProductFeasibilityStatus,
)
from kvscope.domain.feasibility import FeasibilityResult
from kvscope.domain.ranges import ByteRange
from kvscope.domain.report import (
    AnalysisInferenceConfig,
    AnalysisProvenance,
    MemoryFeasibilityReport,
)
from kvscope.serialization.json import serialize_feasibility_report_json


def _measurement_data() -> dict[str, object]:
    return {
        "schema_version": "v0.1",
        "record_id": "test-vllm-record-001",
        "collected_at": "2025-01-15T12:00:00Z",
        "backend_profile_id": "vllm-generic-unverified-v0",
        "backend_version": "0.6.6",
        "hardware_profile_id": "generic-discrete-16gib",
        "model_id": "qwen-example",
        "model_revision": "test-revision",
        "model_config_digest": None,
        "inference_config": {
            "context_length": 4096,
            "batch_size": 1,
            "max_num_seqs": 1,
            "active_sequences": 1,
            "prefix_tokens": 0,
            "multimodal_tokens": 0,
            "weight_dtype": "fp16",
            "kv_dtype": "fp16",
            "graph_capture_enabled": False,
            "cpu_offload_bytes": 0,
        },
        "observed_peak_memory_bytes": 200,
        "measurement_source": "local monitoring export",
        "measurement_method": "peak device-memory value",
        "confidence": "high",
        "notes": None,
        "evidence": [
            {
                "evidence_id": "test-local-export",
                "source_type": "local_measurement",
                "source": "redacted test export",
                "version": "1",
                "observed_at": "2025-01-15T12:00:00Z",
                "notes": None,
            }
        ],
    }


def _measurement(observed: int) -> CalibrationMeasurement:
    data = _measurement_data()
    data["observed_peak_memory_bytes"] = observed
    return CalibrationMeasurement.model_validate(data)


def _provenance() -> AnalysisProvenance:
    return AnalysisProvenance(
        model_id="qwen-example",
        model_revision="test-revision",
        model_config_digest=None,
        backend_profile_id="vllm-generic-unverified-v0",
        backend_version="0.6.6",
        hardware_profile_id="generic-discrete-16gib",
        inference_config=AnalysisInferenceConfig(
            context_length=4096,
            batch_size=1,
            max_num_seqs=1,
            active_sequences=1,
            prefix_tokens=0,
            multimodal_tokens=0,
            weight_dtype="fp16",
            kv_dtype="fp16",
            graph_capture_enabled=False,
            cpu_offload_bytes=0,
        ),
    )


def _report(
    *, partial: bool = False, include_provenance: bool = True
) -> MemoryFeasibilityReport:
    component = MemoryComponentRequirement(
        component="component",
        memory=ByteRange.exact(1),
        confidence=Confidence.HIGH,
    )
    total = None if partial else ByteRange(
        lower_bytes=100, expected_bytes=200, upper_bytes=300
    )
    aggregation = MemoryAggregationResult(
        resident_weights=component,
        kv_cache=component,
        runtime_overhead=component,
        known_subtotal=ByteRange.exact(3),
        total_requirement=total,
        is_partial=partial,
        missing_components=["runtime_overhead"] if partial else [],
        confidence=Confidence.UNKNOWN if partial else Confidence.HIGH,
    )
    feasibility = FeasibilityResult(
        internal_status=(
            InternalFeasibilityStatus.UNKNOWN
            if partial
            else InternalFeasibilityStatus.GUARANTEED_FEASIBLE
        ),
        product_status=(
            ProductFeasibilityStatus.UNKNOWN
            if partial
            else ProductFeasibilityStatus.FEASIBLE
        ),
        requirement=total,
        known_subtotal=aggregation.known_subtotal,
        physical_total_bytes=1000,
        allocatable_before_headroom=ByteRange.exact(900),
        recommended_allocatable=ByteRange.exact(800),
        confidence=Confidence.UNKNOWN if partial else Confidence.HIGH,
        is_actionable=not partial,
        explanation="test report",
    )
    return MemoryFeasibilityReport(
        provenance=_provenance() if include_provenance else None,
        aggregation=aggregation,
        feasibility=feasibility,
        constraint_analysis=ConstraintAnalysis(confidence=feasibility.confidence),
    )


def test_loader_round_trip_preserves_nullable_unknowns(tmp_path) -> None:
    """A valid local record round-trips through strict JSON loading."""
    measurement_file = tmp_path / "measurement.json"
    measurement_file.write_text(json.dumps(_measurement_data()), encoding="utf-8")

    loaded = load_calibration_measurement(measurement_file)

    assert loaded.record_id == "test-vllm-record-001"
    assert loaded.model_config_digest is None
    assert loaded.observed_peak_memory_bytes == 200


@pytest.mark.parametrize(
    ("observed", "within"),
    [(200, True), (301, False), (99, False)],
)
def test_compare_reports_interval_membership_and_signed_deltas(
    observed: int, within: bool
) -> None:
    """Measurements in, above, and below the prediction interval stay auditable."""
    comparison = compare_calibration_measurement(_report(), _measurement(observed))

    assert comparison.status is CalibrationComparisonStatus.COMPARABLE
    assert comparison.observed_within_predicted_range is within
    assert comparison.delta_vs_lower_bytes == observed - 100
    assert comparison.delta_vs_expected_bytes == observed - 200
    assert comparison.delta_vs_upper_bytes == observed - 300
    assert comparison.signed_error is not None
    assert comparison.signed_error.lower_bytes == observed - 300
    assert comparison.relative_error_vs_expected is not None
    assert comparison.relative_error_vs_expected.denominator_bytes == 200


def test_compare_rejects_provenance_mismatch() -> None:
    """A report with different runtime settings cannot produce an error conclusion."""
    mismatched_data = _measurement_data()
    mismatched_data["inference_config"] = {
        **mismatched_data["inference_config"],
        "context_length": 8192,
    }
    comparison = compare_calibration_measurement(
        _report(), CalibrationMeasurement.model_validate(mismatched_data)
    )

    assert comparison.status is CalibrationComparisonStatus.IDENTITY_MISMATCH
    assert comparison.observed_within_predicted_range is None
    assert "inference_config.context_length" in comparison.identity_mismatches[0]


def test_compare_rejects_report_without_provenance() -> None:
    """Legacy reports lacking provenance remain explicitly non-comparable."""
    comparison = compare_calibration_measurement(
        _report(include_provenance=False), _measurement(200)
    )

    assert comparison.status is CalibrationComparisonStatus.IDENTITY_UNVERIFIED
    assert comparison.observed_within_predicted_range is None


def test_compare_partial_report_returns_no_optimistic_conclusion() -> None:
    """A partial report produces a structured non-comparable result."""
    comparison = compare_calibration_measurement(
        _report(partial=True), _measurement(200)
    )

    assert comparison.status is CalibrationComparisonStatus.INCOMPLETE_REPORT
    assert comparison.predicted_total_requirement is None
    assert comparison.observed_within_predicted_range is None
    assert comparison.confidence is Confidence.UNKNOWN
    assert "no complete total requirement" in " ".join(comparison.warnings)


def test_loader_rejects_invalid_json_and_non_positive_observed_bytes(tmp_path) -> None:
    """Loader errors identify invalid JSON and disallow zero or negative byte peaks."""
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        load_calibration_measurement(invalid_file)

    zero_data = deepcopy(_measurement_data())
    zero_data["observed_peak_memory_bytes"] = 0
    zero_file = tmp_path / "zero.json"
    zero_file.write_text(json.dumps(zero_data), encoding="utf-8")
    with pytest.raises(ValueError, match="greater than 0"):
        load_calibration_measurement(zero_file)

    with pytest.raises(ValidationError, match="confidence no higher"):
        unknown_data = deepcopy(_measurement_data())
        unknown_data["backend_version"] = None
        CalibrationMeasurement.model_validate(unknown_data)

    wrong_schema_data = deepcopy(_measurement_data())
    wrong_schema_data["schema_version"] = "v9.9"
    schema_file = tmp_path / "wrong-schema.json"
    schema_file.write_text(json.dumps(wrong_schema_data), encoding="utf-8")
    with pytest.raises(ValueError, match="calibration-record-v0.1.json"):
        load_calibration_measurement(schema_file)


def test_cli_calibrate_compare_terminal_and_json(tmp_path, capsys) -> None:
    """Terminal and JSON CLI formats use the local loaders and comparison result."""
    report_file = tmp_path / "report.json"
    measurement_file = tmp_path / "measurement.json"
    report_file.write_text(
        serialize_feasibility_report_json(_report()), encoding="utf-8"
    )
    measurement_file.write_text(json.dumps(_measurement_data()), encoding="utf-8")
    args = [
        "calibrate",
        "compare",
        "--report-json",
        str(report_file),
        "--measurement-json",
        str(measurement_file),
    ]

    assert main(args) == 0
    assert "KVScope Calibration Comparison" in capsys.readouterr().out

    assert main([*args, "--format", "json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["kind"] == "calibration_comparison"
    assert output["status"] == "comparable"

    assert main([*args, "--format", "markdown"]) == 0
    assert "# KVScope Calibration Comparison" in capsys.readouterr().out


def test_cli_calibrate_compare_reports_partial_input(tmp_path, capsys) -> None:
    """The CLI renders an explicit incomplete result and returns a nonzero status."""
    report_file = tmp_path / "partial-report.json"
    measurement_file = tmp_path / "measurement.json"
    report_file.write_text(
        serialize_feasibility_report_json(_report(partial=True)), encoding="utf-8"
    )
    measurement_file.write_text(json.dumps(_measurement_data()), encoding="utf-8")

    assert (
        main(
            [
                "calibrate",
                "compare",
                "--report-json",
                str(report_file),
                "--measurement-json",
                str(measurement_file),
            ]
        )
        == 3
    )
    assert "INCOMPLETE REPORT" in capsys.readouterr().out
