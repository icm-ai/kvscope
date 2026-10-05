"""Tests for Phase 10b local runner, scoped fitting, and human review."""

import json
import sys
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from kvscope.calibration import (
    CalibrationCandidateStatus,
    CalibrationMeasurement,
    CalibrationMeasurementTemplate,
    CalibrationReviewStatus,
    CalibrationRunManifest,
    compare_calibration_measurement,
    export_calibration_measurements,
    fit_calibration_comparisons,
    load_calibration_comparison,
    load_calibration_measurement,
    load_calibration_profile_candidate,
    load_calibration_run_manifest,
    review_calibration_candidate,
    run_calibration_manifest,
)
from kvscope.calibration.artifacts import (
    COMPARISON,
    MEASUREMENT,
    OBSERVATION,
    PROFILE_CANDIDATE,
    REVIEW_DECISION,
    RUN_MANIFEST,
    RUN_RESULT,
    CalibrationArtifact,
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
from kvscope.errors import CalibrationFitError, CalibrationLoadError
from kvscope.serialization.calibration import serialize_calibration_comparison_json
from kvscope.serialization.calibration_runner import (
    serialize_calibration_profile_candidate_json,
    serialize_calibration_review_json,
    serialize_calibration_run_json,
)


def _assert_schema_valid(artifact: CalibrationArtifact[Any], instance: object) -> None:
    """Validate a real calibration artifact against its published schema."""
    schema_dir = Path(__file__).resolve().parents[2] / "src/kvscope/schemas"
    schema = json.loads((schema_dir / artifact.schema_filename).read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(instance)


assert_artifact_valid = _assert_schema_valid


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

    assert_artifact_valid(
        RUN_RESULT, json.loads(serialize_calibration_run_json(result))
    )
    assert_artifact_valid(
        MEASUREMENT, result.successful_measurements[0].model_dump(mode="json")
    )
    assert_artifact_valid(
        OBSERVATION,
        {
            "schema_version": "v0.1",
            "observation_id": "sample",
            "observed_at": "2025-01-15T12:00:00Z",
            "observed_peak_memory_bytes": 250,
            "evidence": [
                {"evidence_id": "tool", "source_type": "tool", "source": "test"}
            ],
            "notes": None,
        },
    )
    assert len(result.successful_measurements) == 2
    assert result.conservative_peak_memory_bytes == 250
    assert result.selected_measurement_id == "runner-test-1"
    assert "KVSCOPE_OBSERVATION_PATH" not in result.model_dump_json()

    exported_paths = export_calibration_measurements(result, tmp_path / "measurements")
    assert len(exported_paths) == 2
    assert load_calibration_measurement(exported_paths[0]).record_id == "runner-test-1"
    assert "runner-test-1" not in exported_paths[0].name
    with pytest.raises(ValueError, match="would overwrite"):
        export_calibration_measurements(result, tmp_path / "measurements")


def test_cli_run_exports_standalone_measurements(tmp_path, capsys) -> None:
    """The run CLI exposes exported records that feed directly into compare."""
    observation_code = (
        "import json, os; "
        "open(os.environ['KVSCOPE_OBSERVATION_PATH'], 'w').write(json.dumps({"
        "'schema_version':'v0.1','observation_id':'cli-observation',"
        "'observed_at':'2025-01-15T12:00:00Z','observed_peak_memory_bytes':250,"
        "'evidence':[{'evidence_id':'tool','source_type':'tool','source':'test'}],"
        "'notes':None}))"
    )
    manifest = CalibrationRunManifest(
        schema_version="v0.1",
        run_id="cli-runner-test",
        command=[sys.executable, "-c", observation_code],
        observation_json_path="observation.json",
        timeout_seconds=10,
        working_directory=None,
        measurement=_template(),
        notes=None,
    )
    manifest_path = tmp_path / "run.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    assert_artifact_valid(RUN_MANIFEST, manifest.model_dump(mode="json"))
    assert (
        main(
            [
                "calibrate",
                "run",
                "--manifest-json",
                str(manifest_path),
                "--output-dir",
                "measurements",
                "--format",
                "json",
            ]
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    exported = output["exported_measurement_paths"]
    assert len(exported) == 1
    assert load_calibration_measurement(exported[0]).record_id == "runner-test-1"


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

    assert_artifact_valid(
        COMPARISON, json.loads(serialize_calibration_comparison_json(comparisons[0]))
    )
    assert_artifact_valid(
        PROFILE_CANDIDATE,
        json.loads(serialize_calibration_profile_candidate_json(candidate)),
    )
    assert_artifact_valid(
        REVIEW_DECISION, json.loads(serialize_calibration_review_json(review))
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


def test_legacy_bare_json_and_kind_compatibility_are_preserved(tmp_path) -> None:
    """Loaders keep legacy bare comparison/candidate and record/manifest rules."""
    comparison = compare_calibration_measurement(_report(), _measurement("legacy", 220))
    comparison_path = tmp_path / "comparison.json"
    comparison_path.write_text(comparison.model_dump_json(), encoding="utf-8")
    assert load_calibration_comparison(comparison_path) == comparison
    comparison_path.write_text(
        json.dumps({**json.loads(comparison.model_dump_json()), "kind": "wrong"}),
        encoding="utf-8",
    )
    with pytest.raises(CalibrationLoadError) as comparison_error:
        load_calibration_comparison(comparison_path)
    assert comparison_error.value.code == "unexpected_artifact_kind"

    candidate = fit_calibration_comparisons([comparison])
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(candidate.model_dump_json(), encoding="utf-8")
    assert load_calibration_profile_candidate(candidate_path) == candidate

    manifest = CalibrationRunManifest(
        schema_version="v0.1",
        run_id="legacy-manifest",
        command=[sys.executable, "-c", "pass"],
        observation_json_path="observation.json",
        working_directory=None,
        measurement=_template(),
        notes=None,
    )
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({**json.loads(manifest.model_dump_json()), "kind": "ignored"}),
        encoding="utf-8",
    )
    assert load_calibration_run_manifest(manifest_path) == manifest


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
