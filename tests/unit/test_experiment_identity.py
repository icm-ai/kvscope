"""Characterization tests for reproducible experiment identity behavior."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from kvscope.api import InferenceConfig, KVDType, WeightDType, resolve_model
from kvscope.calibration import (
    CalibrationComparisonStatus,
    CalibrationIdentityVerification,
    CalibrationMeasurement,
    compare_calibration_measurement,
    fit_calibration_comparisons,
    load_memory_feasibility_report,
    review_calibration_candidate,
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
from kvscope.engines.static_analysis import prepare_static_workload
from kvscope.errors import CalibrationFitError


def _config_data() -> dict[str, object]:
    return {
        "context_length": 4096,
        "batch_size": 2,
        "max_num_seqs": 4,
        "active_sequences": 4,
        "prefix_tokens": 3,
        "multimodal_tokens": 5,
        "weight_dtype": "fp16",
        "kv_dtype": "fp8",
        "graph_capture_enabled": True,
        "cpu_offload_bytes": 17,
    }


def _identity_data() -> dict[str, object]:
    return {
        "model_id": "model-a",
        "model_revision": "rev-a",
        "model_config_digest": "digest-a",
        "backend_profile_id": "backend-a",
        "backend_version": "1.2",
        "hardware_profile_id": "hardware-a",
        "inference_config": _config_data(),
    }


def _measurement_data() -> dict[str, object]:
    return {
        "schema_version": "v0.1",
        "record_id": "record-a",
        "collected_at": "2025-01-15T12:00:00Z",
        **_identity_data(),
        "observed_peak_memory_bytes": 200,
        "measurement_source": "test observation",
        "measurement_method": "unit test",
        "confidence": "medium",
        "notes": None,
        "evidence": [
            {
                "evidence_id": "identity-test",
                "source_type": "local_measurement",
                "source": "test fixture",
                "version": "1",
                "observed_at": "2025-01-15T12:00:00Z",
                "notes": None,
            }
        ],
    }


def _report_data(*, partial: bool = False) -> MemoryFeasibilityReport:
    component = MemoryComponentRequirement(
        component="component", memory=ByteRange.exact(1), confidence=Confidence.HIGH
    )
    total = (
        None
        if partial
        else ByteRange(lower_bytes=100, expected_bytes=200, upper_bytes=300)
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
        internal_status=InternalFeasibilityStatus.UNKNOWN
        if partial
        else InternalFeasibilityStatus.GUARANTEED_FEASIBLE,
        product_status=ProductFeasibilityStatus.UNKNOWN
        if partial
        else ProductFeasibilityStatus.FEASIBLE,
        requirement=total,
        known_subtotal=aggregation.known_subtotal,
        physical_total_bytes=1000,
        allocatable_before_headroom=ByteRange.exact(900),
        recommended_allocatable=ByteRange.exact(800),
        confidence=Confidence.UNKNOWN if partial else Confidence.HIGH,
        is_actionable=not partial,
        explanation="identity characterization",
    )
    identity = {
        key: value
        for key, value in _identity_data().items()
        if key != "inference_config"
    }
    return MemoryFeasibilityReport(
        provenance=AnalysisProvenance(
            **identity, inference_config=AnalysisInferenceConfig(**_config_data())
        ),
        aggregation=aggregation,
        feasibility=feasibility,
        constraint_analysis=ConstraintAnalysis(confidence=feasibility.confidence),
    )


def _compare(
    *,
    report_identity: dict[str, object] | None = None,
    measurement_identity: dict[str, object] | None = None,
    partial_report: bool = False,
    provenance: bool = True,
) -> object:
    report = _report_data(partial=partial_report)
    data = _measurement_data()
    if report_identity is not None and provenance:
        identity = {
            key: value
            for key, value in report_identity.items()
            if key != "inference_config"
        }
        report_config = report_identity.get("inference_config", _config_data())
        report = report.model_copy(
            update={
                "provenance": AnalysisProvenance(
                    **identity,
                    inference_config=AnalysisInferenceConfig(**report_config),
                )
            },
        )
    if not provenance:
        report = report.model_copy(update={"provenance": None})
    if measurement_identity is not None:
        data.update(measurement_identity)
        data["inference_config"] = measurement_identity.get(
            "inference_config", _config_data()
        )
    return compare_calibration_measurement(
        report, CalibrationMeasurement.model_validate(data)
    )


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("model_id", "model-b"),
        ("backend_profile_id", "backend-b"),
        ("hardware_profile_id", "hardware-b"),
        ("backend_version", "1.3"),
        ("model_revision", "rev-b"),
        ("model_config_digest", "digest-b"),
    ],
)
def test_identity_metadata_mismatches_preserve_field_names(
    field: str, changed: str
) -> None:
    changed_data = {field: changed}
    result = _compare(measurement_identity=changed_data)
    assert result.identity_verification is CalibrationIdentityVerification.MISMATCH
    assert result.status is CalibrationComparisonStatus.IDENTITY_MISMATCH
    assert result.identity_mismatches == [
        f"{field}: report={_identity_data()[field]!r}, measurement={changed!r}"
    ]
    assert result.delta_vs_expected_bytes is None


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("context_length", 8192),
        ("batch_size", 3),
        ("max_num_seqs", 5),
        ("active_sequences", 5),
        ("prefix_tokens", 4),
        ("multimodal_tokens", 6),
        ("weight_dtype", "fp8"),
        ("kv_dtype", "int8"),
        ("graph_capture_enabled", False),
        ("cpu_offload_bytes", 18),
    ],
)
def test_each_config_field_is_compared_independently(
    field: str, changed: object
) -> None:
    altered = {**_config_data(), field: changed}
    result = _compare(measurement_identity={"inference_config": altered})
    assert result.identity_verification is CalibrationIdentityVerification.MISMATCH
    assert result.status is CalibrationComparisonStatus.IDENTITY_MISMATCH
    expected_mismatch = (
        f"inference_config.{field}: report={_config_data()[field]!r}, "
        f"measurement={changed!r}"
    )
    assert result.identity_mismatches == [expected_mismatch]
    assert result.delta_vs_expected_bytes is None


def test_matching_identity_is_verified_and_comparable() -> None:
    result = _compare()
    assert result.identity_verification is CalibrationIdentityVerification.VERIFIED
    assert result.status is CalibrationComparisonStatus.COMPARABLE
    assert result.delta_vs_expected_bytes == 0


@pytest.mark.parametrize(
    ("report_shape", "measurement_shape", "expected"),
    [
        ("none", "none", "partial"),
        ("revision", "none", "partial"),
        ("none", "revision", "partial"),
        ("digest", "none", "partial"),
        ("none", "digest", "partial"),
        ("none", "both", "partial"),
        ("revision", "revision", "verified"),
        ("revision", "digest", "partial"),
        ("digest", "revision", "partial"),
        ("digest", "digest", "verified"),
        ("both", "none", "partial"),
        ("both", "both", "verified"),
        ("both", "revision", "verified"),
        ("both", "digest", "verified"),
        ("revision", "both", "verified"),
        ("digest", "both", "verified"),
    ],
)
def test_fingerprint_unknown_policy(
    report_shape: str, measurement_shape: str, expected: str
) -> None:
    shapes = {
        "none": (None, None),
        "revision": ("rev-a", None),
        "digest": (None, "digest-a"),
        "both": ("rev-a", "digest-a"),
    }
    report_revision, report_digest = shapes[report_shape]
    measurement_revision, measurement_digest = shapes[measurement_shape]
    report_identity = {
        **_identity_data(),
        "model_revision": report_revision,
        "model_config_digest": report_digest,
    }
    result = _compare(
        report_identity=report_identity,
        measurement_identity={
            "model_revision": measurement_revision,
            "model_config_digest": measurement_digest,
        },
    )
    assert result.identity_verification.value == expected


@pytest.mark.parametrize(
    ("report_version", "measurement_version", "expected"),
    [
        ("1.2", "1.2", CalibrationIdentityVerification.VERIFIED),
        ("1.2", "1.3", CalibrationIdentityVerification.MISMATCH),
        (None, "1.2", CalibrationIdentityVerification.PARTIAL),
        ("1.2", None, CalibrationIdentityVerification.PARTIAL),
        (None, None, CalibrationIdentityVerification.PARTIAL),
    ],
)
def test_backend_version_unknown_matrix(
    report_version: str | None,
    measurement_version: str | None,
    expected: CalibrationIdentityVerification,
) -> None:
    report_identity = {**_identity_data(), "backend_version": report_version}
    result = _compare(
        report_identity=report_identity,
        measurement_identity={"backend_version": measurement_version},
    )
    assert result.identity_verification is expected


def test_one_matching_and_one_mismatching_fingerprint_is_mismatch() -> None:
    result = _compare(
        measurement_identity={
            "model_revision": "rev-a",
            "model_config_digest": "different",
        }
    )
    assert result.identity_verification is CalibrationIdentityVerification.MISMATCH
    assert result.identity_mismatches == [
        "model_config_digest: report='digest-a', measurement='different'"
    ]


def test_partial_backend_version_warns_but_mismatch_still_wins() -> None:
    data = {"backend_version": None}
    result = _compare(measurement_identity=data)
    assert result.identity_verification is CalibrationIdentityVerification.PARTIAL
    assert result.warnings[1] == (
        "backend_version is unknown in the report or measurement; identity "
        "verification is partial."
    )
    mismatch = _compare(
        measurement_identity={"model_id": "different", "backend_version": None}
    )
    assert mismatch.identity_verification is CalibrationIdentityVerification.MISMATCH
    assert (
        mismatch.identity_mismatches[0]
        == "model_id: report='model-a', measurement='different'"
    )
    assert "backend_version is unknown" in mismatch.warnings[1]


def test_unavailable_and_incomplete_report_precedence() -> None:
    unavailable = _compare(provenance=False)
    assert (
        unavailable.identity_verification is CalibrationIdentityVerification.UNAVAILABLE
    )
    assert unavailable.status is CalibrationComparisonStatus.IDENTITY_UNVERIFIED
    incomplete = _compare(partial_report=True, provenance=False)
    assert incomplete.status is CalibrationComparisonStatus.INCOMPLETE_REPORT
    assert (
        incomplete.identity_verification is CalibrationIdentityVerification.UNAVAILABLE
    )
    mismatch_incomplete = _compare(
        partial_report=True, measurement_identity={"model_id": "different"}
    )
    assert mismatch_incomplete.status is CalibrationComparisonStatus.INCOMPLETE_REPORT
    assert mismatch_incomplete.identity_mismatches == [
        "model_id: report='model-a', measurement='different'"
    ]


def test_diagnostic_order_and_repr_are_stable() -> None:
    measurement = deepcopy(_measurement_data())
    measurement.update(
        {
            "model_id": "other",
            "backend_profile_id": "other-backend",
            "hardware_profile_id": "other-hw",
            "backend_version": "2",
            "model_revision": "other-rev",
            "model_config_digest": "other-digest",
        }
    )
    measurement["inference_config"] = {
        **_config_data(),
        "context_length": 8192,
        "weight_dtype": "int4",
        "graph_capture_enabled": False,
    }
    result = compare_calibration_measurement(
        _report_data(), CalibrationMeasurement.model_validate(measurement)
    )
    assert result.identity_mismatches == [
        "model_id: report='model-a', measurement='other'",
        "backend_profile_id: report='backend-a', measurement='other-backend'",
        "hardware_profile_id: report='hardware-a', measurement='other-hw'",
        "inference_config.context_length: report=4096, measurement=8192",
        "inference_config.weight_dtype: report='fp16', measurement='int4'",
        "inference_config.graph_capture_enabled: report=True, measurement=False",
        "backend_version: report='1.2', measurement='2'",
        "model_revision: report='rev-a', measurement='other-rev'",
        "model_config_digest: report='digest-a', measurement='other-digest'",
    ]


@pytest.mark.parametrize(
    ("batch", "max_seqs", "override", "expected_active"),
    [
        (6, 2, None, 6),
        (2, 6, None, 6),
        (4, 4, None, 4),
        (2, 4, 7, 7),
        (2, 4, 4, 4),
    ],
)
def test_static_projection_records_exactly_effective_identity(
    batch: int,
    max_seqs: int,
    override: int | None,
    expected_active: int,
) -> None:
    config = InferenceConfig(
        weight_dtype=WeightDType.INT4,
        kv_dtype=KVDType.FP8,
        context_length=8192,
        batch_size=batch,
        max_num_seqs=max_seqs,
        prefix_tokens=11,
        multimodal_tokens=13,
        cpu_offload_bytes=19,
        graph_capture_enabled=False,
        safety_margin_ratio=0.2,
        active_sequences_override=override,
    )
    resolved = resolve_model("qwen-example").model_copy(
        update={
            "spec": resolve_model("qwen-example").spec.model_copy(
                update={"parameter_count": 1_000}
            )
        }
    )
    projected = prepare_static_workload(resolved, config).inference_provenance
    assert list(projected.model_dump()) == list(_config_data())
    assert projected.model_dump() == {
        "context_length": 8192,
        "batch_size": batch,
        "max_num_seqs": max_seqs,
        "active_sequences": expected_active,
        "prefix_tokens": 11,
        "multimodal_tokens": 13,
        "weight_dtype": "int4",
        "kv_dtype": "fp8",
        "graph_capture_enabled": False,
        "cpu_offload_bytes": 19,
    }


def test_override_source_and_safety_margin_do_not_change_persisted_identity() -> None:
    model = resolve_model("qwen-example")
    model = model.model_copy(
        update={"spec": model.spec.model_copy(update={"parameter_count": 1_000})}
    )
    base = InferenceConfig(
        weight_dtype=WeightDType.FP16,
        kv_dtype=KVDType.FP16,
        context_length=4096,
        batch_size=2,
        max_num_seqs=4,
        safety_margin_ratio=0,
    )
    equivalent = base.model_copy(
        update={"active_sequences_override": 4, "safety_margin_ratio": 0.75}
    )
    assert base.active_sequences_source == "max_num_seqs"
    assert equivalent.active_sequences_source == "explicit"
    assert prepare_static_workload(model, base).inference_provenance.model_dump() == (
        prepare_static_workload(model, equivalent).inference_provenance.model_dump()
    )


def test_wire_models_keep_distinct_names_shared_fields_and_strict_contract() -> None:
    from kvscope.calibration.schema import CalibrationInferenceConfig

    fields = [
        "context_length",
        "batch_size",
        "max_num_seqs",
        "active_sequences",
        "prefix_tokens",
        "multimodal_tokens",
        "weight_dtype",
        "kv_dtype",
        "graph_capture_enabled",
        "cpu_offload_bytes",
    ]
    assert list(AnalysisInferenceConfig.model_fields) == fields
    assert list(CalibrationInferenceConfig.model_fields) == fields
    assert AnalysisInferenceConfig is not CalibrationInferenceConfig
    assert AnalysisInferenceConfig.__name__ == "AnalysisInferenceConfig"
    assert CalibrationInferenceConfig.__name__ == "CalibrationInferenceConfig"
    for model in (AnalysisInferenceConfig, CalibrationInferenceConfig):
        assert model.model_config["frozen"] is True
        assert model.model_config["extra"] == "forbid"
        assert (
            model.model_validate(
                {**_config_data(), "weight_dtype": "  custom dtype "}
            ).weight_dtype
            == "  custom dtype "
        )
        with pytest.raises(ValidationError):
            model.model_validate({**_config_data(), "context_length": True})
        with pytest.raises(ValidationError):
            model.model_validate({**_config_data(), "graph_capture_enabled": 1})
        with pytest.raises(ValidationError):
            model.model_validate({**_config_data(), "weight_dtype": ""})
        with pytest.raises(ValidationError):
            model.model_validate({**_config_data(), "unexpected": 1})


def test_verified_comparisons_with_different_optional_fingerprints_do_not_fit() -> None:
    revision_only = _compare(measurement_identity={"model_config_digest": None})
    digest_only = _compare(measurement_identity={"model_revision": None})
    assert (
        revision_only.identity_verification is CalibrationIdentityVerification.VERIFIED
    )
    assert digest_only.identity_verification is CalibrationIdentityVerification.VERIFIED
    with pytest.raises(
        CalibrationFitError, match="identical verified calibration scope"
    ):
        fit_calibration_comparisons([revision_only, digest_only])


def test_real_static_report_provenance_compares_through_public_api(
    tmp_path, capsys
) -> None:
    report_path = tmp_path / "report.json"
    assert (
        main(
            [
                "analyze",
                "qwen-example",
                "--hardware",
                "generic-discrete-16gib",
                "--backend",
                "vllm",
                "--backend-version",
                "0.6.6",
                "--parameter-count",
                "4000000000",
                "--context",
                "4096",
                "--format",
                "json",
            ]
        )
        == 0
    )
    report_path.write_text(capsys.readouterr().out, encoding="utf-8")
    report = load_memory_feasibility_report(report_path)
    provenance = report.provenance
    assert provenance is not None
    comparisons = []
    for index, observed in enumerate((200, 230, 260), start=1):
        data = _measurement_data()
        data.update(
            {
                "record_id": f"static-report-{index}",
                "observed_peak_memory_bytes": observed,
                "model_id": provenance.model_id,
                "model_revision": provenance.model_revision,
                "model_config_digest": provenance.model_config_digest,
                "backend_profile_id": provenance.backend_profile_id,
                "backend_version": provenance.backend_version,
                "hardware_profile_id": provenance.hardware_profile_id,
                "inference_config": provenance.inference_config.model_dump(mode="json"),
            }
        )
        measurement = CalibrationMeasurement.model_validate(data)
        result = compare_calibration_measurement(report, measurement)
        assert result.identity_verification is CalibrationIdentityVerification.VERIFIED
        assert result.status is CalibrationComparisonStatus.COMPARABLE
        assert result.delta_vs_expected_bytes is not None
        comparisons.append(result)
    candidate = fit_calibration_comparisons(comparisons)
    review = review_calibration_candidate(
        candidate,
        reviewer_id="identity-test-reviewer",
        status="accepted",
        notes="Static report round-trip identity fixture.",
    )
    assert candidate.status.value == "scoped_envelope"
    assert candidate.sample_count == 3
    assert review.candidate_digest
