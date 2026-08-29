"""Tests for Phase 10b local runner, scoped fitting, and human review."""

import json
import sys

import pytest

from kvscope.calibration import (
    CalibrationCandidateStatus,
    CalibrationMeasurement,
    CalibrationMeasurementTemplate,
    CalibrationReviewStatus,
    CalibrationRunManifest,
    compare_calibration_measurement,
    fit_calibration_comparisons,
    review_calibration_candidate,
    run_calibration_manifest,
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
from kvscope.errors import CalibrationFitError
from kvscope.serialization.calibration import serialize_calibration_comparison_json


def _template() -> CalibrationMeasurementTemplate:
    return CalibrationMeasurementTemplate(
        record_id_prefix="runner-test",
        backend_profile_id="vllm-generic-unverified-v0",
        backend_version="0.6.6",
        hardware_profile_id="generic-discrete-16gib",
        model_id="qwen-example",
        model_revision="test-revision",
        model_config_digest=None,
        inference_config={
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
        measurement_source="local runner",
        measurement_method="external observation JSON",
        confidence=Confidence.HIGH,
        notes=None,
    )


def _report() -> MemoryFeasibilityReport:
    component = MemoryComponentRequirement(
        component="component", memory=ByteRange.exact(1), confidence=Confidence.HIGH
    )
    total = ByteRange(lower_bytes=100, expected_bytes=200, upper_bytes=300)
    aggregation = MemoryAggregationResult(
        resident_weights=component,
        kv_cache=component,
        runtime_overhead=component,
        known_subtotal=ByteRange.exact(3),
        total_requirement=total,
        confidence=Confidence.HIGH,
    )
    feasibility = FeasibilityResult(
        internal_status=InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        product_status=ProductFeasibilityStatus.FEASIBLE,
        requirement=total,
        known_subtotal=aggregation.known_subtotal,
        physical_total_bytes=1000,
        allocatable_before_headroom=ByteRange.exact(900),
        recommended_allocatable=ByteRange.exact(800),
        confidence=Confidence.HIGH,
        is_actionable=True,
        explanation="test report",
    )
    return MemoryFeasibilityReport(
        provenance=AnalysisProvenance(
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
        ),
        aggregation=aggregation,
        feasibility=feasibility,
        constraint_analysis=ConstraintAnalysis(confidence=Confidence.HIGH),
    )


def _measurement(record_id: str, observed: int) -> CalibrationMeasurement:
    return CalibrationMeasurement(
        schema_version="v0.1",
        record_id=record_id,
        collected_at="2025-01-15T12:00:00Z",
        backend_profile_id="vllm-generic-unverified-v0",
        backend_version="0.6.6",
        hardware_profile_id="generic-discrete-16gib",
        model_id="qwen-example",
        model_revision="test-revision",
        model_config_digest=None,
        inference_config=_template().inference_config,
        observed_peak_memory_bytes=observed,
        measurement_source="test",
        measurement_method="test",
        confidence=Confidence.HIGH,
        notes=None,
        evidence=[
            {
                "evidence_id": f"evidence-{record_id}",
                "source_type": "test",
                "source": "test fixture",
            }
        ],
    )


def test_local_runner_collects_repeated_observations_conservatively(tmp_path) -> None:
    """The runner uses local argv, imports observations, and selects the max peak."""
    observation_code = (
        "import json, os; "
        "open(os.environ['KVSCOPE_OBSERVATION_PATH'], 'w').write(json.dumps({"
        "'schema_version':'v0.1','observation_id':'obs','"
        "observed_at':'2025-01-15T12:00:00Z','observed_peak_memory_bytes':250,"
        "'evidence':[{'evidence_id':'tool','source_type':'tool','source':'test'}],"
        "'notes':None}))"
    )
    manifest = CalibrationRunManifest(
        schema_version="v0.1",
        run_id="runner-test",
        command=[sys.executable, "-c", observation_code],
        observation_json_path="observation.json",
        repetitions=2,
        timeout_seconds=10,
        working_directory=None,
        measurement=_template(),
        notes=None,
    )

    result = run_calibration_manifest(manifest, manifest_directory=tmp_path)

    assert len(result.successful_measurements) == 2
    assert result.conservative_peak_memory_bytes == 250
    assert result.selected_measurement_id == "runner-test-1"
    assert "KVSCOPE_OBSERVATION_PATH" not in result.model_dump_json()


def test_local_runner_records_nonzero_exit_without_a_measurement(tmp_path) -> None:
    """A failing command creates non-sensitive failure evidence and no result peak."""
    manifest = CalibrationRunManifest(
        schema_version="v0.1",
        run_id="failing-runner-test",
        command=[sys.executable, "-c", "raise SystemExit(7)"],
        observation_json_path="observation.json",
        timeout_seconds=10,
        working_directory=None,
        measurement=_template(),
        notes=None,
    )

    result = run_calibration_manifest(manifest, manifest_directory=tmp_path)

    assert result.successful_measurements == []
    assert result.failures[0].code == "command_nonzero_exit"
    assert result.failures[0].return_code == 7


def test_fit_requires_verified_same_scope_and_review_never_promotes() -> None:
    """Three verified comparisons yield a scoped candidate and review artifact."""
    report = _report()
    comparisons = [
        compare_calibration_measurement(report, _measurement("record-1", 200)),
        compare_calibration_measurement(report, _measurement("record-2", 230)),
        compare_calibration_measurement(report, _measurement("record-3", 260)),
    ]

    candidate = fit_calibration_comparisons(comparisons)
    review = review_calibration_candidate(
        candidate,
        reviewer_id="reviewer-1",
        status="accepted",
        notes="Samples are reproducible and within the stated scope.",
    )

    assert candidate.status is CalibrationCandidateStatus.SCOPED_ENVELOPE
    assert candidate.additional_reserve_bytes.upper_bytes == 60
    assert review.status is CalibrationReviewStatus.ACCEPTED
    assert review.candidate_id == candidate.candidate_id


def test_fit_rejects_partial_identity_and_accepting_insufficient_data() -> None:
    """Fit cannot generalize partial identity records or approve a weak candidate."""
    report = _report()
    partial_measurement = _measurement("partial", 220).model_copy(
        update={"backend_version": None, "confidence": Confidence.MEDIUM}
    )
    partial = compare_calibration_measurement(report, partial_measurement)
    with pytest.raises(CalibrationFitError, match="identity verified"):
        fit_calibration_comparisons([partial])

    candidate = fit_calibration_comparisons(
        [compare_calibration_measurement(report, _measurement("single", 220))]
    )
    assert candidate.status is CalibrationCandidateStatus.INSUFFICIENT_DATA
    with pytest.raises(CalibrationFitError, match="cannot be accepted"):
        review_calibration_candidate(
            candidate,
            reviewer_id="reviewer-1",
            status="accepted",
            notes="Not enough samples.",
        )


def test_cli_fit_emits_a_review_only_candidate(tmp_path, capsys) -> None:
    """The fit command consumes comparison JSON and exposes the scoped status."""
    report = _report()
    comparison_paths = []
    for index, observed in enumerate((200, 230, 260), start=1):
        comparison = compare_calibration_measurement(
            report, _measurement(f"cli-{index}", observed)
        )
        path = tmp_path / f"comparison-{index}.json"
        path.write_text(
            serialize_calibration_comparison_json(comparison), encoding="utf-8"
        )
        comparison_paths.append(path)

    arguments = ["calibrate", "fit"]
    for path in comparison_paths:
        arguments.extend(["--comparison-json", str(path)])
    arguments.extend(["--format", "json"])

    assert main(arguments) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["kind"] == "calibration_profile_candidate"
    assert output["status"] == "scoped_envelope"
